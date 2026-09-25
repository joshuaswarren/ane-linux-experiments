# 2026-09-24 — t6001/t6001-host (M1 Max) decode: one-token timeline, bottleneck attribution, and the closed-lever map

Lane: decode-profile (measure where one decode token's ~14 ms goes; attack the
dominant category). Host: t6001-host (T6001/G13C, Omarchy, kernel 7.1.6-1-1-ARCH).
Starting stack: serving venv `/var/tmp/v072-venv-fused`, wheel
`0.32.3.dev202609240802+04de5704` — `libmlx.so` sha256 `e0ad2548eacfdd3c…` =
exactly the `/var/tmp/ccut-wt/dist` 04de5704 build (tree 69801d05 lineage +
mode-1 scaled routing + GDN raw-route + conv-concat fold). Model
`SiddhJagani/Qwen3.8-2B-mlx-4Bit` (24 layers = 18 GDN + 6 full-attn, hidden
2048, vocab 248,320; weights 1,059,404,429 B; read set incl. lm_head ≈ 1067 MB).

**Verdict: MEASURED — decode is neither host-bound nor GPU-idle-bound; the wall
is GPU-side serial time = kernel stream (~8.7 ms/tok, dominated by the q4-GEMV
family at its measured 160 GB/s pattern ceiling) + a per-launch
driver-side CDM-barrier/serialization sink (~4.9 ms/tok) that every bit-exact
lever below it has failed to shave (barrier-bit bisection: all four designed
bits required; the fast configuration is bit-corrupt). NO INSTALL — no
implementable bit-exact win exists in this lane's reach; per-category closure
receipts + fresh numbers below. Service restored and verified with a real
completion.**

## 1. Fresh anchors (window 20260924T100306Z, GPU lock held, service stopped)

| leg | venv | decode | 3-pass digest |
|---|---|---:|---|
| ctl (installed) | v072-venv-fused | **73.80 tok/s** (13.55 ms/tok) | `bc519c03` ✓ |
| prof (diag wheel 04de5704, env OFF) | /dev/shm venv, routing files copied verbatim from ctl | 73.93 | `bc519c03` ✓ |
| prof profiled (env ON) | same | 28.98 (instrumented) | `486872c4` (expected timing perturbation) |

Diag build: `scripts/build-wheel.sh --diagnostics` at 04de5704 in a fresh
worktree (`/var/tmp/profdecode-wt`), wheel
`0.32.3.dev202609240958+diag.04de570` — same source commit as the installed
`libmlx.so` (hash-pinned above), only `MLX_OMARCHY_GPU_PROFILING=ON` added.
Instrument inertness: leg 2 = leg 1 within noise, digest identical.

## 2. One-token timeline (153 mid-run tokens, GPU timestamps, profiled stream)

`profile.jsonl` = 187,004 dispatches / 1,077 submissions / 2 joins /
374,008 barriers (2 per dispatch, **skipped = 0**). Decode cycle period
detected on-device: **513 dispatches/token exact** (post-fold census;
bitwall predicted 513). 2.97 submissions/token × ~171 dispatches (the 256-node
batch budget). Joins = 2 in the entire run → **there are no per-token host
joins**; the per-token argmax sync is absorbed in the submission pipeline.

| quantity | value |
|---|---|
| wall/token (real, unprofiled) | **13.55 ms** (73.80 tok/s) |
| wall/token (profiled) | 34.8 ms median (instrument serialization) |
| GPU busy/token (profiled) | 23.0 ms median — 66% of profiled wall |
| GPU busy/token (real, ÷ ~1.7 diag inflation) | **≈ 13.5 ms ≈ the entire real wall** |
| host record cost (Σ d.h, profiled) | 0.905 ms/tok |
| host submit cost (Σ s.dur, profiled) | 15.8 ms/tok over 2.97 subs (inflated) |
| idle structure (GPU clock) | 0.11 ms/tok at token boundary + 1.58 ms/tok between subs (inflated; real ≈ 2 × ~0.2 ms) |

Consistency check that names the bottleneck class: profiling inflates
per-dispatch HOST work ~2.5× and decode throughput scales 1:1 down with it
(73.9 → 28.98) — yet the identical host path sustained **102 tok/s** when the
uscstudy lane removed only the driver-side per-launch CDM barrier set
(68.24 → 102.85, bit-corrupt arm, receipt 93bb431). Conclusion: the host is
never binding; the wall = kernel stream + per-launch driver serialization.

## 3. Kernel composition (binding-range bytes; profiled µs; real ≈ ÷1.7)

| kernel | n/tok | µs/tok (prof) | share | MB/tok | grid gx (top) |
|---|---:|---:|---:|---:|---|
| QmmVecQ4MultiSubgroupBF16 | 90.7 | 5964 | 23.6% | 419 | 256/1536/260 |
| QmmVecQ4WordSubgroupBF16 | 17.9 | 2276 | 9.0% | 392 | 768/31040 |
| FastRmsNormBF16 | 76.6 | 2186 | 8.6% | 1.4 | **gx=1** (16.6k/27.8k), 16, 2 |
| GatedDeltaDecodeBF16 | 17.0 | 1971 | 7.8% | 0.5 | 16 |
| CastBF16F32 | 58.0 | 1403 | 5.5% | 3.5 | 8 |
| GatedDeltaPrefillBF16 | 0.9 | 1199 | 4.7% | 0.2 | 16 |
| FusedChainF32 | 35.9 | 1148 | 4.5% | 1.7 | 8 |
| FastNormGatedBF16 | 34.9 | 1137 | 4.5% | 1.0 | 16 |
| CopyGeneralBF16 | 38.5 | 1092 | 4.3% | 14.9 | 8/2 |
| QmmPrefillCoopmatM16BF16X32 | 3.1 | 991 | 3.9% | 8.2 | 64 |
| CastF32BF16 | 23.3 | 695 | 2.7% | 0.6 | 8 |
| LogSumExpBF16 | 0.9 | 635 | 2.5% | 1.0 | **gx=1**, p50 673 µs |
| MatmulF32 | 11.3 | 609 | 2.4% | 0.9 | 16/2/3 |
| FusedChainBF16 | 17.9 | 527 | 2.1% | 1.2 | 24 |

Total binding bytes 1146 MB/tok → effective 85 GB/s over the real wall vs
macOS 191.6 GB/s (179.47 tok/s) and the measured 241 GB/s read roof.

New on-device facts this lane adds:
1. **The swarm is single-core-by-grid, not launch-latency**: FastRmsNorm runs
   gx=1 (one workgroup, 60 launches/tok), LogSumExp over the 248,320-wide
   logits runs gx=1 at p50 673 µs, copies/casts run gx=2-8. The GPU's other
   ~30 cores idle behind the blanket barrier while they run.
2. **Prefill-shaped kernels execute inside decode**: QmmPrefillCoopmatM16
   (M=16 tile) 3.1/tok + GatedDeltaPrefillBF16 0.9/tok ≈ 4.2 ms/tok profiled
   (≈ 2.5 ms/tok real, ~18%) — quantifies the open "raw-route dispatch depth /
   multi-T wheel" defect on the current stack.
3. Cycle period 513/token exact; 2.97 subs/token; joins≈0 — submission/sync
   structure is NOT the gap anymore (the m1 2026-09-02 disease is cured).

## 4. Bottleneck decomposition (bit-exact floor, per token)

| component | ms/tok | evidence | lever status |
|---|---:|---|---|
| q4-GEMV weight streaming | ≈ 6.7 | 1067 MB at the in-model 160 GB/s pattern ceiling (occupancy receipt) | CLOSED — kernel levers exhausted; split-K refused (46346bb) |
| driver per-launch CDM-barrier sink | ≈ 4.9 | 68.24 → 102.85 tok/s with corrupt usc-only set (93bb431); ~4.6-5.1 µs/dispatch × 513 | CLOSED at bit level — all four designed bits required; fast arms corrupt (320/320 flips); GATED_BARRIERS=1 flat (parity-pkdeep: 63.8, "the driver-side per-launch sink is the coin", maxdispatch) |
| micro-swarm (norm/chain/cast/copy single-core kernels) | ≈ 2 | §3 grid geometry | mode-1 installed; mode-0 = 1-ULP shader wall (fix spec'd, perf-neutral even when exact); chain extension ≈ +2% |
| prefill-shaped kernels in decode | ≈ 2.5 prof | §3 fact 2 | OPEN DEFECT (raw-route dispatch depth) — root cause unknown after dedicated lane; not attacked here |
| host (record/submit/sync/print) | hidden | joins=2; corrupt arm held 102 tok/s through the same host path | no headroom — rtmod print gating and budget changes measured sub-noise (subfix §5) |

Sum ≈ 13.6 ms ✓ matches the measured 13.55 ms/token.

## 5. Why nothing was installed

Every lever with ≥5% headroom terminates in a measured dead end:
- **Dispatch-count reduction**: copycast/bitwall (18d2d72) − 36 dispatches/token
  = −0.034 ± 0.112 tok/s (parity). Confirmed again by my cycle census (513).
- **Barrier/wait structure**: uscstudy (93bb431) bit-bisected every designed
  CDM bit; each is individually required; every bit-exact arm ±0.2 tok/s of
  default; the +48.5% arm flips 320/320 tokens.
- **GEMV bandwidth**: split-K (46346bb) refused at every S; occupancy ceiling
  160 GB/s stands; lm_head already at ~roof.
- **Swarm fusion**: mode-1 installed; mode-0 blocked on a 1-ULP exp-lowering
  wall (fix queued in the bitwall receipt, §4) and is measured perf-neutral on
  T6001 even when exact.
- **Host-side** (syncs, submits, prints, budgets): host is not binding —
  proven by the 102 tok/s corrupt arm passing through the unchanged host path,
  and by joins=2 in 187k dispatches.

The next lever (outside this lane's reach, ≥20% class): **mesa-side
dependency-tracked per-launch sink** — make the driver's per-dispatch
CDM barrier processing conditional on actual buffer overlap (the MLX-level
GATED_BARRIERS tracker proves 39% of consecutive pairs are provably disjoint,
but the driver currently charges the sink per launch regardless). Secondary:
root-cause the prefill-shaped-kernel routing in decode (raw-route dispatch
depth; ~2.5 ms/tok profiled on the table). Tertiary: bit-exact norm-into-GEMV
prologue fold (reproduce the bf16 rounding in-register; ≈ +2%).

## 6. Install state / restore / hygiene

- **NOTHING INSTALLED.** Installed venv untouched (hash-pinned in §1);
  system ICD untouched; no reboots.
- Service `llm-inference.service` stopped for the single measurement window,
  restored by the window trap (`/health` `{"status":"ok"}` poll #2), and
  verified with a real completion: HTTP 200, qwen3.8-27b, content `"Hello"`,
  finish=stop, 30 completion tokens (2026-09-24 ~05:20 CDT).
- API key read via the documented `/etc/llm-inference/api-key` file; key never
  printed; file untouched.
- Lane artifacts (mine): `/var/tmp/profdecode-wt` (diag worktree + wheel,
  8.4 MB), `/var/tmp/profdecode-out/` (50 MB NDJSON + contract JSONs + window
  log), `/var/tmp/profdecode_timeline*.py`, `/var/tmp/profdecode_grids.py`,
  `/var/tmp/profdecode-{window,venv-prep}.sh`. tmpfs build dir removed.
- Infra note for the homelab lane: the root btrfs hit ENOSPC with 5 GB free —
  device 100% chunk-allocated (unallocated = 1 MiB, metadata 87%); a
  metadata balance cannot start in that state. I built in /dev/shm as the
  workaround. The fs needs a real cleanup/balance cycle from an unmounted or
  quieter state at some point.
