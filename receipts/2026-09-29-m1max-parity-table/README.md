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
| Qwen ANE reference, Linux ANE-only vs macOS ANEForge (10 prompts x 32 tokens x 1 rep; reduced n) | e2e median 364 s per 32 tokens (min 318, max 484): 0.088 tok/s; 0/10 prompts match all 32 ids (first divergence token 5-23; macOS token is Linux rank 2-4, gap 0.125-0.70) | e2e median 5.67 s, decode 6.76 tok/s (n=100) | ~64x slower e2e | loss on speed AND top-1 gate FAIL; not the contract cell (no warmups, n=1 rep, no bootstrap): UNPAIRED |

Progress since the 2026-09-28 pairing (same protocol): decode +9.7..+10.6%, prefill +3.8..+6.1%, Parakeet
warm total 913.7 -> ~795 ms (receipts 2026-09-29-m1max-linux-perf-levers). No cell has reached parity.

## Addendum (later 2026-09-29): fused norms at prefill sizes deployed
mlx-omarchy cfaca451e removes the decode-only size guards of the bit-exact fused gated-norm and qk-scaled norm routes (0 mismatches vs the composed chain at 16..32768 rows; all 7 cell digests unchanged). Prefill now 804.9 / 896.3 / 919.5 tok/s at 512 / 1024 / 2048 (0.606 / 0.661 / 0.666 of macOS); decode unchanged (88.7 / 87.7 / 86.4 / 84.1 tok/s, 0.49-0.48 of macOS). Still every cell a loss. Largest remaining prefill terms (T=2048, per-layer, Linux vs macOS): SDPA 22.7 vs 5.5 ms (composed QK^T/softmax/PV, no fused causal kernel), gated_delta_update 9.6 vs 3.7 ms, MLP/projection GEMM 1.27x slower, lm_head over all T 464 vs 365 ms.

Qwen ANE gate diagnosis: a host-fp32 final norm + lm_head (the macOS contract arm) leaves the Linux generated ids unchanged on the three earliest-diverging prompts (first divergence tokens 13/6/5 both ways), so the top-1 flips originate in the 24 decoder layers, not the head. Per-layer checkpoint comparison with a macOS ANEForge capture is the next discriminator.
