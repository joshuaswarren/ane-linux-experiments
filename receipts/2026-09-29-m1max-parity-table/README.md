# 2026-09-29 — M1 Max (T6001) paired parity table, Linux vs jw16's own macOS

Pass rule: throughput >= 1.00x macOS, latency <= 1.00x, with uncertainty; anything else is a loss.
Uncertainty here = min-max over the n=5 measured passes/processes (spreads are all <2% of the median, far
smaller than every gap). Linux = production stack after 2026-09-29 (mlx-omarchy `rw10` wheel + gated-norm
mlx-lm patch, Honeykrisp `poll9d949d4`, no env overrides); macOS = upstream mlx 0.32.2 (Metal) / CoreML,
2026-09-28 window 1. Ordered-records digests: identical to the pre-change Linux baseline in every cell;
Linux vs macOS token ids identical for the first 117 generated tokens (d64 digest identical), diverging at
token 117 on longer cells (bf16 near-tie), deterministic on both sides.

| cell | Linux median (min-max) | macOS median (min-max) | Linux/macOS | verdict |
|---|---:|---:|---:|---|
| decode 64 tok/s | 88.21 (88.16-88.58) | 180.01 (179.34-180.23) | 0.490 | loss |
| decode 128 | 87.62 (87.16-87.69) | 179.28 (179.22-179.50) | 0.489 | loss |
| decode 256 | 86.61 (86.49-86.78) | 178.28 (178.15-178.47) | 0.486 | loss |
| decode 512 | 84.16 (84.06-84.83) | 177.12 (177.03-177.19) | 0.475 | loss |
| prefill 512 tok/s | 791.3 (786.0-794.2) | 1327.2 (1324.7-1340.7) | 0.596 | loss |
| prefill 1024 | 883.0 (880.0-885.9) | 1355.8 (1355.4-1359.7) | 0.651 | loss |
| prefill 2048 | 895.7 (888.4-912.2) | 1379.6 (1379.1-1379.9) | 0.649 | loss |
| whole encoder ms (latency) | 440.8-441.1 (n=3 x 5 contract runs) | 138.18 (134.10-141.72), n=10 | 3.19x slower | loss |
| Parakeet warm total ms, 10.4 s fixture | ~795 | 261 (ane arm inference) | ~3.0x slower | loss |
| Parakeet 11-clip corpus, transcript match | 9/11 exact, WER 0.76% vs macOS ane | reference | - | functional match on speech, tail differs |
| Qwen ANE reference (reduced n: 1 prompt, 2 tokens) | 0.042 tok/s (24 s/token; 20.4 s/step + 3.4 s logits), ids == macOS for the 2 generated tokens; ANE-only, finite | 6.76 tok/s decode (n=100) | 0.006x | loss; contract cell (10 reps x 10 prompts x 32 tokens, ~24 h) not run: UNPAIRED |

Progress since the 2026-09-28 pairing (same protocol): decode +9.7..+10.6%, prefill +3.8..+6.1%, Parakeet
warm total 913.7 -> ~795 ms (receipts 2026-09-29-m1max-linux-perf-levers). No cell has reached parity.
