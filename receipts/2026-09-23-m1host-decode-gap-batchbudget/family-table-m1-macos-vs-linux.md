# Per-op-family table: m1 macOS (Metal) vs m1-host Linux (Vulkan)
# (host names sanitized per repo privacy patterns)
# Per-op-family table: m1 macOS (Metal) vs m1-host Linux (Vulkan)
# Same chip (T8103/M1), same model (SiddhJagani/Qwen3.8-2B-mlx-4Bit
# snapshot 0867d98b), same script (family_bench.py, amortized
# launches/flush, median of 30). Calls/token from the Linux compile-ON
# decode capture. Sources: families-metal-m1.json (macOS) +
# families-linux-installed.json (Linux, installed umalimit1 wheel).

| family | calls/tok | macOS us | Linux us | ratio | delta us/tok |
| --- | ---: | ---: | ---: | ---: | ---: |
| sdpa | 18.6 | 5.81 | 230.06 | 39.6x | **4171** |
| rms_norm | 118.8 | 1.52 | 19.14 | 12.6x | **2093** |
| qmm[2048x2048] | 37.2 | 28.63 | 62.99 | 2.2x | 1278 |
| qmm[6144x2048] | 18.6 | 84.50 | 152.01 | 1.8x | 1256 |
| lm_head full composed | 1.0 | 4242.07 | 5399.36 | 1.27x | 1157 |
| qmm[2048x6144] | 18.6 | 78.80 | 138.82 | 1.76x | 1116 |
| qmm[4096x2048] | 18.6 | 56.36 | 111.76 | 1.98x | 1030 |
| conv+silu[6144x4] | 18.6 | 3.66 | 37.65 | 10.3x | 632 |
| rope | 12.4 | 3.64 | 22.15 | 6.1x | 230 |
| qmm[512x2048] | 18.6 | 7.56 | 17.37 | 2.3x | 183 |
| qmm[16x2048] | 6.2 | 2.33 | 6.07 | 2.6x | 23 |
| TOTAL benched delta | | | | | **13,170 us/tok** |

Whole-token: m1 macOS 49.6-49.9 tok/s (stock mlx-lm 0.31.3) vs m1-host
Linux installed 36.7 tok/s. The benched-family delta (13.2 ms/tok
amortized) overstates the whole-token gap (7.3 ms) — the amortized
methodology charges Linux full serialized host-issue cost that the real
decode partially pipelines — but the RANKING is the deliverable.

## Ranked levers (real, same-chip)
1. **SDPA is a composed fallback on Linux: 230 µs/launch vs Metal's
   fused 5.8 µs (39.6x)** — 4.2 ms/tok. The single biggest row. A fused
   Vulkan SDPA kernel (decode shapes: 6 full-attn layers, 8 heads x
   256, kv 2 x 256, L<=1024) is the top lever.
2. **Per-launch host cost: Linux ~19 us vs Metal ~1.5 us for tiny
   kernels (12.6x on rms_norm; 118.8 launches/tok)** — ~2.1 ms/tok on
   rms_norm alone, more across the swarm. Systemic: the omarchy
   encoder's per-node record+barrier+submit cost. Fusion (swarm) or
   cheaper per-node recording both attack this.
3. **qmm GEMV kernels 1.8-2.6x slower than Metal quantized matmul** —
   ~4.9 ms/tok across the family (bandwidth-bound both sides; Metal's
   kernel efficiency wins, not its bandwidth). Kernel-efficiency work
   (occupancy/tiling) on QmmVecQ4*.
4. lm_head: only 1.27x — both near-roofline (bandwidth-bound); the
   pruned route already banked the available win here. Parked.
