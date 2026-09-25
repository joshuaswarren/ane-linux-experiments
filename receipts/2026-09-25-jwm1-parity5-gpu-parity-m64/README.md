# 2026-09-25 — jwm1 (T8103) GPU Qwen parity lane: dispatch floor, reduction flavor, TTFT decomposition, coopmat M64 prefill tile (Jwm1Parity5)

Owner: Jwm1Parity5. Host: jwm1-linux (T8103 M1, MacBookPro13-x), stack
mlx-omarchy main `ecda0fa33`, venv `/var/tmp/jwm1-parity3-venv`
(wheel `+af73787`), mlx-lm 0.31.3, GDN fast+raw + greedy-prune patches,
`MLX_DISABLE_COMPILE=1`, honeykrisp fork ICD
`libvulkan_asahi.so.7faf04c` (joshuaswarren/mesa-1 `honeykrisp-omarchy`).
Prior lanes: `2026-09-25-jwm1-parity3-main-battery`,
`2026-09-25-jwm1-parity4-falsifications-and-ane-regression`.

## 0. Baseline control (frozen contract, 3 warmup + 10 reps, n=100, quiet box)

Rerun this session, production stack, before any change:

| metric | this control | task row | macOS bar | ratio |
| --- | ---: | ---: | ---: | ---: |
| decode tok/s (median) | 37.47 | 37.4 | 47.05 | 0.796x |
| ttft tok/s (median) | 50.26 | 50 | 99.12 | 0.507x |
| pure prefill tok/s (512) | 235.34 | 217.6 | 343.73 | 0.685x |
| e2e s (median, 32 tok) | 1.0842 | 1.09 | 0.7898 | 0.728x |

10-pass pin: **`dbf704971617fdfc` HOLDS** (exact control established).
Control JSON: `/var/tmp/jwm1-parity5/qwen/contract-baseline.json`.

## 1. Dispatch floor A/B (main pattern, stamp 20260925T131458Z)

`tools/dispatch-floor-bench` @ `ce91f5b`, default ICD, two legs (a/b),
jwm1 G13G B1, ts_period 1.0 ns. Per-dispatch medians:

| case | host record us | GPU span us |
| --- | ---: | ---: |
| empty (no kernel) 1..144 wg | 0.12 | 0.13 |
| trivial dispatch (no barrier) | ~2.05 | **0.062** |
| full barrier per dispatch | ~2.21 | 3.17 |
| **MLX production pre+post pair** | ~3.70 | **3.10** |
| rebind / push-const / pipe-switch | 2.1-2.4 | 0.06 |

Reading: the per-dispatch GPU floor is **barrier-edge dominated** (~3.1 us
per dependent dispatch), not record- or binding-dominated; the bare
dispatch execution itself is 0.06 us. 507 dispatches/tok put the
barrier-edge cost at ~1.6 ms/tok. Both legs agree within 0.1 us.

## 2. q4 GEMV reduction flavor: subgroupAdd vs shared tree — WASH

`tools/subgroup-bench` @ origin/main (bit-identical source at `ce91f5b`),
byte-identical kernels differing only in the reduction body, GPU
timestamps, 65536 groups:

- GPU: subgroup 36458 ns vs tree 36292 ns → **ratio_gpu 1.005**.
- Device: `Apple M1 (G13G B1)`, subgroupSize 32, ARITHMETIC supported.
- Equivalence: both flavors sit within 1.9e-6 of the CPU f32 reference;
  they differ from each other at 2.4e-7 (last-ulp rounding).

Verdict: the "float subgroupAdd lowers to a software shuffle chain"
comment claim is FALSE on this driver, but subgroup is not faster either.
The production kernels already dispatch the Subgroup flavor (kernel names
`QmmVecQ4*SubgroupBF16`), and per `receipts/2026-09-09-q4-gemv-order` the
two flavors are bit-identical at the shipped pairing. **Reduction-flavor
lever closed: no perf to gain.**

## 3. TTFT decomposition: a ~196 ms fixed per-prompt cost

Contract prompts are 11-18 tokens (median 13). Linear fit over the 100
control records: **ttft = 195.9 ms fixed + 4.81 ms/token**. Phase probe
(fresh cache per rep): cache_make 0.03 ms, iterator 0.12 ms, everything
inside the first `next()` (prefill + first step), `mx.eval` 0.0 (lazy).
The fixed cost repeats per fresh cache (median over 30 reps includes late
reps), so it is not one-time pipeline creation.

macOS bar for the same 13-token ttft is ~131 ms, so the Linux fixed cost
(~196 ms) plus per-token prefill (4.81 ms/tok vs ~2.5 ms/tok macOS-equiv)
are both live TTFT levers.

## 4. Prefill profile: compute-bound qmm coopmat at the tile limit

- Pure prefill-512 (clean): 233.66-235.34 tok/s across ctl venvs.
- The fork's coopmat qmm route measured 1034.6 GFLOP/s at the dominant
  gate_up cell (`receipts/2026-09-12-prefill-fma-qualify`); prefill-512
  needs ~2.1 TFLOP → 2.05 s predicted vs 2.18-2.19 s observed: the cell
  is compute-bound on the coopmat pipe, consistent with the roofline.
- macOS Metal reaches 1.41 TFLOP/s on the same shapes (343.73 tok/s).
- Kernel structure (`shaders/qmm_coopmat.comp`): per (m-tile, n-tile) the
  full weight panel is re-staged and re-dequanted per k-step; at M=512 /
  TILE_M=32 the packed word load + 8 dequant FMAs per lane run **16x**
  per weight byte.

## 5. Lever: TILE_ROWS=64 coopmat variant (agent/jwm1-parity5-coopmat-m64)

Change (5 files, +35/-1, commit `9b250d7` pushed):
- `shaders/qmm_coopmat.comp`: accept `TILE_ROWS=64` (`SUBGROUP_ROW_BLOCKS=4`).
  Drain loop and guards are already generic in `SUBGROUP_ROW_BLOCKS`.
- CMake: `qmm_coopmat_m64_{f16,bf16,x32}` variants.
- `compute.h`/`compute.cpp`: append-only kernel ids (profile ids stable).
- `primitives.cpp`: `coopmat_tile_rows` now returns the widest tile (64 ->
  32 -> 16) whose grid still fills cores*workgroups_per_core.

Bit-exactness argument: per-output k chain unchanged (CHUNK_K=64,
STEP_K=16, same coopMatMulAdd sequence), only the m/n work partition
moves; rows past matrix_m are clamped on load and guarded on store as
before. Gates below verify 0 flips + pin identity.

### Results

Gates ran 2026-09-25 on the m64 wheel (`dev202609251754+4c09f1f`,
sha256 `a4602e87...`), 10x interleaved r1 contracts then the 10-pass pin
contract (raw: `/var/tmp/jwm1-parity5/gate/contract-ctl.json`,
`contract-cand-m64-r1..10.json`, `contract-cand-p10.json`):

- Bit-exactness: all interleaved contracts PASS and the 10-pass digest
  pin **`dbf704971617fdfc` HOLDS** on the m64 stack (0 flips, pin
  identity as argued).
- Paired decode A/B: delta **-0.031 +/- 0.042 tok/s** (ratio 0.9992, CI
  not positive) — no decode gain.
- Pure prefill-512 A/B: cand 221.81 vs ctl 235.34 tok/s on the contract
  stack; clean re-pair cand 225.7 vs ctl 240.6 — no prefill gain.

Verdict: **FALSIFIED for perf, exactness PROVEN**. The weight-restage
hypothesis of section 4 is falsified on G13G: the TILE_ROWS=64 tile's
register/occupancy cost offsets the staging saving. NOT LANDED; branch
`agent/jwm1-parity5-coopmat-m64` @ `4c09f1f` stays pushed and unmerged as
the falsification record (see mlx-omarchy
`receipts/2026-09-25-qmm-coopmat-m64.md`).

## 6. Window log (jwm1 ownership)

- Baseline contract 10:04-10:06, floor A/B re-read 10:0x, subgroup-bench
  10:0x, family bench + profiles 10:16-10:18, ttft probes 10:2x-10:3x.
- Serialized peer windows honored: AneKillCleanup 10:2x (kill-race x10
  PASS, batteries green, **engine exec 141.5 ms restored** by module
  686ccd6), AneClockM1 read-only PMU probes (genpd state, 0x23b110000
  reads) 10:1x-10:4x, Main-ordered grouped macOS window from ~10:4x.
- Jwm1Parity6 continuation 13:34-13:37: Parakeet golden re-run under the
  armed 600 s-per-rep watchdog — 3/3 reps PASS bit-exact on installed
  a9a5f60; hang did not reproduce
  (`receipts/2026-09-25-jwm1-parakeet-golden-rerun`).

## 7. Final verdict table

| cell | linux | macOS | ratio | pass bar | verdict |
| --- | ---: | ---: | ---: | --- | --- |
| GPU decode tok/s (median) | 37.47 | 47.05 | 0.796x | >= 1.00x | FAIL |
| GPU ttft tok/s (median) | 50.26 | 99.12 | 0.507x | >= 1.00x | FAIL |
| GPU pure prefill-512 tok/s | 235.34 | 343.73 | 0.685x | >= 1.00x | FAIL |
| GPU e2e s (median, 32 tok) | 1.0842 | 0.7898 | 1.373x latency | <= 1.00x | FAIL |
| digest pin `dbf704971617fdfc` | — | — | — | holds on every candidate | PASS |

Correctness closes green: bundle battery 34/34 cases (5904/5904
assertions) on ane `a9a5f60`, Parakeet golden bit-exact on the installed
module, Qwen ANE layout gate verify 10/10 with the guard refusing
unguarded loads.

Levers closed this lane: q4 reduction flavor WASH (section 2); coopmat
m64 FALSIFIED for perf, bit-exact proven, not landed (section 5). Live
levers named for the next owner: the ~196 ms fixed per-prompt TTFT cost
(section 3), the 3.10 us/dispatch barrier-edge floor at 507
dispatches/tok (section 1), and the Qwen ANE TTFT gap 1.347x macOS
(`receipts/2026-09-25-jwm1-qwen-ane-layout-gate`).
