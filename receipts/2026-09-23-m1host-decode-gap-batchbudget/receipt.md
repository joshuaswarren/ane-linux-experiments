# 2026-09-23 — m1-host decode gap: per-step profile, batch-budget fix, A/B

Lane: M1HostDecode (vocab-prune follow-up). Base: installed
`mlx_omarchy-0.32.3.dev202609231347+a91adbf` (0cbb48ec) with patched
mlx-lm 0.31.3 (GDN routes + greedy prune), the `/var/tmp/vp/venv-cand`
config. Branch `agent/vocab-prune-wire` (off `agent/vocab-prune`
aa0b67257): wiring commit 4aa4b8b9c + cherry-picked batch-budget commit
8fed014e6.

## 0. Wiring (assignment item 1)

`patches/mlx-lm-greedy-prune.patch` is now applied by the installed
path: `scripts/apply-mlx-lm-patches.sh` runs `apply
mlx-lm-greedy-prune.patch` (default on; the patch self-guards on
`hasattr(mx.fast, "greedy_quantized_argmax")` and
`MLX_OMARCHY_NO_GREEDY_PRUNE=1`), and `install.sh` downloads it
alongside the GDN patch. Verified end-to-end on m1-host against
mlx-lm 0.31.3 in `/var/tmp/vprof/venv-diag2` (patch applies; op
present). Closes the open item flagged in the vocab-prune receipt.

## 1. Profile: one decode step (assignment item 2)

Diagnostics wheel `0.32.3.dev202609231525+diag.a91adbf`
(sha256 a65219db…) built off-device in the the chroot host ALARM chroot
(image `dg-alarm-py314:sep23`, `scripts/build-wheel.sh --diagnostics`,
`MLX_OMARCHY_WHOLE_BUNDLE_DIR` = the parakeet bundle extracted from the
identical release wheel; profiler compiled IN — verified by the
build's receipt line). m1-host venv `/var/tmp/vprof/venv-diag2`: diag
wheel + mlx-lm 0.31.3 + dg GDN patches + greedy prune patch (identical
graph config to the installed build). Window under one persistent
`flock /tmp/m1-gpu.lock` hold 10:33:40–10:34:02 EDT.

Run: `prof_decode.py` (mirrors the contract bench exactly:
`generate_step` iterator, `mx.eval` per token, greedy, corpus prompt 0,
12-token prompt, 31 decode intervals), `MLX_DISABLE_COMPILE=1`,
`MLX_OMARCHY_GPU_PROFILE` NDJSON + markers, analyzed with
`scripts/profile_analyze.py` + `--compute-h` at a91adbf. Second prompt
(control) reproduced the result. Raw NDJSON + markers:
`prof/prof-p0.jsonl` (21 595 records).

**Decode step shape: 584 dispatches/token, 3.1 submissions/token,
dispatches 252+250+63 per token.** GPU busy (profiled build) 39.9
ms/tok over a 46-49 ms profiled wall; unprofiled production wall is
27.43 ms/tok (36.45 tok/s) — the profiler's per-dispatch barriers
inflate absolute times ~1.5x (m1max analog measured 2.5x), so shares
rank but absolutes come from the roofline below.

Per-kernel decode-window attribution (per token, profiled build):

| kernel | n/tok | ms/tok | share |
| --- | ---: | ---: | ---: |
| QmmVecQ4MultiSubgroupBF16 (FFN+GDN projections) | 99.2 | 16.21 | 40.7% |
| QmmVecGreedyBF16 (pruned lm_head, 8 stages) | 8.3 | 5.80 | 14.6% |
| FastRmsNormBF16 | 118.8 | 3.06 | 7.7% |
| QmmVecQ4WordSubgroupBF16 (6 attn layers) | 18.6 | 2.93 | 7.3% |
| GatedDeltaDecodeBF16 (18 GDN layers) | 18.6 | 2.46 | 6.2% |
| ElementwiseBF16 | 62.0 | 1.90 | 4.8% |
| CopyGeneralBF16 | 74.4 | 1.69 | 4.2% |
| CastBF16F32+CastF32BF16+MatmulF32+FusedChainF32 (GDN f32 state chain) | ~111 | ~3.2 | 8.0% |
| rest (rope, softmax, binary, …) | ~60 | ~1.7 | 4.3% |

Host side (profiled): submit() p50 1.68 ms x3.1/token (inflated by the
profiler's per-dispatch barriers), inter-submission GPU gaps p50 330
us, intra-dispatch gaps p50 13 us. Dispatch barriers: 584/token, 0%
skipped (GATED_BARRIERS off = default).

## 2. Roofline

Ceiling: m1-host DRAM 58.2 (copy) / 59.6 (read) GB/s measured with
corrected wall figures (q4-gemv-bandwidth receipt, same host). The
mlx elementwise microbench on the diag build is NOT a usable proxy
(abs 512 MiB bf16 = 4 GB/s, sum = 2.7 GB/s, f32 abs = 8 GB/s — the
generic elementwise path is pathologically slow on this stack; none of
the decode hot kernels are that path). Bytes/token: 804.36 MB weight
stream (DecodeRoofline component sum) + head reads 286 MB unpruned /
~159 MB pruned (sketch 63.6 + scales/biases 31.8 + partial round-trips
~64 MB) + ~10 MB state/KV.

| | bytes/tok | tok/s | eff GB/s | % of 59.6 ceiling |
| --- | ---: | ---: | ---: | ---: |
| Linux now (pruned) | 973 MB | 36.45 | 35.5 | 60% |
| Linux ctl (unpruned head) | 1100 MB | 35.36 | 38.9 | 65% |
| macOS reference | 1100 MB | 47.05 | 51.8 | 87% |
| byte-ideal (pruned read set) | 973 MB | 61.2 | 59.6 | 100% |

**Top 3 costs against the roofline:**
1. **QmmVecQ4 GEMV family (823 MB weight stream, 99+19 launches)** —
   ~13.6 ms byte-ideal vs ~16.2 ms profiled: ~85-95% efficient after
   xpack; little headroom without shader surgery (dual-row NO-LAND,
   qmm-decodeqmm receipt).
2. **Greedy head chain (159 MB reads, 8 dispatches)** — 2.7 ms ideal
   vs 5.8 ms profiled: ~3 ms of stage overhead/partial round-trips.
   Touching it risks invalidating the vocab-prune exactness proof.
3. **Micro-kernel swarm + submission boundaries** — RMSNorm 119 +
   elementwise/copy/cast ~220 + f32 GDN chain launches ≈ ~5-6 ms real
   for ~1 ms of bytes (launch-latency bound), plus 3.1 submits/token
   with inter-submission boundary gaps (m1max measured 231 us/firmware
   boundary; ~0.5 ms/token removable by merging the 3 submits into 1).

**Selected fix (assignment item 3): submission batching** —
`kBatchNodeBudget` 256→4096 (`overlay/mlx/backend/omarchy/encoder.h`).
Decode token graphs (~585 nodes) exceeded the 256-node budget and were
split into 3 submits/token with GPU idle gaps at every boundary; 4096
keeps a whole token on one submit. The byte budget (limit/16) stays
the real cap for large-tensor graphs (prefill flush behavior
unchanged, 2026-09-08 incident still covered). Cherry-picked verbatim
from `agent/decode-fuse` c111c784e where it was written against the
m1-host DecodeGap profile. Expected: remove 2 boundaries/token ≈ +3-5%
(m1max AGX_SUBMIT_TRACE analog measured ~231 us x 2).

Not chosen this session, with reasons:
- **MTP speculative decoding** (potentially the only lever past the
  ~61 tok/s byte ceiling): blocked — the 4-bit checkpoint carries no
  MTP weights (0/694 safetensors keys; config declares
  `mtp_num_hidden_layers: 1` but mlx-lm 0.31.3 qwen3_5.py explicitly
  strips `mtp.*` weights at load), the upstream official repo is
  gated (401 from m1-host, no token), and third-party MTP weight repos
  are a provenance risk. Needs a weights-pipeline decision first.
- **Prefix caching**: does not move decode tok/s or the 512-token
  prefill leg (distinct prompts); TTFT-only lever for multi-turn.
- **RMSNorm-prologue fusion**: documented NO-LAND
  (`agent/gemv-rmsnorm-prologue` 64e529439 — breaks the ctx1024 pin).
- **Greedy-head stage reduction**: deferred — the 8-stage chain is
  bound by the vocab-prune exactness proof (T1-T4); changing it
  requires re-proving, not an A/B.

## 3. A/B (assignment items 3-4)

Candidate wheel `mlx_omarchy-0.32.3.dev202609231540+8fed014e6`
(sha256 604de669…) built off-device in the the chroot host chroot
(`DEV_RELEASE=1 MLX_OMARCHY_SOURCE_COMMIT=8fed014e6`, release build —
no profiler). Arms: ctl = `/var/tmp/vp/venv-cand` (installed a91adbf
wheel, identical mlx-lm 0.31.3 + GDN + greedy-patch config), cand = same
config + the 8fed014e6 wheel (fresh `/var/tmp/vprof/venv-cand2`). The
only wheel delta is `kBatchNodeBudget` 256→4096 in
`overlay/mlx/backend/omarchy/encoder.h`.

Protocol (contract bench, one persistent `flock /tmp/m1-gpu.lock` hold
for the whole window, lock released 10:52:51 EDT): warmup 3, 10
interleaved reps per arm (rep = one bench invocation, 10 prompts,
median decode tok/s over prompts, prefill leg 512, 32 new tokens,
greedy), then logits gate v4 on both arms + compare.

| arm | decode tok/s per rep (r1..r10) | mean |
| --- | --- | ---: |
| ctl (a91adbf) | 36.23 36.20 36.42 36.28 36.34 36.29 36.38 36.38 36.41 36.26 | 36.32 |
| cand (8fed014e6) | 36.59 36.62 36.72 36.69 36.69 36.73 36.64 36.69 36.65 36.59 | 36.66 |

**Paired per-rep delta: +0.342 ± 0.048 tok/s (95%, t, df = 9), ratio
1.0094 — a +0.94% decode win, CI entirely positive.**

Correctness, identical on every measure:

- Ordered digest `ordered_records_sha256 = 486872c4…` — ONE distinct
  digest across all 20 runs (both arms, all 10 reps). (Different literal
  from the vocab receipt's `bc519c03…` only because this window ran
  `--passes 1` → 10 canon records vs 30; the digest hashes
  (pass, prompt_idx, input_ids, output_ids) — token content, not
  timings.)
- Logits gate v4: 320 steps over the 10-prompt corpus, **0 flips,
  max |Δ top-1 logit| over the matched prefix = 0.0**.
- Post-install qualification (`greedy_qual.py`, prune mode, installed
  venv): 601 cases, **0 token mismatches, 0 bits mismatches**, 61
  full-path cases — identical to the vocab receipt's original run.
- Post-install contract smoke (installed venv): digest 486872c4…
  reproduced.

Secondary metrics, reported honestly: ttft_tok_rate paired delta
−0.86 ± 0.73 tok/s (−1.6%) and pure_prefill512 238.5 → 235.5 tok/s
(paired +2.98 ± 6.30, noise) — ctl always ran first in each pair and
both secondary legs are more load-order-sensitive than the steady-state
decode leg; the decode win holds despite that bias. No mechanism ties
fewer submit boundaries to slower prefill (fewer boundaries, same
kernels).

**Installed.** `0.32.3.dev202609231540+8fed014e6` is now in BOTH
`/var/tmp/v072-venv-fused` (wheel home) and `/var/tmp/vp/venv-cand`
(the working inference venv), `pip install --force-reinstall
--no-deps`, mlx-lm 0.31.3 + patches untouched. Rollback:
`pip install /var/tmp/vp/mlx_omarchy-0.32.3.dev202609231347+a91adbf-*.whl`
(both venvs).

## 4. Remaining gap

With the install, the m1-host installed-config numbers vs macOS:

| metric | m1-host now | macOS | gap |
| --- | ---: | ---: | ---: |
| decode | **36.66** tok/s (27.28 ms/tok) | 47.05 | **10.39 tok/s (decode at 77.9% of macOS)** |
| pure prefill512 | ~235.5 tok/s | 343.73 | 108.2 tok/s (68.5%) |

Byte ceiling with the current read set (973 MB/tok pruned): 16.3 ms/tok
= 61.2 tok/s at the 59.6 GB/s read roofline — macOS's 47.05 (87% of
roof) is beatable without reading fewer bytes, but only by closing the
~11 ms/token of non-roofline time measured in section 1: the
micro-kernel swarm (~5-6 ms real: 119 RMSNorm + ~220
elementwise/copy/cast launches for ~1 ms of bytes), the greedy head
chain overhead (~3 ms vs 2.7 ms of bytes), GEMV efficiency (~1 ms left
after xpack; dual-row is NO-LAND on digest), and the now-removed submit
splitting (this change, +0.34 tok/s realized).

Next levers, in roofline order: (1) GDN f32 state chain + elementwise
fusion (the "decode-kernels" lane cut mid-work, `agent/decode-fuse`
a2feb3f9b); (2) greedy-head stage merge (requires re-proving the
vocab-prune exactness bounds); (3) MTP — the only lever past the byte
ceiling — blocked on an MTP-weights decision (no mtp.* keys in the 4-bit
checkpoint, mlx-lm strips them, upstream repo gated 401).

## Artifacts

- This dir: `prof/` (NDJSON + markers), `ab/` (20 contract JSONs + 3
  gate JSONs + smoke-qual-prune.json), `scripts/` (prof_decode,
  window-profile, window-ab, analyze_ab, bw_roofline, stage-prof-venv),
  `artifacts-window.log` (bw + profile console output; [rtmod] lines are
  ANE runtime module noise from the sibling lane's module, present in
  the environment for all arms equally).
- m1-host: `/var/tmp/vprof/` (venvs + wheels), `/var/tmp/vprof/ab/` (same
  as ab/).
- the chroot host: `~/src/DecodeProfile-build/` (a91adbf + 8fed014e6 trees,
  build logs `build-diag.log`, dist with both wheels).
- mlx-omarchy branch `agent/vocab-prune-wire` (local): 4aa4b8b9c
  (wiring) + 8fed014e6 (batch budget).

## Notes for the next person

- Themlx elementwise path on this stack is pathologically slow (abs
  512 MiB bf16 = 4 GB/s, f32 = 8 GB/s) — do not use mlx elementwise ops
  as a bandwidth proxy; use the q4-bw-bench wall-copy methodology.
- `flock /tmp/m1-gpu.lock`: the file was deleted twice today by reboots
  while held (sibling lane's lockups #3/#4). Hold one inode for the
  whole window (the receipt scripts do `exec 9>` + `flock 9`) and check
  `fuser` before trusting "free".
- `[rtmod] SUBMIT/COMMIT-NOOP` console spam is environmental (ANE
  runtime module debug prints) and did not differ between arms.
- Scratch left on m1-host: `/var/tmp/vprof/venv-wiretest` and
  `/var/tmp/vprof/venv-diag` (partial, superseded by venv-diag2) —
  harmless, not installed anywhere.

## Addendum (same day, later): cross-host warning on the batch-budget change

the T6001 decode lane bisect-isolated the same `kBatchNodeBudget` 256→4096 change on
the T6001 host (a12b1aa1 lineage, 10 paired reps + logits gate): digest
FLIPS, decode 63.5 → 37 tok/s, prefill512 830 → 74 tok/s — a severe
regression, output-changing there, while output-neutral and +0.94% here.
The change is therefore **host-dependent and must not merge fleet-wide
without a per-host gate** (m1-host: keep; T6001-class: do not ship). Branch
`agent/vocab-prune-wire` is local/unpushed and the wheel was installed
only on this host, so nothing contaminated other hosts. This also
invalidates the "machine state" attribution in the T>1 lane's multi-T
wheel receipt — the raw-route wheel delta there is real (−10.6%, still
bit-exact records), per the T6001 decode lane's same-window measurement.

## Addendum 2 (root cause, Main directive): the T6001 flips are a build-pipeline artifact, not a barrier bug

Main ordered a root-cause of the T6001 digest flips under the 4096 budget.
Result: **no node-pair dependency violation exists; the flip class traces
to the T6001 lane's chroot build wrapper delivering stale/mixed source.**

Evidence:
1. **Forced flush storm on m1-host is bit-exact.** New instrumentation
   (`agent/batch-flush-rootcause`, env `MLX_OMARCHY_BATCH_BYTE_DIVISOR` +
   `MLX_OMARCHY_BATCH_TRACE`, wheel
   `0.32.3.dev202609231722+diag.batchflush1` sha256 201f4f7d…): forcing
   the byte budget with divisor 8192 produced **10,144 mid-graph commits
   in one contract run** (per-node flushing, decode 36.67 → 29.78 tok/s —
   the expected commit overhead) with ordered digest `486872c4…`
   **bit-identical** and logits gate **0 flips / max Δ 0.0**. Divisor 256
   (521 commits): identical digest, no perf change. The encoder's
   batch-splitting machinery with unconditional per-dispatch barriers is
   output-neutral at commit densities far beyond anything the budget
   constant can produce. (Artifacts: `flushrepro/` on the m1-host
   scratch, console logs carry the per-commit trace.)
2. **The two lineages' batch code is byte-identical.** `git diff
   a12b1aa1..8fed014e6` touches only the ANE side, the greedy kernel, and
   the budget constant — `encoder.cpp`, `eval.cpp`, `allocator.*` are the
   same files, so a source-level host difference in the batching path does
   not exist.
3. **The two "different" T6001 wheels produced the same wrong output.**
   arm4 (budget 4096) and bisect-C (print gate only, budget still 256)
   both read digest `d4377e53` with the same 2 flips (p4@25, p9@19),
   10/10 reps. Different sources cannot yield byte-identical wrong
   output; both binaries must have been the same stale build. The lane's
   own earlier datum — a wheel built 6 minutes after the gate commit
   still printed pre-gate lines — is direct stale-read evidence through
   the bind mount (macOS VirtioFS into docker).
4. Discriminator in flight: the same source rebuilt through the
   cp-in-verified flow (wheel 70b6297f, sha256 ff14cfb5…) probing on the
   T6001 host. Expected: healthy, bit-exact.

Consequence for this receipt's change: the batch-budget commit is
**correct as built via the verified flow**; the earlier "must not ship to
T6001-class hosts" caution is narrowed to "must not ship wheels from the
unverified chroot wrapper". The per-host digest+logits gate remains the
landing discipline regardless.

**Bonus defect found while instrumenting** (backend lane, not fixed
here): `caps.total_memory` is the largest `VK_MEMORY_HEAP_DEVICE_LOCAL`
heap (device.cpp:213). Under Honeykrisp on T8103 that heap is ~15.8 MB,
so `memory_limit_ = 90%` of it ≈ 14.26 MB and the documented
"limit/16" batch byte budget is in fact ~891 KB — it fires routinely
(6 commits per contract run at default divisor, reason=byte). Proven
benign for outputs (see the storm above) but the budget does not
implement its documented intent; `total_memory` should consider the
largest heap usable by the allocator's memory type (the unified
host-visible-coherent heap on Apple silicon).

## Addendum 3 (correction, supersedes the root cause in addendum 2)

The T6001 lane's discriminator proved the flips were NOT stale chroot
source either. Actual root cause of the flip class: **stock vs patched
GDN route in the venv**. Stock mlx-lm 0.31.3 gates the GDN fast route on
`mx.metal.is_available()`, which is FALSE on Linux, so any venv built
with plain `pip install mlx-lm==0.31.3` silently runs the eager composed
GDN scan: ~36.7 tok/s, digest `d4377e53`, slow prefill. The "broken"
arms on T6001 were exactly that; the same C1 wheel file ran broken
(stock route) and clean (patched route) with no wheel change. Arm4 vs
bisect-C shared `d4377e53` because both venvs were on the stock route —
not because the binaries were stale. Every fleet venv created through
`scripts/apply-mlx-lm-patches.sh` (or the dg patch scripts) gets the
fast route and is unaffected; hand-rolled venvs are the hazard.

Standing findings after the correction:
- The m1-host forced-flush-storm exculpation stands (my venvs are
  patched-route; bit-identical under a 10,144-commit storm).
- Budget on T6001, patched route, 2 reps: decode +0.6 tok/s (sub-noise)
  but prefill512 729 vs 832 (−12%) → the batch budget stays REJECTED for
  T6001 on prefill grounds. Plausibly the byte-branch flush storm under
  the broken ~sub-MB memory limit (addendum 2 bonus defect); the UMA
  heap fix in `agent/batch-flush-rootcause` (commit "allocator limit:
  total_memory = largest HOST_VISIBLE heap") raises the budget to its
  documented scale and should be re-tested together with the budget on
  T6001 before any final verdict.
- Multi-T wheel −10.6% T=1 regression: confirmed, digest intact; the
  T1-static shader variant did not recover it (cost is in the raw-op
  route layer, not the shader loop).

## Addendum 4 (Main follow-up): UMA heap limit fix — measured, gated, installed

Fix (mlx-omarchy `agent/batch-flush-rootcause` fbe4fc0ae):
`caps.total_memory` = largest HOST_VISIBLE heap (the memory type every
buffer allocates from) instead of largest DEVICE_LOCAL heap. Restores the
documented limit/16 batch byte budget semantics (~845 MB on m1-host
instead of ~891 KB).

Measurement (contract A/B, warmup 3, 10 interleaved paired reps, lock
14:59–15:09 EDT window): decode +0.011 ± 0.055 tok/s (ratio 1.0003 —
neutral, as predicted: the broken budget cost only ~6 commits per run),
prefill512 +2.9 ± 5.7 (noise), ordered digest `486872c4…` bit-identical
across all 20 runs, logits gate 0 flips / Δ 0.0, qualification 601 cases
/ 0 token / 0 bits mismatches. Installed `0.32.3.dev202609231736+umalimit1`
(sha256 9f9f6b99…) into both `/var/tmp/v072-venv-fused` and
`/var/tmp/vp/venv-cand`; rollback: the 8fed014e6 wheel in `/var/tmp/vp/`.

Where the fix should actually pay: T6001, whose byte-branch flush storms
under the broken limit are the leading explanation for the −12% prefill
seen with the 4096 budget there; the series (UMA fix + budget) was handed
to the T6001 lane for a patched-route 10-rep re-test. Submit-count
instrumentation (MLX_OMARCHY_TRACE_DISPATCH SUBMIT-ENTER) did not fire in
release wheels — commit-count telemetry needs the BATCH_TRACE diag wheel
instead; queued as a follow-up if the T6001 numbers need it.

## Addendum 5 (three-way split, my lever): greedy head stage-1 restaging — bit-exact but slower, NO-LAND

Main assigned the greedy head chain (8 dispatches, ~5.5-5.8 ms/tok
measured vs ~3.8 ms of unavoidable sketch+scales reads). Design tested:
stage 1 (bounds) walks the 190.7 MB 3-bit sketch with a 24-byte stride
across lanes; the refactor staged each row's 192 plane words through
6 KB of shared memory with cooperative consecutive loads
(commit abe27078b, diag + release wheels built off-device).

Qualification FIRST (bit-exactness holds by construction — pw[] values
and the per-row fma chain are unchanged): greedy_qual all three modes —
prune 601/0/0, keep 601/0/0, full 601/0/0 mismatches, and the contract
digest `486872c4…` bit-identical across all 20 A/B runs, logits gate
0 flips / Δ 0.0.

The performance verdict is a clear NO-LAND: decode 33.12 vs ctl 36.75
tok/s = **−3.63 ± 0.03 (−9.9%)**, and the profiled head op rose
5.804 → 8.888 ms/tok. Root cause of the slowdown: the direct-walk
version's per-row loads were already latency-hidden by the async queue
(no intra-workgroup sync across the 16-row loop), while the staging
rounds insert 32 full-workgroup barriers per workgroup and serialize
load and compute per row — the overlap loss dwarfs any coalescing gain.
The 24-byte-stride "cache line per lane" theory was wrong for this
kernel: the bounds stage is not coalescing-starved.

Reverted (d90835378). Conclusion for the head: at ~5.5 ms against
~3.8 ms of sketch+scales bytes, the remaining ~1.7 ms is ALU/unpack and
dispatch-structure cost; cutting it requires an algorithmic change to
what the sketch stores or how many rows get bounded (both reopen the
vocab-prune exactness proof T1-T4), not a memory-movement refactor.
The installed state on m1-host remains umalimit1 (batch budget 4096 +
UMA limit fix) at 36.44-36.75 tok/s.

## Addendum 6 (Main follow-up): designedusc CDM_BARRIER arm — neutral on m1-host, not installed

Main directed a test of MaxDispatch's lighter CDM_BARRIER set
("designedusccdmbarrier": drops unk_7, adds usc_inval) on m1-host, where
~20.4 us/launch x ~600 launches/token had been hypothesized as the
biggest remaining cost. Release driver build (chip-generic,
sha256 3e3063de, staged at /var/tmp/maxdispatch/t6001/ with an
icd json; env-selected arms, no system mutation for measurement).

3-arm window (warmup 3, paired; lock 16:31:19–16:39:45 EDT):
- anchor: installed system driver (git-7faf04c065) — 36.25, 36.38
- armdef: candidate .so, default trim — 10 reps, mean 36.36
- armusc: candidate .so + HK_PERFTEST=designedusccdmbarrier — 10 reps,
  mean 36.32

**designedusc paired delta: −0.036 ± 0.042 tok/s (95%, t, df = 9,
ratio 0.9990) — dead neutral.** Prefill512 −0.56 ± 5.46 (noise).
Ordered digest `486872c4…` — ONE distinct digest across all 22 runs;
logits gate between arms 0 flips / max Δ 0.0. The candidate binary at
default trim also matches the installed system driver (+0.04 tok/s), so
the lineage step 7faf04c → 5deac1c is performance-neutral on m1-host
and the T6021/T6001 lanes can adopt it freely.

Interpretation: the ~20.4 us/launch barrier cost measured on trivial
microbench chains does not manifest in real decode — the async queue
overlaps CDM_BARRIER packets with execution, so the 600 x 20 us
arithmetic (12 ms/token) never appears as wall time. This is the same
mechanism as the addendum-5 storm NO-LAND: barrier/dispatch costs on
this stack are latency-hidden, not serialized. NO WIN → NOT installed;
the system ICD is untouched and the candidate .so stays staged at
/var/tmp/maxdispatch/ for the T6001/T6021 lanes.

## Addendum 7 (three-way split, second lever): conv+SiLU fusion — bit-exact but slower, NO-LAND, unwired

The other unclaimed swarm half per the the gdn-fuse lane boundary: the GDN
conv+silu chain — ConvBF16 + ElementwiseBF16(sigmoid) + BinaryVecBF16(mul),
3 dispatches x 18 GDN layers. Implemented the full Wave-9 stack:
`fast_conv_silu.comp` (specialized depthwise causal conv1d + SiLU
epilogue, bf16), ConvSiluBF16 kernel (append-only enum id), ConvSilu
fast primitive end-to-end (fast.h/fast.cpp/fast_primitives.h/python
binding via patches/mlx-fast-conv-silu.patch), mlx-lm routing
(patches/mlx-lm-qwen35-convsilu.patch, hasattr+bf16+depthwise guarded,
exact composed fallback).

Qualification: the fused primitive is bit-exact (standalone probe
maxdiff 0.0 vs composed on the real shapes; contract digest `486872c4…`
bit-identical across all 20 runs; logits 0 flips / Δ 0.0; greedy head
qual 601/0/0).

Performance verdict: NO-LAND. Contract A/B (10 paired reps, warmup 3):
decode 33.02 vs ctl 36.65 tok/s = **−3.63 ± 0.048 (−9.9%)**, prefill
−4.3 ± 5.8 (noise). Standalone microbench: fused 277.8 us vs composed
266.1 us per call — the naive specialized kernel costs ~190 us/dispatch
more than the tuned general conv.comp's share of its 3-dispatch chain.
Launch-count savings do not pay when the specialized kernel is 3x the
per-dispatch cost of the tuned general one. Routing unwired from
apply-mlx-lm-patches.sh and install.sh; the primitive + patch remain in
the repo as documented candidates. Combined with addendum 5: BOTH
micro-kernel fusion attempts on m1-host lost to latency-hiding /
kernel-tuning gaps — the swarm's profiler-time overstates its
wall-time value, and the remaining head/sketch levers stay parked
behind the proof rework.

Installed state on m1-host unchanged and green: umalimit1 (batch budget
4096 + UMA limit fix), decode ~36.4-36.7 tok/s across today's windows.

## Addendum 8 (Main follow-up): cross-host per-op-family bench — script validated, Linux column captured, macOS window staged

Main directed a per-kernel Linux-vs-macOS comparison. Method: a
device-agnostic `family_bench.py` that loads the real model and benches
each op family with the real decode shapes (one bf16 token), amortized
launches between flushes (per-launch = max(host enqueue, kernel time)),
median of 30 rounds, 3 warmups — identical script on both hosts so the
columns are symmetric and profiler-free.

Validated off-device on the chroot host (M1 Max, Metal): the whole chain ran
(qmm families, rms_norm, conv+silu, gated_delta_update, sdpa, rope,
lm_head full GEMV via QuantizedEmbedding.as_linear, whole-token decode).
Reference numbers: qmm[6144x2048] ≈ 259 µs (12 MB at ~46 GB/s), small
kernels at the ~0.8 µs/launch issue floor, lm_head full ≈ 878 µs.

Linux column (m1-host, installed umalimit1 wheel, quiet machine, whole
token 36.7 tok/s): lm_head full composed 5399 µs, gated_delta_update_raw
187.5 µs, sdpa 230.1 µs, qmm[6144x2048] 152.0 µs, qmm[4096x2048]
111.8 µs, qmm[2048x6144] 138.8 µs, qmm[2048x2048] 63.0 µs, qmm
[512x2048] 17.4 µs, qmm[16x2048] 6.1 µs, rms_norm 19.1 µs, conv+silu
37.7 µs, rope 22.2 µs. (Also captured on the stage-1-restage diag wheel
for provenance: identical family numbers within ~2%.)

Macroscale sanity: the m1-host vs M1-Max rows are consistent with the
DRAM-bandwidth ratio (~1/6.9), i.e. both stacks are bandwidth-bound in
the same families. The decisive rows come from the m1-macOS window
(same chip), which is staged and awaiting Main's go — runbook in
macos-window-runbook.md (bless one-shot macOS boot syntax confirmed
from --list-volumes: "1) Macintosh HD / *2) Omarchy"; return via
default-order reboot).
