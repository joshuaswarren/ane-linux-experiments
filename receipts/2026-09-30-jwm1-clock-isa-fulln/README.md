# jwm1 2026-09-30 (session 2): GPU clock ruled out, coopmat FULL_N shipped (+8.8% prefill), kernel-ISA findings, ANE window 4

## macOS window 4 (11:19Z-11:25Z, ~6 min, read-only)
- Encoder ANE 200 reps: median 113.27 ms (window-1 value 113.24 reproduced; placement ane 1345 / cpu 29). macOS ANE denominator is stable.
- powermetrics GPU during the parity workloads: `GPU HW active residency: 100.00%` at 1278 MHz (top of 396/528/720/924/1128/1278) in every busy sample of decode256 (median GPU power 6.5 W) and prefill2048 (10.4 W). `ane_power` reads 0 mW on this OS build (sampler broken).
- Artifacts: artifacts/jwm1-parity/macos-window4/ (ADT plists incl. ane0 + pmgr voltage-states, powermetrics captures, 3x d256 + 3x pf2048 legs).

## Linux GPU clock: settled, not the gap
- Out-of-tree read-only `macsmc_railmon.ko` (source /var/tmp/railmon on jwm1; unloaded after use) dumps SMC keys. Load-vs-idle scan identified the GPU rail: VP1b (0.005 -> 0.71 V) with PP1b power 0 -> 5.7 W.
- macOS ADT voltage-states9 decodes to (MHz, mV): 396/600, 528/634, 720/671, 924/759, 1128/850, 1278/918.
- During sustained prefill2048 and decode256 on Linux VP1b reads 0.909-0.911 V = the 1278 MHz top state; GPU rail power 7-8 W (prefill) / 5.4-5.8 W (decode) vs macOS GPU 10.4 / 6.5 W. The firmware holds the top pstate; clock is NOT the cause of 0.74x prefill / 0.84x decode. (DT perf-controller knobs - tgt-utilization 85%, PI gains - remain a documented-but-unpulled lever; unnecessary since the top state is already reached.)

## ISA / microarchitecture facts (AGX_MESA_DEBUG=shaders on the release poll driver)
- fp32 scalar FMA throughput on G13G: ~1.15 TFLOP/s in every operand class (GPR/uniform/immediate, ffma/fmul/fadd), ~56 lane-ops per cycle per core at 1278 MHz x 8 cores; scalar fp16 hfma is 2.156 TFLOP/s (~105 lane-ops/cycle/core). The fp32 inner loop is exactly 16 ffma + iadd + jmp (optimal codegen). macOS reaches 2.15 TFLOP/s fp32 in its 1024^3 matmul via the matrix unit, not scalar ALU.
- The deployed prefill qmm kernel (X_F32 coopmat build) inner loop: 473 AGX instructions per 64 simd_matrix_fmadd32 (iadd 100, lload 64, device load 38, u32_to_f+ffma 32+32 dequant, lstore 32, ...). Every lstore/lload carries its own iadd and index operand 0 (the known Mesa `agx_zero()` index TODO; WIP 0003 offset-fold was +4.15% on llama.cpp but numerically invalid).

## Shipped (mlx-omarchy origin/main)
- b612e4f63: FULL_N x32 variants of the qmm coopmat kernels (column_ok compiled out when matrix_n % 32 == 0 - true for every Qwen3.8-2B projection). Interleaved A/B vs live, fresh candidate venv: pure prefill 512 255.5 -> 278.1 (+8.88%, n=5), 1024 +8.62%, 2048 +8.75%; decode unchanged; every digest identical. Kernel-level +8.3..+12.4% on 10 shape/M configs with mismatch 0 (new tools/qmm-prefill-bench harness). Live venv pinned after deploy: prefill512 278.26 tok/s digest ccb601895581d89f, decode256 41.31 tok/s digest 828b55d6249d9679. Rollback venv /var/tmp/jwm1-venv-91cc3f0f3.
- Also on main this session: d955aebed (harness probes: pad/cols/realloc/xtile; negative-record shaders n64 + tile-major-A).
- Earlier in the session: H71 CCTRACE stderr print removal (c065a3df9, decode-neutral), H61/H62 receipts backfilled.

## Current standing (Linux / macOS, paired same-die cells)
| Cell | Linux | macOS | Ratio |
|---|---:|---:|---:|
| decode 64 / 128 / 256 | 41.8 / 41.2 / 41.3 tok/s | 49.36 / 49.26 / 49.33 | 0.846 / 0.836 / 0.838 LOSS |
| prefill 512 / 1024 / 2048 | 278 / 280 / 272 tok/s | 345.31 / 345.76 / 341.80 | 0.805 / 0.810 / 0.797 LOSS (was 0.74) |
| TTFT | 0.160 s | 0.1248 | 1.28x latency LOSS |
| Parakeet stage-sum (mel+enc+TDT) | 263.4 ms | ~272 | not a parity claim |
| encoder ANE | 138.0 ms | 113.27 | 0.815 LOSS |

## Rejected today (all bit-exact, all slower or neutral)
- GDN decode 16-ahead state loads (H68): +0.44-0.56% but decode256 digest changed -> reverted.
- qmm TILE_ROWS=64 (0.92 gate / 0.84 down), TILE_N=64 (0.68, register pressure), tile-major A layout (mode-tracking, no gain), runtime ablation bits (uniform branches degrade the kernel 20% - H74 invalid as designed).
- macOS-side ANE clock observability (powermetrics ane_power = 0) and Linux GPU clock raising (top state already held).

## Open levers, ranked
1. Mesa agx local-load/store offset fold (+~4% expected; poll-src incremental build verified; validation = harness mismatch + digests).
2. qmm coopmat instruction diet beyond FULL_N (vectorized/shared fragment staging; the 38 scalar A loads per trip).
3. Decode small-op dispatch fusion (swiglu/RMSNorm into qmm prologue) - decode is 0.84x with ~441 dispatches/token.
4. ANE: firmware-mediated perf mode (CSNE_CMD) - 138 vs 113.27 ms.
