# jwm1 gated-barriers digest gate (H33), 2026-09-29

jw16 (T6001) reported MLX_OMARCHY_GATED_BARRIERS moving to default ON. This is the T8103 (jwm1) gate on the live wheel (1daa1ad5d + qk/conv/gated patches), stock system Vulkan driver, Qwen3.8-2B MLX 4-bit, qwen38 protocol, temp 0.

Arms interleaved per round under one flock hold: a = live default, b = GATED_BARRIERS=1, c = GATED_BARRIERS=1 + HK_SUBMIT_POLL_US=2000 (inert here: no poll driver installed).

Result: all 54 runs carry the pinned digests (decode64 7fe6badf4d560e25, decode128 da5568eeb4b6a1c1, decode256 828b55d6249d9679, prefill ccb601895581d89f). Median throughput ratios vs a (b / c):

| Cell | b/a | c/a |
|---|---|---|
| decode64 (n=4 rounds x 5 prompts) | 1.001 | 1.001 |
| decode128 (3 rounds) | 0.997 | 0.996 |
| decode256 (3 rounds) | 1.001 | 0.999 |
| prefill512 (5 rounds) | 0.995 | 0.998 |
| prefill2048 (3 rounds) | 1.001 | 1.005 |

All within the 2.4% same-code spread: no gain, no regression, no divergence on jwm1. Default-ON is digest-safe here and buys nothing here. `analysis.txt` is the analyzer output; `raw/` has every run JSON.

Not a parity claim: Linux stays below macOS on every GPU cell (see receipts/2026-09-29-jwm1-deployed-stack-cells).
