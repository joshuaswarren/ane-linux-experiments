# 2026-09-23 — m1-host GDN decode chain fuse: FastNormGatedBF16 (rms_norm+swiglu / rms_norm+scale)

Lane: GdnFuse (m1-host). Target: the GDN f32-chain/elementwise micro-kernel
swarm measured by the m1host batch-budget receipt
(receipts/2026-09-23-m1host-decode-gap-batchbudget, 7fa42bd). Base:
installed `0.32.3.dev202609231540+8fed014e6` in both
`/var/tmp/v072-venv-fused` and `/var/tmp/vp/venv-cand`.

## 1. The swarm, from the profile (decode-window attribution, profiled build)

Per-token counts and GPU time (30 inter-token intervals, prof-p0.jsonl,
`scripts/kernels_decode.py`):

| kernel | n/tok | ms/tok | us/launch |
| --- | ---: | ---: | ---: |
| FastRmsNormBF16 | 115.0 | 2.965 | 25.8 |
| ElementwiseBF16 | 60.0 | 1.843 | 30.7 |
| CopyGeneralBF16 | 72.0 | 1.636 | 22.7 |
| CastBF16F32 | 54.0 | 1.128 | 20.9 |
| MatmulF32 (attention, not GDN) | 12.0 | 0.826 | 68.8 |
| CastF32BF16 | 24.0 | 0.773 | 32.2 |
| FusedChainF32 | 18.0 | 0.668 | 37.1 |
| ConvBF16 | 18.0 | 0.653 | 36.3 |
| BinaryVecBF16 | 24.0 | 0.586 | 24.4 |

chain_census token dump gives the exact per-GDN-layer sequence. The
chain this lane fuses:

- **Gated norm+swiglu** (`Qwen3NextRMSNormGated` + `_precise_swiglu`):
  FastRmsNormBF16 → CastBF16F32(z) → CastBF16F32(x) →
  FusedChainF32(sigmoid,mul,mul) → CastF32BF16 = 5 dispatches × 18
  layers = 90 dispatches/token on ≤8 KB tensors.
- **q/k norm+scale**: FastRmsNormBF16 → ElementwiseBF16(mul) ×2 = 72
  dispatches/token.

Not in scope (consumer-pattern limited, untouched): conv+silu (Conv +
sigmoid + mul), the concat CopyGeneral pair, attention-side
MatmulF32/SoftmaxF32/FastRopeBF16.

## 2. Change (mlx-omarchy `agent/gdn-fuse-m1host` @ 276c3b7dd, wheel @ 57c3963ad)

The eager chain scope cannot reach this chain (`_precise_swiglu` runs
as a compiled tape; the tape fuser cannot carry casts or the
two-operand silu·normed form), so the GDN raw-route precedent is used:
two new mlx-core fast primitives + one new backend kernel.

- `overlay/mlx/backend/omarchy/shaders/fast_norm_gated.comp` —
  FastNormGatedBF16, bf16, two modes. The norm body is copied verbatim
  from fast_norm.comp (256-thread workgroup, shared-memory tree reduce,
  `value*norm*weight` in f32). Mode 0 re-rounds the norm result to bf16
  (exactly what the composed path stores), widens, applies
  `1/(1+exp(-g))` then two f32 muls (the chain's sigmoid,mul,mul form,
  left-associated), rounds once. Mode 1 multiplies the widened norm
  result by `bf16_store(params.beta)` re-widened — reproducing the
  promote cast's RNE on the scalar without binding a buffer. Every
  intermediate the composed sequence rounds to bf16 is rounded here;
  f32 widens are exact ⇒ fused == composed bitwise by construction.
- `patches/mlx-fast-rms-norm-gated.patch` — mlx core
  `fast.rms_norm_gated(x, gate, w, eps)` and
  `fast.rms_norm_scaled(x, w, scale, eps)` (fast.h, fast_primitives.h
  Custom subclasses, fast.cpp with composed fallbacks, python bindings).
- `overlay/.../primitives.cpp` — RMSNormGated/RMSNormScaled eval_gpu
  dispatch FastNormGatedBF16 (mode via params.operation); loud
  `unsupported` outside bf16; bf16 out.
- `scripts/patch-mlx-lm-qwen35-gdn-norm.py` — routes
  Qwen3NextRMSNormGated and the q/k pairs (qwen3_next.py + qwen3_5.py),
  guarded on hasattr + bf16 + gpu + **size ≤ 32768 (≤256 rows)**.
- The two dg lane patch files referenced by prepare-mlx.sh
  (mlx-gated-delta-raw-gates, mlx-fast-greedy-argmax) were already
  tracked at 8fed014e6; the branch is self-contained.

Provenance note: the wheel was built at 57c3963ad; the commit was then
amended (276c3b7dd) changing ONLY the venv-side patch script (routing
gate), zero wheel-code delta.

## 3. Qualification

### Tensor-level bit-exactness (m1-host, cand venv, device)

40 gated cases — gated/weightless/scaled/weighted forms over
(16|1|7|256|3-row)×(128|2048) decode shapes, scales
inv_scale²/inv_scale/1/e/1e-3, extreme magnitudes, zero input:
**all 0 bits diff** (`.local/jgd-fuse/qual_bitexact.py`, output in
window.log + ab-gdnfuse/bitexact.txt).

**Known deviation, routed around:** at ≥512 rows (prefill chunks) a
rare ~1e-5-of-outputs 1-ULP deviation vs composed appears (e.g. 8 of
2M outputs, max_abs 1.95e-03 at [1,512,16,128]); row-count dependent,
side undetermined (fused large-grid vs composed large-tensor dispatch
difference — not root-caused in this lane's budget). The mlx-lm
routing therefore fuses decode-sized calls only; prefill keeps the
composed ops and is bit-identical to the installed baseline by
construction. Decode shapes (16 rows) are exhaustively clean.

### Digest + logits gate + A/B

Window: `scripts/window-gdnfuse.sh` (this dir), one persistent
`flock /tmp/m1-gpu.lock` hold; ctl = `/var/tmp/vp/venv-cand`
(installed 8fed014e6 config), cand = `/var/tmp/vprof/venv-gdnfuse`
(candidate wheel + mlx-lm 0.31.3 + dg gdn/gdn-raw/greedy-prune patches
+ this lane's gdn-norm patch). Protocol: bit-exact gate first (fail
fast), then 3 warmups + 10 interleaved paired contract reps per arm
(10 prompts, 32 new tokens, prefill 512, greedy), then logits gate v4
on both arms + compare, then greedy_qual smoke. Results:
`m1-host:/var/tmp/vprof/ab-gdnfuse/` (contract-ctl-rN.json,
contract-cand-rN.json, gate-*.json), log
`m1-host:/var/tmp/jgd-fuse/window.log`.

[RESULTS PENDING — window was running detached at receipt-writing
time; fill paired delta + digests + gate verdicts from
ab-gdnfuse/ when the window lands. Paired analysis with
receipts/2026-09-23-m1host-decode-gap-batchbudget/scripts/analyze_ab.py.]

## 4. Remaining gap to macOS 47.05

Decode 36.66 tok/s (8fed014e6 installed) = 77.9% of macOS; byte roof
61.2 tok/s on the 973 MB read set. This change attacks the ~5-6 ms/tok
micro-kernel swarm; the fused portion is ~90+72 of the ~200
elementwise-class launches (≈2.0 ms profiled / est. ~0.8-1.3 ms real ≈
+1.5-3.5 tok/s if the profiled ratio holds). Remaining after this
lane, in roofline order: greedy-head stage merge (~3 ms over bytes;
needs vocab-prune exactness re-proof), conv+silu and concat copies
(~1 ms combined, consumer-pattern or conv-epilogue work), GEMV
efficiency tail (~1 ms, dual-row NO-LAND on digest), submit-boundary
gaps (closed by 8fed014e6), MTP (only lever past the byte ceiling;
blocked on weights decision).

## Artifacts

- mlx-omarchy branch `agent/gdn-fuse-m1host` @ 276c3b7dd (worktree
  ~/src/wt-gdn-fuse).
- Candidate wheel `mlx_omarchy-0.32.3.dev202609231648+57c3963ad`
  sha256 f0da914f2b3d719d725122b7ec0d708dab8c2a24221388fd7f04de32ef437db8
  (chroot-host:~/src/GdnFuse-build/dist-out/, m1-host:/var/tmp/jgd-fuse/).
- m1-host: /var/tmp/jgd-fuse/ (window + qual + patch scripts, window.log),
  /var/tmp/vprof/ab-gdnfuse/ (bench + gate JSONs).
- This dir: window-gdnfuse.sh, launch-window.sh, qual_bitexact.py,
  kernels_decode.py (decode-window kernel attribution).
- T6001 handoff: sibling T6001 lane pulls the branch for its A/B (the
  norm/swiglu/cast portion of their 21 ms soup; ReduceF32/f32-state
  residual stays eager — next lever there).
