# 2026-09-21: decode kv-direct (c) bf16 producer-direct cache write — PARTIAL LAND verdict — bf16 direct rotate landed; kv-window leg open

Lane: DecodeKvDirect. Base: `mlx-omarchy` `bf16-decode-gdn` tip 1af87a50d.
Candidate branch: local `agent/decode-kv-direct` @ 649b315 (worktree
`~/src/wt-decode-kv-direct`; never pushed, wheel never promoted).
Wheels: diag.649b315 built on M1 host (0229) and M1 Max host (0231), profiling harness on.

## What was implemented (change c)

1. `shaders/fast_rope.comp` bf16 leg: output changed from a float32 temp to
   packed bf16 words. Each lane store is a disjoint-half `atomicOr` (the two
   lanes of one output word can belong to different invocations; each word
   receives exactly two ORs that each zero the other half, so the OR result
   should be the packed value regardless of order). The store applies the RNE
   f32->bf16 rounding the cast kernel used to apply. All six shader variants
   compile clean (glslc, x86 check).
2. `RoPE::eval_gpu`: the `MLX_OMARCHY_ROPE_BF16_DIRECT` env gate and the
   CastBF16F32/CastF32BF16 sandwich are deleted — bf16 rotates directly
   (packed-word load, packed-word store). f16/f32 paths unchanged.
3. `fused_chain.cpp` `direct_window_geometry` + both window planners: direct
   KV windows accept bf16 caches (member/base/update same dtype), and record
   `in_place` when the cache buffer's only in-tape consumer is the pair
   member (uses == 1). `KvDirectWindow` grew an `in_place` flag.
4. `primitives.cpp` values fence + rope fence: bf16 accepted; with `in_place`,
   the producer writes new rows straight into the live cache (node shares
   base storage) and the per-layer per-token full-cache copy disappears.
   Guards: rope out dtype must equal cache dtype; even element offset for
   bf16; odd bf16 passthrough refused.
5. Tests: the rope bf16 case lost the env-gate/wrapped leg (the wrapped path
   no longer exists); direct vs composed + f64 reference kept.
   docs/install-omarchy.md env list updated.

## Measurement — M1 host A/B (same protocol as the GDN receipt: eager, 64-token
window, France x16 prompt, temp 0 seed 0, flock /tmp/m1-gpu.lock, model =
HF snapshot models--SiddhJagani--Qwen3.8-2B-mlx-4Bit, venv ~/gdn/venv with
the mlx-lm gated_delta routing patch; logs on M1 host /tmp/kvdirect-ab.log,
results /var/tmp/kvdirect/results/kvdirect-{before,after})

| arm | wheel | decode gpu_busy | decode dispatches | CopyGeneralBF16 n | greedy identity |
| --- | --- | ---: | ---: | ---: | --- |
| before (baseline) | 5b183060 | 1573.642 ms | 22410 (747/tok) | 4650 | 760 1156 369 9859 ... 248046 198 — matches the bf16 reference stream |
| after (candidate) | diag.649b315 | 3227.166 ms | 45549 | 7015 | all zeros — BROKEN |

Baseline arm reproduces the GDN receipt's numbers exactly (22410, 1573 ms),
so the harness and model pin are correct. The candidate is a hard failure:
generation collapses to token 0 from the first step, decode dispatches and
gpu_busy double (fused-plan aborts cascade back to ordinary paths), and
CopyGeneralBF16 goes UP not down.

## Root cause (isolated empirically on M1 host, scripts /tmp/ropediag*.py)

`mx.fast.rope` bf16 vs an f32 composed reference, shape matrix:

| shape | dims | result |
| --- | --- | --- |
| full rotation (dims == D), any layout | — | correct (<= 0.02, bf16 rounding) |
| passthrough, D=64 dims=32 T=29 | 32 | wrong values (6.49), no NaN |
| passthrough, D=128 dims=32 T=1 | 32 | WRONG — 229 NaN (the same shape passed at 0.0058 in an earlier run: nondeterministic) |
| passthrough, D=256 dims=64 (model shape, T=29 and T=1) | 64 | NaN / garbage both layouts |

Verdict: the packed bf16 output store via disjoint-half `atomicOr` is
unsound on the Apple-hardware Vulkan driver (Asahi Mesa). Under the
passthrough branch (one element per invocation, so the two lanes of a word
are written by different invocations) lanes are intermittently lost, leaving
recycled-memory garbage (NaN, 3.4e38) in the output. The full-rotation
branch (two stores per invocation) happened to pass but rides the same
mechanism and cannot be trusted. The f32-temp + cast kernel it replaced was
the proven form; this leg of the change must be redone without atomics —
e.g. pair-granular processing (one invocation computes and stores both lanes
of each output word) or a 16-bit-typed store if the llvmpipe uint16 block
bug ever gets a second look on-device.

The isolation chain: FUSED_CHAIN=0 and KV_DIRECT=0 both still produced
all-zero tokens with the candidate wheel (baseline wheel + FUSED_CHAIN=0
produces the correct stream), which cleared the planner/in-place work and
pinned the plain bf16 rope leg; the shape matrix then split full-rotation
(correct) from passthrough (broken, nondeterministic).

## M1 Max host

The M1 Max host A/B window was invalid (harness file missing after staging; both
arms produced degenerate streams), so no M1 Max host numbers are claimed. The M1 Max host
wheel exists at /var/tmp/kvdirect/dist (diag.649b315) and the venv was left
with the NEW wheel installed — install 4517642 or newer before next use.

## Disposition

- NO-LAND. Branch `agent/decode-kv-direct` kept for the record; do not
  build serving wheels from it.
- The planner-side work (bf16 window geometry, in-place producer-direct
  write with the uses==1 proof, dtype fences) compiled and is unexercised
  but unproven; it is only sound behind a working bf16-out rope.
- M1 host venv restored to the 5b183060 baseline wheel and re-verified against
  the reference stream after the experiments.

## (b) norm->scale->rope micro-chain — scoped, not attempted

The full-attention decode chain is q_norm/k_norm (`mx.fast.rms_norm` with
weight, FastRmsNormBF16) -> transpose view -> rope (dims = 0.25*head_dim,
partial rotation). A true norm->rope fold is a NEW primitive (reduction +
rotation in one dispatch, view-chain and strided-input handling, bf16
rounding contract) — high effort, and the honest expected gain is the ~12
dispatches/token (2 norms + 2 ropes over 6 full-attn layers, ~= 1.6% of
M1 host's 747) and well under 1% decode GPU (these kernels are ~25-30 us each).
The cheaper (b) lever with existing plumbing: lift the f16-only
FastTrioRopePair fusion (shaders/fast_trio.comp TRIO_ROPE_PAIR,
fused_chain.cpp rope-pair plan, dispatch_rope_pair) to bf16 — 2 ropes -> 1
dispatch per layer, 6 dispatches/token — but it must wait for a sound bf16
out-of-place rope store, and its key side keeps the kv-direct window.

## Next lever (step 3, to be re-profiled on a clean baseline)

With (c) not landing, the remaining decode CopyGeneralBF16 mass (2.2% GPU on
M1 host, ~24 dispatches/token for the f16 sandwich + cache copies in the
current wheel) still points at the kv-copy elimination as the right lever —
via a sound bf16 store mechanism — now proven to be the pair-granular
word store below (the atomicOr theory was wrong; see Addendum 2).

## Addendum 2: pair-granular store PASSES — A/B measured (same session)

The Mesa lane proved atomicOr sound and that ropediag7's "transposed"
diffs reproduce with the stock wheel: my diagnostic's composed reference
applied the position axis over the wrong axis for transposed layouts
(time is shape(-2) in-kernel; the script indexed the N axis). The
pair-granular kernel was correct once the r2 side used the mirrored
rotation index (commits 495482535 + fixups). Ground truth:

tokid with the diag.pairfix3 wheel reproduces the bf16 reference stream
token-for-token (760 1156 369 9859 ... 248046 198).

A/B on the M1 host (same protocol; before = 5b183060, after =
diag.pairfix3, results kvdirect-{before,after}):

| arm | decode gpu_busy | dispatches/token | CastF32BF16 n | CopyGeneralBF16 n | identity |
| --- | ---: | ---: | ---: | ---: | --- |
| before | 1576.746 ms | 747 (22410) | 3958 | 4650 | reference stream |
| after | 1531.929 ms (−2.8%) | 723 (21690, −24/tok) | 3563 | 4639 | identical, 32/32 |

The −24 dispatches/token are the deleted bf16 rope f32 sandwich
(cast-in + cast-out x 2 ropes x 6 full-attn layers = 24) plus the
per-token margin; CastF32BF16 n drops by the predicted ~384. The
producer-direct KV window (the in-place cache-copy elimination) did NOT
engage for bf16: CopyGeneralBF16 n is essentially unchanged (−11), so
the values/rope window planners still refuse the bf16 pair somewhere
upstream of the fences. That leg remains open work; the landed win is
the direct bf16 rotate (no f32 interior) with bit-identical output.

M1 host venv left with diag.pairfix3 (identity-verified).

## Addendum 1: pair-granular rewrite iteration

Per review steer, the atomicOr store was replaced by a pair-granular
bf16 main (each invocation owns whole output words and computes both
lanes; plain stores, no atomics) — commits 495482535 + two fixups in
`agent/decode-kv-direct`. Host guards: even rotation half, even
passthrough extent, passthrough count halved to word granularity.

Empirical status on the M1 host (shape matrix /tmp/ropediag7.py):

- contiguous non-passthrough and contiguous passthrough: CORRECT
  (maxdiff 0.016-0.019, bf16 rounding) after fixing the r2 side to use
  the mirrored rotation index (element - half_dims).
- ALL head-seq-transposed layouts: still wrong (maxdiff ~3-7,
  deterministic, no NaN). The loads/theta/out addressing are
  symbol-for-symbol the std kernel's head_seq_transpose formulas, so
  the remaining defect is not yet understood; it needs the in-repo
  rope value tests (which run per-device) rather than more remote
  guesswork.

Verdict stands: NO-LAND. M1 host venv restored to the 5b183060 baseline
wheel and re-verified against the reference stream after every
iteration. The atomicOr lane-loss reproducer package
(atomicor-lane-loss/) is handed to the Mesa divergence lane.

Next step for this lane: add a bf16 transposed-layout case to the
in-repo fast_rope value tests, debug the head_seq_transpose leg of the
pair main locally (llvmpipe reproduces the value contract for the f16
twin; check whether it does for bf16 pairs), and only then re-run the
A/B windows.


## Addendum 3: why the producer-direct KV window refuses — the dense-GEMV gate

Source-level finding (fused_chain.cpp): plan_values_window classifies the
values side only through the QUANTIZED GEMV groups (gemv_groups) — the
update chain must end in an Add that is a QuantizedMatmul member's
epilogue. In the 2B full-attention layers, v comes from a plain dense
bf16 Linear served by dense_gemv_groups (dispatch_dense_gemv_group),
which has no sum_window/epilogue support at all. The values side is
therefore never classifiable on this model, no DirectPlan is formed,
and every layer/token falls back to the merged SliceUpdatePair
dispatch that materializes the full-cache copy — this predates the
bf16 work (it is why the CopyGeneralBF16 mass existed at all).

Next lever (concrete): add producer-direct window write support to the
DENSE decode GEMV path — a strided-row store variant of the dense bf16
GEMV shader (matmul_vec bf16 family) plus a sum_window analog on
DenseGemvGroup members, then the existing rope-side fence/plumbing
(already bf16-clean in this branch) fires unchanged. Expected: removes
the ~4640-run CopyGeneralBF16 mass (~2.0% full-run GPU, ~2 copies x 6
layers x per-token in decode) on top of the measured -24
dispatches/token and -2.8% decode gpu_busy from the direct rotate.

## Addendum 4: M1 Max host A/B

The A/B is staged durably (~/gdn-harness/{profile_generate,profile_
analyze,tokid}.py; script /var/tmp/kvdirect/kvdirect-ab-M1 Max host.sh) and
was queued on /tmp/m1-gpu.lock behind another lane's window at session
end; it self-completes into /var/tmp/kvdirect/ab.log and
/var/tmp/M1 Max host-pd-receipts/kvdirect-{before,after}/ (before =
4517642 wheel, after = diag.pairfix3, identity runs both arms).

## Addendum 5: dense-GEMV values window — implemented, not yet engaging

Commit d3177f10e (branch agent/decode-kv-direct): plan_values_window now
accepts a dense decode GEMV member as the values terminal (same
view-chain proof, same geometry); DenseGemvGroup carries per-member
windows; the dense eval branch installs in-place storage and commits;
dispatch_dense_gemv_group takes a window array and sets the shader's
per-member window mode; matmul_vec_multi_bf16.comp scatters each
4-group of the row to (window offset) + (e/head_dim)*row_gap +
e%head_dim (flags bit 4096<<i, matrix_n=row gap, matrix_m=head dim).

Measured A/B (M1 host, before=5b183060, after=diag.densewin):
identical to the pairfix3 A/B — decode 21690 dispatches (723/tok),
gpu_busy 1528.5 ms, CopyGeneralBF16 n=4639 (unchanged), identity 32/32
identical to the reference stream in both arms. The dense window is
implemented but still not engaging: no additional dispatch or GPU-time
change beyond the already-landed direct rotate.

Open debugging leads, in order:
1. Is v_proj actually in a dense GROUP on this model (needs >=2 bf16
   Matmuls sharing the aliased x view, kDenseVecMultiWeights>=2)? If
   q/k/v are split across streams or the x alias check fails, the
   dense path never plans, and dense_roles is empty at classify time.
2. The view chain from the cache update to the Matmul node may pass
   through an op outside {Reshape, Transpose} (e.g. an explicit
   as_strided/contiguous from the transpose materialization).
3. The update use_count==1 check: the transposed values view may have a
   second tape consumer.
Trace hook needed: env-gated fprintf in the kv_direct plan loop
recording per-side rejection reason (the RopePairScanTrace pattern).

Environment: M1 host venv holds diag.densewin (identity-verified); M1
Max host A/B from Addendum 4 still queued on the lock — its script now
needs its NEW glob updated from pairfix3 to densewin before it fires.

## Addendum 6: trace verdict — no SliceUpdate pairs form on this model

MLX_OMARCHY_KV_TRACE (commit after d3177f10e) prints per-pair refusal
reasons from the direct-plan loop. On the pinned 2B bf16 decode it
prints NOTHING: state->slice_update_pairs is empty — the K/V cache
updates never form planable SliceUpdate pairs, so the entire
producer-direct machinery (quantized OR dense) never engages, and the
CopyGeneralBF16 mass comes from whatever update path mlx-lm's
ArraysCache/KVCache actually takes on this model. The -24
dispatches/token and -2.8% decode gpu_busy that DID land come from the
direct bf16 rotate alone; identity held in every measured arm.

Next lever, corrected: instrument/inspect the actual cache-update op
sequence on this model (profile the SliceUpdate/concat path — likely a
concat-based cache like ArraysCache, not slice-update pairs), then aim
the producer-direct write at the real update primitive. The dense-GEMV
window work (d3177f10e) stays valid and becomes reachable once pairs
(or their replacement) exist.

## Addendum 7: in-place widening measured — flat; the copies are not the KV slice updates

Widened the in-place proof to view-only extra consumers (the returned
keys[..., :offset] slice; commit after kvtrace, wheel diag.inplace2)
and restored the dense fresh-copy fallback. A/B result: IDENTICAL to
pairfix3/densewin — decode 21690 dispatches (723/tok), gpu_busy 1527.5
ms, CopyGeneralBF16 n=4639, identity 32/32 both arms.

Conclusion across three candidate wheels: the ~4639-run CopyGeneralBF16
mass (p50 30 us, 2048-element rows) does NOT respond to any kv-window
or in-place change, i.e. it does not come from the KV cache slice
updates at all. The landed, reproducible win remains the direct bf16
rotate: -24 dispatches/token, -2.8% decode gpu_busy, identity
bit-identical in every arm. The next investigation must first
attribute CopyGeneralBF16 decode dispatches to their call site (buffer
sizes + stack attribution in the encoder) before any further
producer-direct work; the kv-direct machinery in this branch is
implemented, abort-safe, and idle.

## Addendum 8: CopyGeneralBF16 attribution (MLX_OMARCHY_COPY_TRACE, one full tokid run)

Top sites by occurrence (counts are for one prefill + 32 decode tokens):

| n | bytes each | producer prim | out shape | site |
| ---: | ---: | --- | --- | --- |
| 2196 | 4096 | ExpandDims (of a strided cache-slice view, strides 2048,1,128,1) | 1,1,16,128 | contiguity copy of a strided (1,16,T,128) cache-slice row — ~36/token |
| 465 | 36864 | none (pre-materialized strided view) | 1,3,6144 | GDN conv-state window copy (conv_kernel window of the 6144 conv dim), ~7/token prefill-side |
| 411 | 12288 | none | — | same family, 3-step window |
| 298 | 262144 | none | — | large GDN/prefill-window copies |
| 273 | 4096 | none | 1,1,16,128 | the same cache-slice row copy with a materialized producer |

Total copied: 203.3 MB per generation. The dominant site (~36 copies of
4 KB per token, ~75% of all CopyGeneralBF16 dispatches) is a
contiguity copy of a strided one-step cache-slice view produced by an
ExpandDims — i.e. a consumer calling contiguous()/refusing strided
input on a (1,16,1,128) row of a preallocated K/V-shaped cache. The fix
is backend-side: make that consumer accept the strided row (the fused
kernels already take explicit strides) or keep the slice-update write
the row directly. This is a separate lane from kv-direct; the
attribution trace ships in copy.cpp under MLX_OMARCHY_COPY_TRACE.

## Addendum 9: consumer identification attempt — needs a symbolized build

Added backtrace_symbols_fd to the trace (first 40 copies). The wheel's
libmlx.so is stripped, so frames resolve to "libmlx.so" only — no
consumer identification. To finish: rebuild with -g (CMAKE_BUILD_TYPE
RelWithDebInfo or -DCMAKE_CXX_FLAGS=-g) and addr2line the captured
frames, or extend the encoder's dispatch record to carry the
MLX primitive name (trace::prim_counts already names primitives in
eval.cpp — plumb the current primitive into the dispatch record).

The stride fingerprints from the shape trace remain the strongest
lead: the 4096-byte copies read (2048,1,128,1) views — a (1,1,16,128)
slice of a 2048-stride parent, i.e. one time-step of a (·,·,·,128)
row-major cache/conv buffer whose 16-lane axis strides 128 — consumed
somewhere that forces a General contiguity copy instead of passing
strides.

## Addendum 10: consumer named — Concatenate (GDN conv-state rolling window)

With trace::current_prim plumbed into the copy record (eval.cpp sets a
thread_local around eval_gpu; copy.cpp prints it), the consumer
aggregate over one tokid run:

| n | consumer |
| ---: | --- |
| 3054 | Concatenate |
| 286 | SliceUpdate |
| 285 | ScaledDotProductAttention |
| 179 | RMSNorm |
| 148 | Reshape |
| 30 | Full |

The dominant 4096-byte ExpandDims copies AND the 36 KB copies are
Concatenate: the GDN conv-state rolling window in the vendored
mlx-lm gated_delta.py (concatenate([conv_state, qkv], axis=1) then
mx.contiguous(conv_input[:, -n_keep:, :]) per GDN layer per token, and
the keys/values ArraysCache growth).

Fix design (python, vendored mlx-lm patch, not a backend kernel):
replace the concat-per-token conv window with a preallocated rolling
buffer — cache[0] holds (B, N, conv_dim) with a write offset; each step
slice-update one qkv row (one 12 KB write) and run conv1d on the
contiguous 4-row window slice. CopyGeneralBF16 site (1) and (2)
disappear (36/token + 7/token); the SliceUpdate it adds is already the
primitive the kv-direct planner handles. Backend kernel work: none.
