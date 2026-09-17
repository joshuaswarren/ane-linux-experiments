# 2026-09-17: QMM prefill ceiling — per-candidate attribution, the
# jwm1(+33%)/jw16(30%) short-prefill asymmetry, and two digest-clean
# schedule arms that fail the perf screen

Date: 2026-09-17. Lane: QmmPrefillCeiling. Hosts: jwm1-linux (Apple M1
G13G B1, 8 GPU cores) and jw16mbp1-linux (Apple M1 Max G13C C0, 32 GPU
cores), driver `mesa-honeykrisp-omarchy 26.3.0.devel.hkf96e090-2` on
jwm1 / `hk5deac1c-2` on jw16. Base: mlx-omarchy main `98e3e2b8`
(v0.6.6). Work branch: `agent/qmm-prefill-ceiling` @ `6f70d4fa`
(graft of the four QmmCoopBench data-path arms from
`wave/CoopmatTflopClose` @ `cb6510a6` + two new arms, below).

## Verdict (both hosts measured)

1. **The ~65% gap to nominal peak decomposes into three measured
   layers, and only one of them was ever reachable from shader source —
   and it is now exhausted.** At the dominant gate_up shape on jwm1
   (1053x896x9728): the shipped kernel sustains 1035.8 GFLOP/s; the
   driver's zero-traffic pure-MulAdd ceiling in the real dispatch
   geometry is 1425.4 (+37.6%); the shared-load+MMA ceiling (no staging
   writes, no barriers) is 748.3 — **28% BELOW the shipped kernel**.
   The shipped schedule already sits between the two driver ceilings,
   closer to the upper one; the 09-11 "staging costs 30%" reading was
   incomplete: the staging cadence is load-bearing for the
   coopMatLoad-from-shared path, not removable overhead on top of it.
2. **Two NEW digest-clean schedule arms (this lane) fail the perf
   screen**: arm 6 (software pipeline: loads for step s+1 issued before
   the matrix work of step s, one barrier per step, double-buffered
   staging) loses 17-93% everywhere; arm 5 (64-wide output tile) loses
   8-11% on the wide cells that dominate prefill. Both reproduce arm
   0's f16 output digest bit-exactly on all 12 cells on jwm1, so the
   deltas are pure schedule, not arithmetic.
3. **The short-prefill asymmetry is explained by a device-invariant
   fork floor against native die scaling.** At m=30 the fork's QMM
   dispatches stream each layer's weights exactly once at per-dispatch
   latency floors of 160-810 µs set by the serial k-chain at low
   workgroup counts (0.25-1.75 workgroups/core on jw16 for down, q/o,
   k/v — those dispatches run 0.98-1.09x the jwm1 time on a 4x die),
   not by FLOPs or host submission (measured: m=30 prefill pass is
   82-96% GPU-busy; qmm is 76% of it on both dies). Native Metal's
   m=30 prefill scales with the die (102 ms on M1 → 19.8 ms on M1
   Max, 5.15x) while the fork moves 1.17x (76.7 → 65.3 ms). The fork
   floor therefore beats native on the small die and loses 3.3x on
   the large one.
4. **Addressable-gap verdict**: ~27-38% kernel-side headroom exists on
   paper between the shipped kernel and the driver's zero-traffic
   coopmat ceiling, but eleven digest-preserving schedule/layout arms
   across three lanes (six layout arms 09-14, chunk staging 09-11, the
   driver unroll patch 09-11, and arms 5+6 this lane) all fail to
   reach it; the ceiling itself is a property of Honeykrisp's f32
   8x8x8 cooperative-matrix emulation (simd_matrix_fmadd32 + mandatory
   shared-memory operand round trip), not of the kernel. Reaching
   native's implied ~5-6.4 TFLOP/s on jw16 requires a different matrix
   lowering (f16 operands — moves digests — or the dead inline route),
   both out of bounds by standing rules. **The f32-coopmat prefill
   kernel is at its practical source-level ceiling.**

## Identity and provenance

- Worktree `~/src/mlx-omarchy-qmmceil`, branch `agent/qmm-prefill-ceiling`,
  base main `98e3e2b8`, lane commit `6f70d4fa`. `git merge-base
  --is-ancestor 63c1d3cf HEAD` FAILS (checked at worktree creation;
  never merged). The local `~/src/mlx-omarchy` checkout was not used.
- Wheel (jwm1 window):
  `mlx_omarchy-0.32.2.dev202609171930+diag.6f70d4fa-cp314-cp314-linux_aarch64.whl`
  (diagnostics build, `-DMLX_OMARCHY_GPU_PROFILING=ON`), venv
  `/var/tmp/qmmceil/venv` (copy of `/var/tmp/V064REL-venv`), loaded
  libmlx identity recorded from `/proc/self/maps` per stage:
  `identity.txt` / `identity-measure.txt` in this directory.
- Default-dispatch byte-identity: the edited `qmm_coopmat.comp`
  preprocesses to SPIR-V byte-identical to main's
  (glslang `sha256 7747c319fda1b5fa3350ef7610e1bfd19dc26e8d7e0c49c94ca7862c211db962`
  for both; the M16 twin is the same shader at `-DTILE_ROWS=16`). No
  env var set → shipped dispatch path unchanged; arms 1-6 exist only
  under `MLX_OMARCHY_QMM_COOP_BENCH`.
- Probe digests reproduce the 09-11/09-14 records bit-exactly (arm 0
  f16 digests `5179630cd4a7c3f9`, `3e79733f76ed9d37`,
  `2df9480de6e511ec`, `e9218e07c9c13e5e`, `6a31dc466db80a40`,
  `5c42552b5320472e`, `4e29e2dbdf33b57b`, `ecd08c8841ecd105` on jwm1),
  so this lane's binaries run the same arithmetic as the historical
  arms.
- Model: `Qwen2.5-0.5B-Instruct-4bit` (jwm1 local dir; jw16 HF
  snapshot `a5339a41…`), `MLX_DISABLE_COMPILE=1`, `HF_HUB_OFFLINE=1`.
- Locks: one bounded `flock -w 900 /tmp/m1-gpu.lock` hold per host
  window (jwm1 inode 35, jw16 inode 12); announced TAKE/RELEASE via
  hub; no lock stolen or unlinked; jw16 `llm-inference.service`
  stopped before the window and restarted + confirmed ACTIVE after.

## The arms (what was screened, and the digest result first)

All arms run the identical probe (`scripts-local/qmm_coop_bench_probe.py`,
mx.quantized_matmul at the four real Qwen2.5-0.5B Q4 shapes x m in
{30, 262, 1053}, 4 warmups + 30 timed, median, f16 output sha256 per
cell, one fresh process per arm). Digest gate: arms 5/6 must equal
arm 0 exactly per cell.

| arm | shader | schedule idea | digest vs arm 0 (jwm1, 12/12 cells) | perf |
| --- | --- | --- | --- | --- |
| 0 | qmm_coopmat.comp (shipped) | stage 16 k → barrier → MMA → barrier, per step | = | baseline |
| 3 | bench path 3 | coopMatLoad + MulAdd only, no staging writes, no barriers (shared-load ceiling) | n/a (ceiling arm) | see tables |
| 4 | bench path 4 | fragments loaded once, pure MulAdd (zero-traffic ceiling) | n/a (ceiling arm) | see tables |
| 5 | qmm_coopmat.comp `-DQMM_TILE_N=64` | 64-wide output tile: halves workgroups + x-restaging, 8 accumulator fragments/lane | **PASS 12/12** | **REJECTED** |
| 6 | qmm_coopmat_pipe.comp (new) | software pipeline: step s+1 loads issued before step s MMA, dequant+store after, ONE barrier/step, double-buffered 8 KiB staging | **PASS 12/12** | **REJECTED** |

## jwm1 results (8 cores, m=1053 ctx cells, GFLOP/s)

| shape | arm0 shipped | arm3 load+MMA | arm4 pure-MMA | arm5 wideN | arm6 pipe |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1053x896x9728 (gate/up) | 1035.8 | 748.3 | 1425.4 | 935.1 (-10.8%) | 565.9 (-83.1%) |
| 1053x4864x896 (down) | 981.8 | 822.1 | 2040.0 | 909.5 (-7.9%) | 509.3 (-92.8%) |
| 1053x896x896 (q/o) | 865.5 | 643.6 | 1184.8 | 800.4 (-8.1%) | 508.8 (-70.1%) |
| 1053x896x128 (k/v, M32-forced) | 296.3 | 366.2 | 495.3 | 460.5 (+35.7%) | 247.8 (-19.6%) |

- The k/v cell is the only arm-5 win (+35.7% over the M32-forced arm
  0) — and production already routes that cell to the M16 twin
  (measured +22.4% there, receipts/2026-09-14-qmm-occupancy-tilem);
  the residual vs arm 5 is worth ~0.26% of the ctx prefill pass. Not
  landable.
- Attribution at gate_up: shipped/arm4 = 72.7% (27.3% of kernel time
  is the gap to the zero-traffic ceiling); shipped/arm3 = 138% (the
  shared-load path alone is 28% slower than the shipped kernel — the
  stage-compute cadence fills latency the bare load loop exposes).
- arm4 vs nominal: 1425.4 / 2654 GFLOP/s = 53.7% at gate_up; the
  down_proj geometry reaches 2040 = 76.9%; the flat pipe (independent
  chains, no geometry) is 2148 = 81% (2026-09-11-fma-ceiling).

## Short prefill, m=30: where the fork's floor comes from (jwm1)

Phase profile (`MLX_OMARCHY_GPU_PROFILE`, prefill + 2 decode steps,
`MESA_SHADER_CACHE_DISABLE=true`; GPU-busy figures are not affected by
the host-side compile stall):

- True prefill pass (565 dispatches, submissions 1-3): **GPU busy
  ≈ 73.3 ms** of the clean-run 76.7 ms short-prefill wall (95.6% busy)
  — the m=30 prefill is GPU-bound, not host/submission-bound.
- QMM inside the pass: **55.5 ms = 75.7% of prefill busy** (M16 twin
  117 dispatches 34.36 ms + M32 46 dispatches 21.16 ms), same dominant
  share as at m=1053.
- Per-dispatch floors at m=30 (census, exact shapes recovered from
  binding ranges): down 807.8 µs, gate/up 459.9 µs, q/o 175.4 µs, k/v
  160.7 µs — vs 2311.9-486.8 µs at m=1053 on 32-core jw16 and
  8578.9-423.8 µs on jwm1. Per-workgroup service time inflates 6.6x
  from m=1053 to m=30 (gate: 3.69 → 24.2 µs/wave on the same shape):
  at m=30 each dispatch has 8-152 workgroups (1-19 waves on 8 cores)
  and streams its weights exactly once (no m-tile reuse), so the
  serial k-chain (56 barrier-separated steps per workgroup) runs
  latency-exposed. Rates: 0.27-0.57 TFLOP/s-equivalent at m=30 vs
  1.03 at m=1053 — 10-20% of the same kernel's saturation rate, and
  4.7 GB/s effective weight streaming vs 68 GB/s DRAM: a parallelism/
  latency floor, not bandwidth, not FLOPs, not the host.

## The asymmetry (jwm1 +33% vs jw16 30%, short prefill)

- Fork m=30 prefill wall: jwm1 76.7 ms (390.8 tok/s) vs jw16 65.3 ms
  (459.7 tok/s) — only 1.17x apart on dies with 4x the FLOPs and 6x
  the DRAM bandwidth, because ~76% of the pass is the latency-floored
  QMM weight-stream above, which barely improves with more cores when
  each dispatch has 8-152 workgroups (k/v: 8 workgroups = 0.25/core on
  jw16 — the extra 24 cores are idle while each workgroup's k-chain
  runs serially).
- Native Metal m=30 prefill: 102 ms (M1) vs 19.8 ms (M1 Max) — native
  scales with the die.
- Therefore: on the M1 the fork's device-invariant ~77 ms floor beats
  native's 102 ms (+33%); on the M1 Max the same class of floor loses
  to 19.8 ms (30.3% of native). The asymmetry is not occupancy of the
  coopmat kernel at saturation (that regime is m=1053, where the fork
  tracks per-core efficiency across both dies); it is the m=30
  low-parallelism weight-streaming floor, which is fork-invariant and
  die-scaling in native Metal. jw16's own profile (below) confirms the
  floor's device-invariance.

## jw16 results (32 cores)

Wheel `mlx_omarchy-0.32.2.dev202609171941+diag.6f70d4fa` (diagnostics),
venv `/var/tmp/qmmceil/venv`, libmlx sha256 `83d20eefad8033eefb2b323c4de74124b50e306f917ed57ad69700d73a29f6f7`
(jwm1 wheel: `…1930+diag.6f70d4fa`, libmlx `78a1a5f130516834ad6f556210f8dc3b3160967e417c8a3db90451bc30cf9a98`;
each measurement ran on that host's fresh private venv — the only
libmlx resolvable to it — with `HF_HUB_OFFLINE=1`, no
`LD_LIBRARY_PATH`/`VK_*` overrides). llm-inference stopped before,
restarted and confirmed ACTIVE after.

### Probe (m=1053, GFLOP/s; digests bit-identical to arm 0 on 12/12 cells for arms 5/6)

| shape | arm0 shipped | arm3 load+MMA | arm4 pure-MMA | shipped/arm4 | arm5 wideN | arm6 pipe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1053x896x9728 (gate+up fused) | 3702.7 | 2804.5 | 4104.0 | **90.2%** | 3235.7 (-14.4%) | 1916.2 (-93.2%) |
| 1053x4864x896 (down) | 3362.6 | 2586.9 | 5172.1 | **65.0%** | 2688.3 (-24.9%) | 1499.6 (-124.2%) |
| 1053x896x896 (q/o) | 1532.1 | 1244.0 | 1687.7 | **90.8%** | 1316.3 (-16.4%) | 917.3 (-67.0%) |
| 1053x896x128 (k/v, M32-forced) | 559.0 | 328.6 | 597.8 | **93.5%** | 371.4 (-50.5%) | 325.1 (-72.0%) |

- arm5 is REJECTED on jw16 everywhere, including the k/v cell where it
  won on jwm1 (+35.7% there): at jw16's 4.1-wg/core the wider tile
  halves the grid the starving part cannot spare. Production routes
  this cell to the M16 twin anyway (1.42 TFLOP/s measured in-graph —
  ABOVE the M32-forced arm4 ceiling of 0.598, because M16 doubles the
  grid; the M32 arm4 number under-references that cell's ceiling).
- arm6 (pipeline) is REJECTED decisively on both hosts: the
  one-barrier loads-early schedule loses 26-124% across all cells. The
  shipped two-barrier cadence is what the driver's compiler and
  co-scheduling actually exploit.
- arm3 (shared-load+MMA ceiling) is BELOW the shipped kernel on every
  large cell on BOTH hosts (-19..-70%): reproduces and strengthens the
  09-11 paradox on the current driver.

### In-graph census (phase profiles, m=1053 ctx leg)

`QmmPrefillCoopmatF16` 115 wide-shape dispatches 184.613 ms = 3.852
TFLOP/s (3.98 / 3.76 / 3.48 across gate/up, down, q/o) + `M16F16` 48
k/v dispatches 8.156 ms = 1.42 TFLOP/s → **722.67 GFLOP in 192.77 ms =
3.749 TFLOP/s aggregate** (the "3.751" bound), 70.4% of the 273.9 ms
clean prefill wall and ~76% of prefill GPU busy.

### Short prefill, m=30 (the asymmetry measured on the fork side)

Prefill-window busy 70.265 ms minus two in-window decode steps
(2 × 8.408 ms busy) → **true prefill-pass busy ≈ 53.4 ms** of the
clean 65.3 ms wall (82% busy). QMM (all 163 dispatches route to the
M16 twin at m=30 on this die): **40.861 ms = 76.5% of pass busy.**
Per-dispatch floors by shape (jwm1 → jw16):

| shape | wg (jw16, /core) | jwm1 mean | jw16 mean | die speedup |
| --- | --- | ---: | ---: | ---: |
| down 896x4864 | 56 (1.75) | 807.8 µs | 742.3 µs | **1.09x** |
| q/o 896x896 | 56 (1.75) | 175.4 µs | 166.1 µs | **1.06x** |
| k/v 128x896 | 8 (0.25) | 160.7 µs | 163.8 µs | **0.98x** |
| gate/up 4864x896 | 304 (9.5) | 459.9 µs | 180.2 µs | 2.55x |

At m=30 each dispatch has 8-304 workgroups; where that is below ~10
per core (down, q/o, k/v) the dispatch time is the per-workgroup serial
k-chain (56 barrier-separated steps streaming that dispatch's weight
slice exactly once) and the extra 24 cores buy NOTHING (0.98-1.09x).
Only gate/up, with 304 workgroups, scales (2.55x). That is the fork's
device-invariant floor: jwm1 qmm-at-m=30 = 55.5 ms, jw16 = 40.9 ms —
1.36x apart on a 4x-FLOP/6x-bandwidth die change.

## The asymmetry, closed

| short-prefill leg (30 tok) | jwm1 (M1) | jw16 (M1 Max) | die scaling |
| --- | ---: | ---: | ---: |
| fork Linux wall | 76.7 ms (390.8 tok/s) | 65.3 ms (459.7 tok/s) | **1.17x** |
| fork qmm busy in pass | 55.5 ms | 40.9 ms | 1.36x |
| native macOS Metal wall | 102 ms (294.1 tok/s) | 19.8 ms (1517.6 tok/s) | **5.15x** |

Native Metal's m=30 prefill scales with the die; the fork's is pinned
by the low-parallelism weight-streaming floor above (plus ~12 ms of
absolute intra-submission gap cost at jw16's dispatch cadence — the
same absolute ~12-24 µs/dispatch gaps both dies, worth 4.6% of the
Max's ctx leg and 3x that at m=30). Consequence: on the M1 the fork's
77 ms floor beats native's 102 ms (+33%); on the M1 Max the same floor
class loses to 19.8 ms (30.3% of native). The asymmetry is a property
of what dominates the leg on each platform — latency-floored qmm
dispatch streams for the fork vs die-scaling native kernels — not of
occupancy at saturation (ctx leg) or of dispatch counts (identical
graphs, bit-identical per-kernel counts across dies, 09-14 receipt).

## Ceiling verdict (addressable-gap arithmetic)

Gap chain at the dominant gate_up cell, jwm1 measured multipliers
(each step independently measured, this lane unless noted):

- shipped 1035.8 → arm4 zero-traffic coopmat ceiling 1425.4
  (**×1.376** — 11 digest-preserving schedule/layout restructures
  across three lanes have bought 0% of this: six layout arms 09-14,
  chunk staging 09-11, driver unroll 09-11, wide-N + pipeline this
  lane);
- → flat coopmat pipe (4 chains, no geometry) 2148 (**×1.507**,
  09-11-fma-ceiling) — the real-grid penalty of 5016-workgroup
  scheduling;
- → flat scalar FMA 2302.6 (**×1.072**) — the coopmat-vs-scalar issue
  gap;
- → nominal spec 2617 (**×1.136**) — sustained clock ~1.13 vs 1.296
  GHz (clocks unmeasurable on Asahi; implied by the scalar ceiling).

Log-share of the total ×2.53 gap: kernel schedule 34% (measured
unreachable by source), in-geometry pipeline 44%, coopmat-vs-scalar
7.5%, clock 14%. On jw16 the schedule share collapses to **~10%**
(shipped/arm4 = 90.2% at gate_up; 65% at down, which is 29% of qmm
time — the only cell with paper headroom left), i.e. **~90% of the Max's
to-nominal gap already lives in the driver's f32 8x8x8 cooperative-
matrix emulation and the part's clock, not in the kernel's schedule.**
The emulation ceiling itself (arm4) reaches only 38.7-48.7% of nominal
at the wide cells with ZERO operand traffic; raising it requires a
different matrix lowering (f16 operands — moves digests — or the
structurally dead inline-coopmat route), both excluded by standing
rules. **Verdict: the f32-coopmat prefill kernel is at its practical
source-level ceiling; the addressable-by-this-lane share of the ~65%
gap is ~0% realized (16% paper at the down cell against 11 failed
arms), and the rest is driver emulation + silicon.**

## Land discipline

- No runtime source change is landed. `overlay/` on
  `agent/qmm-prefill-ceiling` carries ONLY bench arms behind
  `MLX_OMARCHY_QMM_COOP_BENCH` (default 0 = shipped dispatch,
  byte-identical default SPIR-V, digest-neutral by construction and
  verified). Nothing merged to main; `63c1d3cf` not merged.
- e2e digest pins for the landed state (no change): governed by the
  v0.6.6 published receipts (`7fd25a869ff21678` / `7da83f06ec9f001d`).
  No perf change was shipped, so no new pin run is required by the
  land rule; the probe-level digest equality above is the screen
  evidence for the rejected arms.

## Artifacts (this directory)

- `jwm1/`, `jw16/`: per-host windows — `profile-{short,ctx}.jsonl`
  (GPU event streams), `markers-{short,ctx}.jsonl` (host phase
  markers), `probe-arm{0,3,4,5,6}.jsonl` (per-cell medians + f16
  digests; `.err` = stderr), `identity*.txt`, `wheel.txt`/`wheel.sha256`,
  `lock-take.txt`, `build-diag.log`, `gen-{short,ctx}.log`,
  `service-restored.txt` (jw16).
- Analyzer: `scripts/profile_analyze.py`, `scripts-local/shape_census.py`,
  `scripts-local/qmmceil_summarize.py` (mlx-omarchy worktree branch).
- libmlx identity (measured directly on the hosts; the identity.txt
  capture in-window recorded the mlx version only — the sha256 lines
  were re-measured post-window from the same private venv each run
  used): jwm1 `78a1a5f130516834ad6f556210f8dc3b3160967e417c8a3db90451bc30cf9a98`,
  jw16 `83d20eefad8033eefb2b323c4de74124b50e306f917ed57ad69700d73a29f6f7`
  (`/var/tmp/qmmceil/venv/lib/python3.14/site-packages/mlx/lib/libmlx.so`,
  the only libmlx resolvable from those venvs; no `LD_LIBRARY_PATH`).
