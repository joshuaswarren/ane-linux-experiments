# jw16 GPU parity after two-pass — baseline, attribution, lever verdict, Mesa-next (2026-09-17)

Lane: GpuParityJw16. Assignment: measure current main (two-pass in) vs native on
jw16 (T6001 / M1 Max, Honeykrisp), attribute the remaining decode/prefill holes,
attempt the highest-share non-dead lever or name the Mesa patch that must exist.
jwm1 untouched (macOS). One flock window per run, lock inode 12, never stolen.

## Baseline on main-with-two-pass (fb649d8d)

- Tree: `joshuaswarren/mlx-omarchy` main `fb649d8d` (merge `23fc9a9a` of
  `283aa076` two-pass asserted ancestor); venv `/var/tmp/V064REL-venv`
  (`0.32.2.dev202609172230+fb649d8`), loaded `libmlx.so` sha256
  `e9e709f38331ff10` (pinned fatal on every run).
- Harness: `bench_decode.py` `f5062d88f34b0845` +
  `bench_matrix.json` `df8eb9f3ed8418260`, fresh subprocess per leg, 3
  interleaved rounds with rotating order, `MLX_DISABLE_COMPILE=1
  HF_HUB_OFFLINE=1`, local snapshot `/var/tmp/jw16gap-model` (the documented
  offline-revision hazard).
- Digests fatal and exact on all rounds: short `7fd25a869ff21678`, ctx1024
  `7da83f06ec9f001d`.

| leg | N | decode tok/s (median) | % native | prefill tok/s | % native |
|---|---:|---:|---:|---:|---:|
| short | 30 | **191.40** (5.2246 ms/tok) | **66.7%** of 286.96 | **459.81** | **30.3%** of 1517.55 |
| ctx256 | 414 | 179.52 | 63.2%* | 3168.33 | — |
| ctx512 | 653 | 151.14 | — | 3237.71 | — |
| ctx1024 | 1053 | **149.32** (6.6972 ms/tok) | **52.6%** of 283.79 | **3863.11** | **48.0%** of 8048.42 |

\* native only pinned for short and ctx1024 legs.

Decode rounds, ctx1024: [163.2, 148.6, 149.3] — sits inside the two-pass fix-arm
window distribution from the DecodeTwoPass lane (fix ctx1024 medians 165.3 /
150.5 / 145.7 across its three windows vs base 149.8 / 132.8 / 138.1). The
best-window two-pass number remains **165.3 tok/s = 58.2% of native** (+10.3%
over base in the same window); the multi-window fair band for two-pass main is
**146–165 tok/s (51–58% of native)**. Short is flat vs pre-two-pass (190.95 →
191.40) as expected: two-pass engages only at k>=1024.
Linear fit over the four leg medians: **t0 = 5.173 ms, slope 1.589 µs/KV-token**.

## Remaining-gap table (ground truth)

| hole | ours | native | gap | share / status |
|---|---:|---:|---:|---|
| decode fixed per-token overhead (barrier sink + dispatch chain) | t0 5.17 ms | ~3.49 ms | **+1.68 ms/tok** | **~65%** of the best-window ctx gap (2.53 ms); micro dependent-chain **29.1 µs/launch** (prior 27.7, same band), stream 31.2 GB/s and fp16 2048² matmul 1.77 TFLOPS unchanged |
| residual KV-walk excess (k<1024 one-pass + two-pass residual) | slope 1.589 µs/tok | ~0.04 µs/tok | ~0.9 ms at ctx1053 (best window) | ~35%; two-pass ate the named slice; walk insensitive to restructuring (Jw16Gap receipt) |
| short prefill (m=30) | 459.8 tok/s | 1517.6 | 30.3% | die-scaling/latency floor of the weight stream (fork 1.17× die scale vs Metal 5.15×); unchanged by two-pass |
| ctx prefill | 3863 tok/s | 8048 | 48.0% | QMM at 90.2% of Honeykrisp's own coopmat ceiling (QMM receipt); unchanged by two-pass |

Micro on main (this lane, `/var/tmp/GpuParityPostTP/micro.json`):
chain 29.144 µs/launch, stream 31.2 GB/s, matmul 9.722 ms / 1.77 TFLOPS.

## Lever verdict — every named family is closed

1. **Two-pass decode**: shipped on main (`23fc9a9a`); this baseline measured
   it in. Done.
2. **KV-walk restructuring**: Jw16Gap `266813b0` screened +2.46% ctx, inside
   wander; walk structural (k/32 serial depth). Dead.
3. **G13X designed-bit barrier trim (both legs)**: the packaged 12-round
   interleaved A/B in `/var/tmp/TermAJW16/deploy.log` (hkd71c94e-2 vs old
   package, digests exact) shows the real coupling: short 190.7→215.5 (+13%),
   ctx1024 ~148→~135 (−3 to −8%). Not landable. The follow-up knob sweep
   (`sweep.ndjson`, supersets/subsets of designed {4,5,6,8}) found no mask
   better than noise — but note **its driver never exports a mask env var**
   (`one()` logs the mask, sets nothing), so its per-mask deltas are single-round
   window noise and must not be cited as lever evidence either way; the packaged
   A/B is the binding evidence. Dead.
4. **QMM prefill arms, inline coopmat, load hoisting**: dead per
   2026-09-17 qmm-prefill-ceiling and decode-gap receipts.

Honest result, with numbers: **remaining decode is the coupled G13X fixed
per-launch sink (~65% of the best-window hole) plus the structural KV walk
(~35%); remaining prefill is the m=30 latency-floored weight stream (short) and
the driver coopmat ceiling (ctx).** No bit-mask, tile-shape, or load-order lever
reaches any of them.

## The next Mesa patch that must exist

**G13X per-dispatch cost amortization in Honeykrisp command-stream emission**
(`src/asahi/vulkan/`, decode dispatch chain): the measured dependent-chain cost
is 29.1 µs/launch on G13X (20.2 on G13G; native pays ~0). With ~201 dependent
dispatches/token that is the whole +1.68 ms fixed overhead. The patch is
structural, not a barrier-bit set: elide or batch the per-dispatch
CDM_BARRIER drain for same-queue dependent compute chains whose dependency is
already carried by the firmware/scheduler ordering (barrier elision keyed on
the existing `hk_cs` dependency tracking), and/or coalesce MLX's per-op
dispatch sequence into amortized submits. A real win here moves decode toward
native on BOTH legs and also attacks the m=30 short-prefill floor (same
per-launch cost × the prefill dispatch chain). That is a Mesa engineering
project (cs-emission change + digest screens + multi-window battery), not a
lane-sized shader arm — named, not attempted, per the assignment's outcome 4.

## Hardware safety / coordination

- jw16 only; two flock windows (window #1 aborted pre-measurement: driver
  script had not copied `caps_sim_guard.py` into the lane scripts dir — fixed
  from main, digests unchanged). Lock inode 12 held via `flock -w 900`, never
  stolen/unlinked. `llm-inference.service` stopped before and started after
  each window; **post-state CONFIRMED `active`** (`systemctl is-active` after
  window #2). ≥3 GiB /tmp asserted per window. jwm1 never touched.
- Mesa installed system package untouched this lane (evidence-only reads of
  TermAJW16 artifacts).

## Artifacts

- jw16: `/var/tmp/GpuParityPostTP/{gp_ladder.py, ladder.json, ladder.stdout,
  micro.json, micro.stdout, window.sh, service.txt, lock.txt, exit.txt}`;
  scripts `scripts/{bench_decode.py f5062d88…, bench_matrix.json df8eb9f3…,
  caps_sim_guard.py, mlx_provenance.py}`.
- TermAJW16 packaged A/B: `/var/tmp/TermAJW16/{deploy.log, sweep.ndjson,
  sweep.log}`.
- This repo: `receipts/2026-09-17-gpu-parity-jw16-post-twopass.md`.
