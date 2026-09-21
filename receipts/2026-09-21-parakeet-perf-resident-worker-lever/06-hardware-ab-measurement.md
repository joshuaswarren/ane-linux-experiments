# 06 — Worker lever hardware A/B measurement (jwm1)

**Lane:** `ParakeetPerformance`, branch `agent/parakeet-perf-worker-lever`.
**Date:** 2026-09-21.
**Hardware:** jwm1-linux, `/dev/accel/accel0`, `/tmp/m1-gpu.lock` inode 27.
**Lease:** warm+5 per arm; ARM A at 07:11Z (arm A only) and 07:28Z (A re-run);
ARM B+C together at 07:30Z (total 83 s under lock; lock released immediately).
**Resolved model:** `minimax-code/MiniMax-M3` (parent omp session).

## Measured A/B/C (warm + 5 measured per arm, all gates green per run)

| arm | worker | sha256 (head) | encoder_ane median all 5 | median runs 2-5 | total median |
|---|---|---|---:|---:|---:|
| A | prebuilt (parent baseline ref) | `944f2a86…` | 5209.149 ms | 5145.876 ms | — |
| B | built base (no lever) | `f039e5fc…` | 5145.542 ms | 5154.900 ms | 6515.212 ms |
| C | built **lever** (`_IONBF` + dropped per-output fflush) | `afd612c4…` | **5101.518 ms** | **5070.390 ms** | 6445.485 ms |

**Lever delta (C vs B — the matched-build comparison):**
- median all 5: **−44.0 ms (−0.86 %)**
- median runs 2-5: **−84.5 ms (−1.64 %)**
- total median: **−69.7 ms (−1.07 %)**

**C vs A (prebuilt parent baseline):** −107.6 ms (−2.07 %) — includes both
the lever gain and the new-build compiler delta; the matched C-vs-B number
is the honest lever-only claim.

**Gates on every measured run of every arm:** `status=match`,
`prefix=104`, mel `5b54f4a9…`, hidden `38c73261…`, transcript
`db501a8c…` — all bit-exact. No criterion weakened anywhere.

## Build provenance

- Canonical omarchy-ane worktree: `/tmp/omarchy-ane-pinned` on jwm1,
  detached HEAD at `6fa243ac7241119a9eb229abbf8cb4dd8949f915`, clean
  (verified `git rev-parse HEAD` + `git status --porcelain` empty).
  Clone from public origin `https://github.com/joshuaswarren/omarchy-ane.git`.
- CMake cache: `MLX_BUILD_OMARCHY=ON`, `MLX_OMARCHY_ANE_DEVICE=ON`,
  `MLX_OMARCHY_ANE_SOURCE_DIR=/tmp/omarchy-ane-pinned`,
  `BUILD_SHARED_LIBS=ON`, `CMAKE_BUILD_TYPE=Release`.
- The CMake `NOT TARGET` guard makes the omarchy backend's thin
  `worker_main.cpp` win the `mlx-omarchy-ane-worker` name, so the TOOLS
  CLI variant was compiled directly with g++ (same headers, same libmlx.so,
  same `-DMLX_OMARCHY_ANE_DEVICE=1`): scripts committed as
  `build_tools_worker.sh` (base) and `build_lever_worker.sh` (lever).
- The two binaries differ ONLY in the lever:
  - `setvbuf(stdout, nullptr, _IONBF, 0)` at `serve_resident` entry
  - one redundant `std::fflush(stdout)` dropped in the per-output emit
    loop (no-op under `_IONBF`)
- Worker subprocesses launched via a tiny wrapper exporting
  `LD_LIBRARY_PATH=/tmp/parakeet-perf-resident/build-lever` so the venv's
  own `mlx` Python module is untouched (global `LD_LIBRARY_PATH` breaks
  the venv mlx with a symbol mismatch — documented pitfall).

## Byte equivalence (previously proven, restated)

Standalone C++ test (`worker-lever/emit_byte_test.cpp`): base and lever
emit byte streams are IDENTICAL — 7944 bytes each, 72 `out ` headers,
48 `job status=` lines, every byte in order. The hardware runs above
additionally enforce the three golden hashes bit-exact per run, which
exercises the real device output end-to-end.

## Interpretation

The lever's −44 to −85 ms (~1-1.6 %) matches the parent-measured
submission-path headroom: the per-output `fflush` costs a syscall +
potential pipe drain per emit (72 emits per pass), and `_IONBF` folds
each into the natural `write()` of the preceding `printf`/`fwrite`.
This is a real, small, gate-preserving win — NOT the 890 ms
`first_byte_ns` segment itself (that is dominated by worker exec + ANE
compute, which no flush strategy can move).

## What was NOT done

- No compiler changes (FleetM1Encoder / EncoderHardwareContinuation lane).
- No Mesa / GPU shader changes (FleetM1MaxGPU / GPUHardwareContinuation).
- No changes to the venv, `encwall-v071/base`, or the parent's prebuilt
  worker `944f2a86` (ARM A preserved it byte-for-byte as the reference).
- No criterion change: 104/104 + three golden hashes bit-exact enforced
  on every measured run of every arm.

## Artifacts

- `ab-hardware/A-prebuilt-summary.json` (this repo, this commit)
- `ab-hardware/B-built-base-summary.json` (this repo, this commit)
- `ab-hardware/C-built-lever-summary.json` (this repo, this commit)
- On jwm1: `/var/tmp/jwm1-ane-step2/fused-e2e/ab-20260921T071102/`
  (ARM A), `/var/tmp/jwm1-ane-step2/fused-e2e/ab-20260921T073054/`
  (ARMs B+C), each with per-arm `identity.txt` pins.
- Binaries on jwm1 under `/tmp/parakeet-perf-resident/`:
  `mlx-omarchy-ane-worker-tools` (f039e5fc…),
  `mlx-omarchy-ane-worker-lever` (afd612c4…), plus
  `worker-base-prebuilt.bak` (944f2a86… backup).

## Next

- The lever patch (`main_lever.cpp`) + scripts live on this branch for
  review. Applying it to the production tree is the omarchy-ane /
  mlx-omarchy owners' call; this lane has shipped the proof chain:
  byte-equivalence (x86 test) + hardware A/B (aarch64 jwm1) + gates.
