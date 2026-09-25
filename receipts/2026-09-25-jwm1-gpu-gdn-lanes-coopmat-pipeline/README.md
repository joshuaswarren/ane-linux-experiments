# 2026-09-25 — jwm1 (T8103) GPU levers: GDN four-lane kernels, qmm coopmat prefetch/double-buffer, ANE prefill-512 leg, Parakeet stage state — Jwm1Parity8

Owner: Jwm1Parity8. Host: jwm1-linux (T8103, G13G), contract venv
`/var/tmp/jwm1-parity3-venv` (mlx-lm 0.31.3 + main patch set), user entry
point `~/.local/bin/mlx-omarchy-serve` -> `~/.local/share/mlx-omarchy/venv`,
`MLX_DISABLE_COMPILE=1`, bench `benchmarks/qwen38-mlx-bench.py` (10 prompts,
32 new tokens, prefill 512, 3 warmups). Prior state:
`receipts/2026-09-25-jwm1-gpu-gemv2-smallm-tile` (decode 39.1, ttft 56.55,
prefill ~237 tok/s, e2e 1.0174 s on mlx-omarchy 27aba5211; pins
486872c410629f1d (1-pass) / dbf704971617fdfc (10-pass)). macOS bars
47.05 / 99.12 / 343.73 / 0.7898 s. Raw JSONs on jwm1: `/var/tmp/parity8/gpu/`,
logs `/var/tmp/parity8/*.out`.

## 1. ANE cell: max_len 513 export kit verified + prefill-512 leg (PASS)

Coordinated with `QwenAneExport512` (kit provenance: compiled on macstudio
with TargetArchitecture h13, io_layout plan 416 surfaces byte-exact vs
macOS at 513, 0 nonzero padding; libane guard refuses pristine dense ANECs;
receipt `receipts/2026-09-25-qwen-ane-export-513` @ main `039fd25`).

- **Replay gate** (correctness at 513): `window.sh replay` on jwm1 ->
  **REPLAY PASS, 368/368 surfaces byte-identical** to the macOS e5rt
  goldens (`export/goldens.json`, sha256 `ac11b3cd…`). The 2/10 score
  against the max_len 50 chunk_00 reference is the expected 513-numerics
  divergence (reproduced identically on macstudio e5rt).
- **Prefill-512 leg** (same boundary as macOS 11.74 tok/s denominator,
  fedd4da §7: 3 timed walls of the staged-decode generate, 512 prompt ids
  + 1 generated token, rate = 512 / median(wall)):
  - Linux wall: **35.6499 / 35.6478 / 35.6327 s** (median **35.6478 s**)
  - Linux throughput: **14.36 tok/s**
  - macOS bar: **11.74 tok/s**
  - **Ratio: 1.223x throughput (PASS)**
- **Informational 513 decode bench** (3 warmups x 10 reps, n=100):
  decode 8.07 tok/s median (mean 8.0894, sd 0.1398, min 7.94, max 8.51),
  ttft 1.0309 s (13.315 tok/s), e2e 4.8449 s. Consistent with the
  certified max_len 50 cell (8.245 tok/s; 10x-wider ctx DMA per step).

The Qwen ANE cell now passes all four bars at normal priority: decode
1.47x (8.245 vs 5.625), TTFT 0.845x latency (0.949 vs 1.189 s), e2e
0.699x latency (4.73 vs 6.72 s), and prefill-512 1.223x throughput
(14.36 vs 11.74 tok/s).

## 2. Parakeet cell: installed-pipeline profile vs macOS

The pipeline profile on the installed stack (mlx-omarchy main 27aba5211 /
bfe2ddc6d, omarchy-ane 5a22ee3, certified whole-encoder bundle `13c74423`
`140.1 ms`, libane-strict `d06222a8`, `CONTRACT_ANE_MODE=inprocess`, 3
warmups + 10 reps, quiet box):

| stage | Linux installed (ms) | macOS (ms, rep10) | delta (ms) | status / lever |
|---|---:|---:|---:|---|
| audio_load | 1.8 | ~2 | -0.2 | MATCH (PASS) |
| mel_frontend | 21.4 (clean ~22) | 13-15 | +6.4 to +8.4 | Profiling below: structural submit pattern; DFT kernel is 2.7 ms wall |
| encoder_ane (stage) | 142.2 (engine 140.1) | 136 (engine 113.12) | +6.2 stage / +27.0 engine | Owned by `AneClockM1` (ANE perf-state lever, needs jwm1 macOS window) |
| tdt_decode | 133.4 (loop 222) | 120 (CoreML floor) | +13.4 | Main's `vulkan_tdt_chain` (device-chained); fold-fusion falsified (+12 ms) |
| detokenize | 0.04 | ~ | 0.0 | MATCH (PASS) |
| **total pipeline** | **298.6** (min 297.4) | **271** | **+27.6** | Ratio 1.10x latency |

Correctness holds across every run: transcript sha256 `db501a8c…` exact
on all 10 reps, 104/104 tokens match, encoder hidden content sha256
`51830b6f…` matches certified pins.

Prior falsifications held (do not re-run):
- TDT fold-fusion (6->5 kernels/slot): branch `agent/jwm1-parity4-tdt-fuse`
  @ `e87f50c65` proved bit-exact but measured ~12 ms SLOWER (135.4 vs 121.9 ms
  min) because redundant per-workgroup recompute exceeded the dispatch-overlap
  saving (`receipts/2026-09-25-jwm1-parity4-falsifications-and-ane-regression`).
- mel DFT 256-thread component split: 2.1x slower (57.2 vs 27.5 ms / 10 reps);
  direct wall of the 64-thread `_dft_frames` on 3001x512 frames is 2.7 ms/rep
  (the earlier "11 ms" was a contention-polluted profile artifact).
- TDT chunk size: slots_per_chunk 64 vs 128 vs 256 is flat (schedule is
  slot-serial by LSTM dependency).

Stage breakdown confirmation via isolated eval probe (`mel_stages.py`):
see section 5.

## 3. GPU levers: GDN four-lane kernels + qmm coopmat prefetch / double-buffer

### A. GDN decode + prefill scan: 4 lanes per Dv row (commit `f0f7dcc3e`)

Prior state (`gated_delta_decode.comp`, `gated_delta_prefill.comp`): one
thread per Dv row holding the 128-float state in registers across the token
recurrence. At Dk=128, Dv=128, Hv=16, each head dispatched ONE 128-thread
workgroup (16 workgroups total), occupying only 2 workgroups per M1 GPU
core, with 128 sequential global/shared loads per token and no memory-level
parallelism (latency-bound at ~135 us profiled per decode token and ~1415 us
per prefill layer-pass).

New design:
- **LANES = 4 threads per Dv row**, each owning a contiguous 32-float
  slice of the row's state in registers (read once, written once).
- Workgroups remain 128 threads and cover 32 rows, so a head dispatches
  **4 workgroups** (64 workgroups total, 8 per core — 4x occupancy and
  4x memory-level parallelism).
- **Ascending lane-to-lane handoff**: the two dot products (kv reduction
  `s_in * g * k` and output projection `s_out * q`) are sequential float32
  chains over Dk in strict ascending order (elements 0..31 summed by lane 0,
  its partial sum passed to lane 1 via `subgroupShuffleUp(acc, 1u)`, lane 1
  continues through elements 32..63, and so on). The final row total is
  broadcast across the 4 lanes via two relative shuffles (`subgroupShuffleDown`
  by 1 and 2).
- **Exactness argument**: because each partial sum and each product is
  evaluated in the identical left-associated order as the one-thread-per-row
  form, every float32 intermediate is bit-identical to the prior kernel.
  The state update `ns = s + delta * k` and state stores are lane-parallel
  (each lane updates its own 32 elements independently).
- **Single-chunk prefill shortcut**: when prompt tokens T < 64 (all contract
  prompts are 10-18 tokens), `chunks == 1`, so pass 0 (the prefix snapshot
  pass) has no snapshot boundaries to write and wrote nothing to the final
  state buffer. Skipping pass 0 entirely when `chunks == 1` eliminates 18
  no-op dispatches per TTFT prompt.

### B. Small-M qmm coopmat: word prefetch + double-buffered staging (commit `c86b36224`)

Prior state (`qmm_coopmat.comp`): each (m-tile, n-tile) workgroup ran the k
reduction in steps of STEP_K=16. In each step, the lane loaded one packed
32-bit Q4 word from global memory, dequantized 8 nibbles into shared memory
`w_s`, waited on a workgroup barrier, issued `coopMatMulAdd` on the hardware
simd-matrix unit, and waited on a second barrier before the next step.
Global load latency was exposed 128 times per workgroup (7-18 GB/s observed
traffic, compute unit starved).

New design:
- **Chunk-ahead prefetch**: each lane's four packed words for the next 64-k
  chunk are loaded into registers a chunk ahead, overlapping global load
  latency with the current chunk's matrix steps.
- **Double-buffered shared staging**: two 16x32 float32 weight tiles in
  shared memory (`2 * STEP_K * TILE_N * 4 = 4096 bytes`), indexed by
  `slot = step & 1`.
- **Single barrier per step**: one barrier orders the staging stores
  before the matrix loads. The trailing barrier is eliminated: the next
  step stages into the alternate slot, so slow matrix readers on slot 0
  are never clobbered by slot 1 stores.
- **Hoisted direct-global A loads**: for non-bf16 activation views (f16,
  and the bf16 cast pass's f32 buffer), `coopMatLoad` on `mat_a` reads
  straight from global memory; both sub-steps' A loads are issued before
  the staging barrier, overlapping their latency with the dequant stores.
- **Exactness argument**: the hardware `coopMatMulAdd` sequence per output
  tile is identical (same 8x8x8 tile pairing, same k chunk order, same
  accumulator chaining); only the staging and global load scheduling moves.

### C. mlx-lm levers2 patch wiring (commit `c68c0d9c1`)

Wired `scripts/patch-mlx-lm-swiglu-eager.py` and
`scripts/patch-mlx-lm-qwen3next-qgate-split.py` into
`scripts/apply-mlx-lm-patches.sh` and `install.sh`. Drops 54 dispatches per
token on Qwen3.8-2B (swiglu folded into GEMV store epilogue; q/gate split
makes attention projections contiguous and groups them into the 4-weight
GEMV dispatch).

### D. Attribution matrix (4 legs, 3 rounds interleaved + bitwise dumps)

### Stage2 measurement status (in-flight background run on jwm1)

Driver: `/var/tmp/parity8/p8-stage2.sh` (pid 1266, nohup, log `/var/tmp/parity8/stage2.out`).
Legs:
- `installed`: `/var/tmp/jwm1-parity3-venv` (mlx-omarchy 27aba5211 + main patches)
- `base`: mlx-omarchy `bfe2ddc6d` (main tip: levers2 multi-weight GEMV + eager swiglu + q/gate split)
- `gdn`: mlx-omarchy `f0f7dcc3e` (base + GDN 4-lane decode and prefill scan)
- `cand`: mlx-omarchy `c68c0d9c1` (gdn + qmm coopmat prefetch/double-buffer + patch wiring)

Bitwise verification:
- `gdn_dump.py` / `gdn_compare.py`: evaluates `gated_delta_update_raw` (T=1, 3 reps) and `gated_delta_update` (T=13, T=70, masked) on fixed pseudo-random inputs and checks bit-identity.
- `qmm_dump.py`: evaluates `quantized_matmul` across prefill shapes (M=1, 13, 16, 17, 512; N, K in 2048/6144) and checks bit-identity.
- 10-pass pin target: `dbf704971617fdfc` on `cand`.

Results will land in `/var/tmp/parity8/gpu/` and `/var/tmp/parity8/stage2.out`.
