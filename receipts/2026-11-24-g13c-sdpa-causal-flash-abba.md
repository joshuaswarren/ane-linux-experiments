# G13C causal-flash SDPA prefill ABBA, 16-inch M1 Max (m1max-host), 2026-11-24

Question: does the coopmat causal flash kernel
(`SdpaCausalFlashCoopmatBF16`, `MLX_OMARCHY_SDPA_CAUSAL_FLASH=1`) beat the
composed chunked default on G13C? Sister check to the G13G ABBA
(`2026-11-24-g13g-sdpa-causal-flash-abba.md`), run after the jwm1 4B pf2048
per-op profile showed SDPA as the super-quadratic riser on the composed
route (6.9% -> 20.0% of dispatch GPU time at pf512 -> pf2048).

Protocol: `qwen38-mlx-bench.py` kit `f872621c`, corpus `9299a3b2`,
`/usr/lib/omarchy-mlx/venv` (`+bf5631d`, predates the #785 G13G flip so arm B
is the true composed default), 5 blocks x ABBA (start arm alternates),
3 prompts x 1 pass x 16 new tokens per run, metrics
`pure_prefill_tok_rate` / `decode_tok_rate.median`. Arm A =
`MLX_OMARCHY_SDPA_CAUSAL_FLASH=1`, arm B = env unset.

## Results (20 runs per cell, ids sha identical in every cell)

| cell | A flash | B composed | delta | per-block |
|---|---:|---:|---:|---|
| 4B pf2048 prefill | **563.34** | 516.59 | **+9.05%** | +8.43 +8.91 +9.19 +8.19 +8.77 |
| 4B pf512 prefill | 595.09 | 588.57 | +1.11% | +0.02 +1.05 +1.14 +1.29 +0.65 |
| 4B dec2048 decode | 80.66 | 80.34 | +0.39% | +1.07 -0.98 +1.53 -0.28 +0.01 |
| 2B pf512 prefill | 1436.90 | 1437.50 | -0.04% | -5.08 +0.19 -0.15 +0.08 -0.09 |

Models: `mlx-community/Qwen3-4B-Instruct-2507-4bit` @ `50d42775`,
`SiddhJagani/Qwen3.8-2B-mlx-4Bit` @ `0867d98b`. `ordered_records_sha256`
identical across arms and across hosts (4B `4f2e744b...`, 2B `5251cdd6...`):
bit-identical output.

No cell regresses. The pf2048 win (+9.05%, every block +8-9%) matches the
G13G re-measure (+8.28%, `2026-11-24-g13g-sdpa-causal-flash-abba.md`). The
earlier gate that declined flash on G13C (receipts/2026-10-09-causal-flash-
gate3) measured pf512 only - consistent with the +1.11% seen here; at 2048
the composed route's score traffic is what the flash kernel eliminates.

Note: the 2B pf512 block-0 A run was one cold outlier (the -5.08% block);
blocks 1-4 are flat. Same cold-start pattern as the G13G A arm.
