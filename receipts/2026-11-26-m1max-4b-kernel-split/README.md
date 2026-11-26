# 16-inch M1 Max 4B per-kernel split: Linux (omarchy/Vulkan) vs macOS (Metal) — 512-token prefill

SUP-3 row. Same physical machine both sides (m1max-host, MacBookPro18,2 / Apple M1 Max G13C,
64 GB). Phase compared: one (1,512) prefill forward on a fresh KV cache, Qwen3-4B 4-bit
(36 layers). Both captures are the existing instrumented artifacts; no new runs.

## Sources

| side | artifact | build / compiler | method |
|---|---|---|---|
| Linux (omarchy/Vulkan, Honeykrisp-class driver) | GPU-profiler NDJSON capture `prof-qwen34b4bit.ndjson`, AN-1 verify-shape sweep, CT-side copy under `~/scratch/main/m1max-vartmp-archive/an1-verify-20261123T093953Z/` (archived m1max-host `/var/tmp` dump) | mlx-omarchy dev build stamped `+4222ef1` (run script asserts the stamp); overlay shaders GLSL → SPIR-V | per-dispatch `d` records are host-side only in this build, so GPU time is attributed per submission: each submission ends in a barrier whose `b.dur` blocks until the queue drains (`b.dur` ≈ serialized GPU exec). The 10 ctx-512 prompt passes (sweep blocks 1–10) were segmented by their per-layer attention marker (36 `e=478` records/pass); block 1 additionally carries model-load records. ms/pass = median of passes 2–10 ≈ mean of 10 (spread 709–888 ms). |
| macOS (Metal) | ktime capture `w71-par83/metal-6733BC93/profile-4b/` (`ktime.jsonl` + `rank.json` + `SHA256SUMS`, boot nonce 6733BC93); `forward.json` pins input sha `7b438f64…` and `next_token_id=13` | `mlx==0.32.4` + `mlx-metal==0.32.4` (Apple Metal toolchain), `mlx-lm==0.32.2`, macOS 26.6.2 (25G83) | `libmetal_ktime.dylib` + `MLX_MAX_OPS_PER_BUFFER=0`: one command buffer per op, per-buffer `GPUStartTime→GPUEndTime` = real per-kernel GPU exec. Single forward, 923 buffers. |

Model refs: Linux `coreglass/models/qwen3-4b-4bit`; macOS `mlx-community/Qwen3-4B-Instruct-2507-4bit` rev `50d42775`. Same family/geometry; prompt content differs (random ids vs text) — kernel cost is shape-driven.

## Per-kernel split, ms per 512-token pass (ms/token)

Linux rows are submission archetypes (the GPU-attributable unit): each submission bundles one
layer-group's ops and drains through its own barrier. Dispatch counts are exact; the primitive
decomposition inside each archetype is an n-weighted estimate (flagged `~`).

| kernel / archetype | Linux disp/pass | Linux ms/pass | Linux ms/tok | macOS disp/pass | macOS ms/pass | macOS ms/tok |
|---|---|---|---|---|---|---|
| attention block: `3×ScaledDotProductAttention + Reshape + 2×QuantizedMatmul` per layer | 36 subs (216 disp) | 556.7 | 1.087 | — | — | — |
| — of which SDPA ~ | 108 | ~431.0 | ~0.842 | 36 `steel_attention` | 24.9 | 0.049 |
| — of which QMM ~ | 72 | ~77.8 | ~0.152 | (part of affine_qmm) | | |
| — of which Reshape ~ | 36 | ~47.9 | ~0.094 | — | — | — |
| QKV/norm block: `Add + QMM + RMSNorm + RoPE` per layer | 35 subs (350 disp) | 149.7 | 0.292 | — | — | — |
| MLP block: `Add + SiLU-fusion + QMM + RMSNorm` per layer | 35 subs (315 disp) | 141.2 | 0.276 | — | — | — |
| QuantizedMatmul (all archetypes, ~) | ~497 | ~290.7 | ~0.568 | 253 `affine_qmm_t` | 728.2 | 1.423 |
| SiLU gate fusion ~ | 35 | ~26.6 | ~0.052 | 36 `CV2I…Multiply…contiguous` | 5.0 | 0.010 |
| RMSNorm ~ | ~72 | ~27.8 | ~0.054 | 145 `rms` | 3.7 | 0.007 |
| Add ~ | ~71 | ~27.2 | ~0.053 | 72 `vvn_Add` | 1.6 | 0.003 |
| RoPE ~ | ~72 | ~0.3 | ~0.001 | 72 `rope` | 1.4 | 0.003 |
| embed / final-norm / lm_head / misc | ~26 | ~3.9 | ~0.008 | ~317 gathers/dequant/unnamed | ~0.1 | ~0.0002 |
| **total** | **890 disp** | **~851** | **~1.66** | **923 bufs** | **764.9** | **1.494** |

## Top 3 named gaps

1. **ScaledDotProductAttention: Linux ~0.842 ms/tok vs macOS 0.049 ms/tok (~17× heavier).**
   Linux issues 3 attention dispatches per layer at prefill scale (2× n=8.4M + 1× n=2.1M —
   a split q-side/kv-side decomposition) plus an attention-adjacent reshape; Metal runs one
   fused `steel_attention` per layer. The attention block is 65% of the Linux pass and 3.3%
   of the macOS pass. Largest single named gap.
2. **QuantizedMatmul: macOS 1.423 ms/tok vs Linux ~0.568 ms/tok (~2.5× heavier on Metal).**
   Metal's `affine_qmm_t` averages 2.88 ms per dispatch across 253 dispatches and is 95% of
   its pass. Linux splits each projection into ~2 dispatches (497 total, two alternating
   QMM programs) but its effective per-projection cost is far lower.
3. **Norm/residual "free" ops: Linux ~0.20 ms/tok vs macOS ~0.013 ms/tok.**
   Linux RMSNorm+Add+Reshape ≈ 0.20 ms/tok inside the mixed blocks vs Metal
   rms+vvn_Add+rope ≈ 0.013 — the per-dispatch barrier serialization tax on small ops.

Net: the two big gaps nearly cancel — totals 1.66 vs 1.49 ms/tok (11% apart) under matched
instrumentation. The structural difference, not the total, is the finding: macOS pays its
time in the quantized matmuls, Linux pays it in a decomposed attention path.

## Caveats

- Both captures are instrumented (Linux: barrier-serialized submissions; macOS: one buffer
  per op via DYLD ktime). Absolute ms/token inflate vs uninstrumented walls — shares are the
  signal, and both sides serialize similarly, so family-level gaps are directionally sound.
- Linux `~` rows decompose mixed submissions by operand-element share; archetype rows are exact.
- Prefill only: the single 4B Metal kernel dump is this forward; no 4B macOS decode ktime
  exists, so decode is out of scope (Linux decode-side split exists separately at ~3.4 ms/tok
  GPU-busy from the same profiler schema family).
