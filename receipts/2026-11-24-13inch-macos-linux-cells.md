# 13-inch M1 (T8103): same-runner macOS vs Linux qwen38-mlx-bench cells, 2026-11-24

Same physical 13-inch M1 (`m1-host`), one session: macOS window via the
documented a12 one-shot route, then back to Omarchy Linux, same kit and
snapshots on both OSes. Question: does the Linux 4B prefill at ctx 2048 trail
macOS, and at ctx 512?

Protocol: `qwen38-mlx-bench.py` (kit sha `f872621c`, corpus `qwen38-2b-prompts.jsonl`
sha `9299a3b2`), 3 prompts x 1 pass, 64 new tokens, warmup 1. Metric: bench's
`pure_prefill_tok_rate` (2048-token prefill leg) / `ttft_tok_rate.median` (512 cell
same shape), decode `decode_tok_rate.median`. n=3 prompts per cell.

Models (same HF snapshots both OSes):
- 2B: `SiddhJagani/Qwen3.8-2B-mlx-4Bit` @ `0867d98bfb174b042d88461c0e7c97b86b34b381`
- 4B: `mlx-community/Qwen3-4B-Instruct-2507-4bit` @ `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`

Venvs:
- macOS: `~/bench-qwen38-venv` — mlx 0.32.2, mlx-lm 0.31.3, python 3.14.7, Metal backend
- Linux: `/usr/lib/omarchy-mlx/venv` — mlx-omarchy `+cf66ff1d0`, honeykrisp Vulkan

## Cells (tok/s)

| cell | decode mac | decode lin | prefill mac | prefill lin |
|---|---:|---:|---:|---:|
| 2B pf512  | 46.72 | 47.53 | 344.5 | 429.1 |
| 2B pf2048 | 47.14 | 47.58 | 340.9 | 423.9 |
| 4B pf512  | 23.42 | 23.61 | 168.6 | 177.5 |
| 4B pf2048 | 24.25 | 23.66 | 160.5 | **151.3** |

Decode is at parity (+-2%) in all four cells. Linux leads prefill in three of
four cells (2B +25%); the exception is 4B pf2048, where Linux trails macOS
151.3 vs 160.5 (-5.7%). Token ids differ per OS (Metal vs honeykrisp numerics)
but are stable within each OS across prompts and passes.

## Follow-up: what grows in the Linux 4B prefill at 2048

Per-op GPU profile of one 4B prefill (profiler wheel `+d6c1eea5b`,
`MLX_OMARCHY_GPU_PROFILE`), shares of total dispatch GPU time:

| op | pf512 share | pf2048 share | time scaling 512->2048 |
|---|---:|---:|---:|
| QuantizedMatmul | 89.3% | 76.9% | ~4.1x (linear) |
| ScaledDotProductAttention | 6.9% | 20.0% | ~13.8x (super-quadratic) |

SDPA is the riser: ~0.21s -> ~2.94s of GPU time per prefill. On G13G the
causal prefill takes the composed chunked route (216 SDPA dispatches/prefill =
3 kernels x 36 layers x 2 runs); the coopmat causal flash kernel
(`SdpaCausalFlashCoopmatBF16`, `MLX_OMARCHY_SDPA_CAUSAL_FLASH=1`) is
default-on only for G16S (primitives.cpp, route comment cites
receipts/2026-11-15-m4-pro-g16s-sdpa-causal-flash; G13C missed the +2% bar at
pf512 in an earlier gate). ABBA of the flash route vs composed default on
m1-host 4B pf2048: see `receipts/2026-11-24-g13g-sdpa-causal-flash-abba.md`.
