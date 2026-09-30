# 2026-10-01 jwm1 parity state of play (Linux vs jwm1's own macOS), losses first

Scope: the goal is >= 1.00x macOS per cell on the same M1 laptop (jwm1, T8103) for GPU inference (Qwen3.8-2B MLX), ANE inference and Parakeet, measured with the existing qwen38 protocol (n >= 5, temp 0) and paired macOS cells. Nothing here claims parity for a cell that has no paired macOS number or that is below 1.00x.

## Ledger (Linux live venv = mlx-omarchy b791539ed on Honeykrisp fork 283bf35c055; macOS = same laptop)

| Cell | Linux | macOS | Ratio | Status |
|---|---|---|---|---|
| Qwen decode 64 / 128 / 256 (tok/s) | 44.35 / 44.08 / 43.94 (n=5, digests d64 7fe6badf4d560e25, d128 da5568eeb4b6a1c1, d256 828b55d6249d9679) | 49.36 / 49.26 / 49.33 | 0.898 / 0.895 / 0.891 | LOSS |
| Qwen prefill 512 / 1024 / 2048, stock software both sides (tier A) | ~315 (last measured at 2cc1175b5-era driver, before later kernel work) | 345.6 / 345.9 / 341.7 | ~0.91-0.92 | LOSS |
| Qwen prefill 512 / 1024 / 2048, last-logits patch both sides (tier B) | ~394.6 / 399.9 / 398.0 | 457.6 / 458.7 / 452.0 | 0.862 / 0.872 / 0.880 | LOSS |
| Qwen TTFT (d64 corpus, median) | ~0.148 s | 0.125 s | ~1.19x latency | LOSS |
| ANE encoder (whole-program exec) | 138-140 ms | 113.27 ms | 0.81 | LOSS |
| Parakeet stage-matched inference (mel + encoder + TDT), fixture / v10 / v5 / v03 (after H142+H143, 2026-10-02) | ~252.2 / ~247.6 / ~226.1 / ~182.1 ms | 268.5 / 264.0 / 239.5 / 205.0 ms | 1.065 / 1.066 / 1.059 / 1.126 | PASS (4 cells; sum of stage medians, n=10 warm) |
| Parakeet stage-matched inference, fixture_v1 (1 s) (after H142+H143) | ~180.6 ms | 171.5 ms | 0.950 | LOSS |
| Functional agreement (d64 tokens vs macOS, 5 prompts) | 3 of 5 identical; the other two flip on bf16 logit ties (1 ulp, exact tie) at indices 14 and 19 | | | qualified, not a defect (H92) |

Parakeet caveats: the stage-matched sum is what macOS's CLI prints as "inference"; Linux's total pipeline (decoder load 40 ms, audio load 3 ms, detokenize 21 ms) is not paired with macOS's separate one-time model load and is not claimed. The encoder stage alone is 3-4% slower than macOS's CLI encoder on every clip (about 140 vs 135 ms).

## What moved in this stretch (all pushed, all bit-exact against the pinned digests)
- mlx-omarchy main: vec4 GDN decode state loads (+3.4% decode on the M1, H95b), Parakeet TDT window kernel load batching + fma (blank-walk TDT -13%, H128), weekly upstream-mlx drift watch (tools/upstream-compat-check.sh + workflow).
- mesa-1 branch asahi/hwmat-vec2-on (installed): paired fragment loads, shared-address fold, compute-shader scheduler skip (prefill +9.4% / +1.8%, decode +1.4-1.8%).

## Rejected with evidence (exact, or not faster): notebook entries in ~/.local/share/apple-silicon-lab/entries/jwm1-parity/
RMSNorm subgroup tail (H96), fp16 matrix operands (H97), magic-number dequant in prefill (H113), small-M matmul levers: A-fragment hoist / tile-major A / split-K / staged-A (H101-H111), stray-lookahead and idle TTFT diagnostics (H115/H116), first-chunk sizing, wider/narrower TDT windows (H119/H124/H125), fma-only TDT window (H126), CPU pstate / memory churn vs launch bimodality (H99/H100/H114).

## Measured ceilings that bound what is left
- fmadd32 chip-wide ceiling 2.00-2.26 TFLOP/s (H112); the prefill qmm reaches 1.45-1.53 in its fast mode (65-70%).
- Decode: Q4 GEMV in-chain 49.8-50.9 GB/s vs the 59.65 GB/s read probe (84%); small ops (~250 dispatches per token) cost roughly 2 ms; parity needs both.
- Parakeet 1 s clip: the TDT stage walks 375 padded frames on both sides by design; ~13 ms of its ~29 ms is re-streaming the 10.5 MB joint weight every slot.
- ANE: the gap is the engine clock, set by ANE firmware that Linux does not run on T8103 (CSNE_CMD 0x1f perf mode, receipt 2026-09-22-ane-dvfs). The macOS ADT (receipt 2026-10-01-jwm1-t8103-ane-adt) shows iBoot preloads an ANE firmware image (segments at 0x80093c000 and 0x8015b4000); the image itself is available from the public restore (see open decision 3).

## Open decisions and blocked levers (nothing is quiescent; each has a named owner or gate)
1. GDN prefill scan (12.6% of the 11-token forward, 7.9% of prefill 512): an exact version is the serial fp32 chain; a faster one changes fp32 summation order. Needs an explicit numerics decision (not taken).
2. (Withdrawn correction.) An earlier draft listed a Metal-style factorized Q4 GEMV as an untried numerics lever. It is already implemented: shaders/qmm_vec.comp follows MLX's native qmv arithmetic (per block dot = sum x*nibble, result += fma(scale, dot, sum*bias), half-precision x quad sums, magic-number nibble convert), i.e. about 3 ALU ops per weight. Nothing is left to gain from that factorization; the remaining decode gap is small-op count and the 84% streaming efficiency, both listed above.
3. ANE clock: T8103 firmware boot bring-up is the only route to the 0.81 cell and to the Parakeet encoder stage. Image source is now resolved without USB: the unencrypted H13 image (Firmware/ane/h13_ane_fw_styx_j5x.im4p in Apple's public restore; payload sha256 204d4b08b2a109a096df2e66ea507f0de928655f2d31c608258551f00e90dc0a) matches the ADT preload segments exactly and is an RTKit firmware that owns TM/TD and clock control (receipt 2026-10-01-jwm1-t8103-ane-adt). Still open: static start sequence, DART map, mailbox base, ADT nub properties, host TM-write conflict, perf-mode acceptance. Owner = the M2/ANE lane (T6021 code exists there, needs USB/hardware time); offline decoding help offered, not started.
4. Parakeet 1 s cell (0.952): remaining levers are a two-window shared weight stream (design change) or GPU-side blank-walk redesign; no exact micro-lever left.

## Update 2026-10-02 (Parakeet TDT dense phase, receipts/2026-10-02-jwm1-parakeet-tdt-h142-h143)
Two exact TDT-stage changes shipped to mlx-omarchy main and the live venv (fixture sha db501a8c0803, 104 emissions, status match after deploy): the control kernel reduces only the rows the window computed (H142) and the one-row window path batches weight loads and stages one row (H143). Dense clips: fixture TDT 110 -> 99.7 ms, v10 105 -> 95.3, v5 80 -> 74.0; blank-phase clips (v03, v1) unchanged. The rows above were updated to the new sums; the 1 s clip stays a loss (TDT ~29 ms vs macOS 22.0 ms, encoder +5 ms).

## Update 2026-10-02 (later): live-wheel regression found and fixed; driver serializes every dispatch
- **Regression (H147/H148):** the Parakeet deploy (wheel b791539ed) had replaced the whole wheel, and its C++ delta included the jw16 lane's attention out-gate prologue fold (972659e6c). On the M1 it cost 1.4-2.1% decode (d64 43.65 vs 44.26-44.35 tok/s, same digests) and was the only source of a GPU fault in a 7-run sample (1 of 7 runs with the fold on; 0 of 14 with it off or on the previous wheel). Fixed by a chip-keyed default (off on G13 parts other than G13C, `MLX_OMARCHY_OUTGATE_FOLD=0/1` override), mlx-omarchy main 34114ea53, live venv upgraded, previous wheels kept as rollback venvs. Post-deploy: decode64 44.26-44.42, Parakeet fixture sha db501a8c0803. The decode rows of the ledger above are therefore valid again for the live stack; between the b791539ed deploy and this fix they overstated it by ~1.7%.
- **Open:** the d256 digest is 7d0523ae795bf83f in every arm this session (including the previous wheel) while the earlier deploy battery recorded 828b55d6249d9679 five times: session/boot-dependent, not diagnosed; d256 comparisons are arm-vs-arm within a session.
- **Driver finding (H146):** `hk_dispatch_with_usc_launch` emits a CDM barrier after EVERY launch regardless of Vulkan barriers, which is why barrier-free issue never overlapped (H138). A fork patch that defers the flush to the end of the compute batch (env `HK_CDM_DEFER_FLUSH=1`, default off; patch in the notebook artifacts, branch jwm1/cdm-deferred-flush in the local fork; the push to mesa-1 is blocked by the privacy hook on old blobs, not bypassed) makes barrier-free GEMV dispatches 10.5 us cheaper each (54 -> 44 us) and gives +0.9..1.0% decode at today's MLX barrier-skip rate (12% of decode dispatches), bit-identical digests. The larger prize is raising the skip rate in the MLX encoder (H149, not started).
