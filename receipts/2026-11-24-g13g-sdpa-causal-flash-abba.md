# G13G causal-flash SDPA prefill ABBA, 13-inch M1 (m1-host), 2026-11-24

Question: does the coopmat causal flash kernel
(`SdpaCausalFlashCoopmatBF16`, `MLX_OMARCHY_SDPA_CAUSAL_FLASH=1`) beat the
composed chunked default on G13G at the cell that trails macOS - 4B prefill
ctx 2048?

Why this op: per-op GPU profile (`+d6c1eea5b`, `MLX_OMARCHY_GPU_PROFILE`) of a
single 4B prefill shows ScaledDotProductAttention growing from 6.9% to 20.0%
of dispatch GPU time at pf512->pf2048 (~13.8x, super-quadratic) while
QuantizedMatmul scales ~4.1x (linear). On G13G the causal prefill dispatches
the composed route (3 kernels x 36 layers); the flash route collapses it to
one kernel per layer (verified in profile: 216 -> 72 SDPA dispatches,
~35% less SDPA GPU time).

Protocol: `qwen38-mlx-bench.py` kit `f872621c`, corpus `9299a3b2`,
`mlx-community/Qwen3-4B-Instruct-2507-4bit` @ `50d42775`,
`/usr/lib/omarchy-mlx/venv` (`+cf66ff1d0`), 5 blocks x ABBA (start arm
alternates), 3 prompts x 1 pass x 16 new tokens per run, metric
`pure_prefill_tok_rate`. Arm A = `MLX_OMARCHY_SDPA_CAUSAL_FLASH=1`, arm B =
env unset (composed default).

## Result

| arm | median pf tps | spread | vs B |
|---|---:|---:|---:|
| A flash | **162.81** | 134.33-162.95 | **+8.28%** |
| B composed | 150.36 | 150.19-150.45 | - |

Per-block medians: blk0 -1.22% (one cold A outlier, 134.33), blk1 +6.45%,
blk2 +5.73%, blk3 +8.34%, blk4 +4.46%. 4 of 5 blocks positive; every B run
sits in a 0.2% band around 150.4 while 7 of 10 A runs land at 162.8-163.0.
Decode flat both arms (~23.7 tps). `ordered_records_sha256` identical across
all 20 runs (`4f2e744b...`): bit-identical output.

The +8.28% flash median closes the macOS gap: composed B (150.4) matches the
earlier Linux cell (151.3) and flash A (162.8) passes the macOS cell (160.5).
A-arm variance is a warm/cold effect - the first-position and last-position A
runs in a block run slower; steady-state flash is ~163.

Caveats: one model (4B), one prompt length (2048), one part (G13G). The prior
gate that declined the default (receipts/2026-10-09-causal-flash-gate3)
measured G13C at pf512 where the gain is small - at 2048 on G13G the composed
route's quadratic score traffic is what the flash kernel eliminates.
