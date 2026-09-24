# Interim results (2026-09-24 15:40 CDT, n=7 paired reps of 10; window paused for M2 ANE capture)

Arms: ctl = bf8793f (receipted 17.46 baseline stack), base = 2df8904 (rel/v0.7.3, no SDPA),
cand = f9d7bb21d (rel/v0.7.3 + SDPA hd256). All arms: unpatched mlx-lm 0.31.3 (verified:
no gated_delta_update_raw / greedy_quantized_argmax in any venv), greedy, 32 new tokens,
warmup 3, 1 pass x 10 prompts per rep, MLX_DISABLE_COMPILE=1.

Pins: ordered_records_sha256 = 1aa2f5f8... IDENTICAL across all 21 contract files, both
arms and all reps — token streams bit-exact, 0 flips.

| arm | n | mean decode tok/s | sd | range |
| --- | ---: | ---: | ---: | --- |
| ctl (bf8793f) | 8 | 16.39 | 0.01 | 16.37-16.41 |
| base (2df8904) | 7 | 16.55 | 0.02 | 16.52-16.58 |
| cand (f9d7bb2) | 7 | 16.69 | 0.01 | 16.68-16.70 |

Paired deltas:
- cand vs ctl: +0.306 tok/s, 95% CI [+0.288, +0.323], ratio 1.0187 — CI entirely positive
- cand vs base: +0.141 tok/s, 95% CI [+0.123, +0.159], ratio 1.0085 — CI entirely positive (PURE SDPA effect)
- base vs ctl: +0.164 tok/s, 95% CI [+0.140, +0.188], ratio 1.0100 (lineage effect alone)

Reading: the pure SDPA effect on T8103 is +0.85% — much smaller than t6001's +4.67% because
the M1 decode wall is dominated by the q4-GEMV bandwidth floor + per-launch overheads; SDPA
composed (230 us x 6 layers ~ 1.4 ms of a ~60 ms token) is only ~2.3% of the M1 token, and
the fused arm recovers ~0.5 ms of it. Consistent with the eb1e711 family table's ranking:
on M1 the bigger levers are the rms_norm swarm (12.6x, 2.1 ms/tok) and qmm efficiency
(1.8-2.6x, 4.9 ms/tok) — but both are multi-day kernel/launch-structure work, while SDPA
was staged and free.

Remaining: reps r8(cand,base), r9, r10 (9 files), 3 ten-pass anchors, budget profile,
microbench, family bench — rescheduled after the M2 ANE capture (Main directive 15:34 CDT).
