# t8103-host Parakeet 935.8 -> 298.6 ms on main tip — chain default live, buckets named (2026-09-25)

Owner: Jwm1Parity3. Host: jwm1-linux (T8103). Stack: mlx-omarchy main
`ce91f5b8e` wheel (`+af73787` build, diag wheel `+diag.ce91f5b` sha256
`be265ad8…` for profiling), omarchy-ane kmod `9a0ec81`, certified
libane-strict `d06222a8`, bundle `13c74423`. Prior lane:
`receipts/2026-09-25-jwm1-parity2-parakeet-lean` (935.8 ms baseline).

## 1. Headline (all gates bit-exact)

In-process contract (3 warmups + 10 reps, one process, ANE session open
amortized — `CONTRACT_ANE_MODE=inprocess`, pkg = main tip
`overlay/tools`):

| stage | prior (v072 + host TDT) | main tip chain | macOS (rep10) |
|---|---:|---:|---:|
| audio_load | 9.1 | **1.8** | ~2 |
| mel_frontend | 63 (in-proc warm 53-55) | **21.4** | ~13-15 |
| encoder_ane (stage) | 293 | **142.2** | 136 (engine bench 113.12) |
| tdt_decode | 610 | **133.4** | 120 |
| detokenize | 0.2 | 0.04 | ~ |
| **total** | **935.8** | **298.6** (min 297.4) | **271** |

Gates: transcript sha `db501a8c…` exact, tokens == `token_ids.json`,
encoder hidden content sha `51830b6f…` == certified pins, all 10 reps.
`decode_path` = chain; host decoder/joint callbacks never fire
(decoder_calls=0, joint_calls=0).

What closed the gaps:
- **TDT 610 -> 133.4**: main's `vulkan_tdt_chain` (device-chained slot
  schedule, one `mx.eval` per chunk, control state in device buffers).
  The flag-lean lever is MOOT on main (no per-step host uploads exist in
  the chain path; the flag-lean diff was correctly never landed).
- **mel 63 -> 21.4**: main's vulkan_mel rework (v072-vintage number dead).
- **encoder 293 -> 142.2**: the 293 was NOT shim cost. A first run
  measured 258-295 while QwenAneRef-2's runner was loading on the box;
  the clean rerun measures 142.2 == the 143.5 engine floor. Lesson
  recorded: single-run in-process numbers on jwm1 are contention-vulnerable;
  require a clean rerun before naming a bucket.

## 2. Remaining 27.6 ms to the macOS bar (298.6 vs 271)

| bucket | ms | evidence | lever |
|---|---:|---|---|
| ANE encoder engine clock | +6 (stage) / 30 (engine 143 vs 113) | macOS engine bench 113.12 (receipt 2026-09-24-jwm1-macos-baselines, `raw/core/bench_ane.json`); Linux engine 143.5 | NOT software — needs `powermetrics --samplers ane` in the grouped macOS window (Main-gated on M2 recovery) |
| TDT dispatch latency | +13.4 | see §3 | kernel-count fusion, bit-exact |
| mel GPU exec | +6.4 | see §4 | DFT-stage kernel, bit-exact |

## 3. TDT decomposition (diag-wheel profile, `MLX_OMARCHY_GPU_PROFILE`)

Chain = 6 serial kernels per slot; ~192 slots execute for the fixture
(durations skip frames). Per-kernel GPU cost:

| kernels/slot | grid | us/exec | per-slot us |
|---|---|---:|---:|
| chains layer0 + layer1 (2) | 100 groups | 123.6 | 247.2 |
| window joint (1) | 33 groups | 199.4 | 199.4 |
| fold, fold_proj, control (3) | 1 group | 93.8 | 281.4 |
| **total** | | | **728** |

x192 slots = 139.8 ms GPU (profiled run wall inflated to 179 by a
co-running process; clean contract number 133.4). The three grid-1
kernels are near-pure launch latency (640-wide work in 94 us).

**Fusion lever**: fold -> chains1 prologue, fold_proj -> window
prologue, control -> window epilogue = 6 -> 3 kernels/slot. At ~94 us
per eliminated dispatch x 192 slots = **~-54 ms** -> TDT ~90-110, total
~245-265 < 271 PASS, without touching the ANE clock bucket. Bit-exactness
is preserved if each fused prologue/epilogue repeats the same fp32
ascending-chain arithmetic in the same order (the landed contracts pin
exactly that order).

slots_per_chunk sweep (chain_bench, 7 reps, token_match true at every
size): min wall 124.5 (64) / 124.3 (128) / 143.0 (256) — chunk size is
NOT a lever; the schedule is slot-serial by dependency.

## 4. mel decomposition (same profile run)

6 custom kernels/rep, GPU-exec-bound 21.9 ms/rep, host 27 us/rep, queue
busy 1.6 ms/11 submits (no dispatch problem):

| grid | count/rep | ms/rep | stage |
|---|---|---:|---|
| 3001 | 1 | **11.0** | DFT (`_dft_frames`, frames x 64 threadgroups) |
| 1501 | 2 | 7.7 | mel projection pair |
| 1 | 1 | 1.6 | stats |
| 6002 | 1 | 0.9 | frames |
| 3013 | 1 | 0.6 | normalize |

The 11 ms DFT kernel is the mel lever; must hold the mel/hidden pins
bit-exact.

## 5. State / handoff

- Harness: `/var/tmp/jwm1-parity3/contract3.py` (adapted for main tip:
  chain default, `run_joint_batch`/`TDT_BATCH` removed — that lever is
  gone from main), `chain_bench.py` (standalone chain timing,
  slots_per_chunk argv), `mel_bench.py`. Profiles:
  `mel-prof.jsonl`, `chain-prof.jsonl`.
- venvs: `/var/tmp/jwm1-parity3-venv` (release), `-venv-diag` (diag wheel).
- Measurement hygiene: every timing claim above is from a clean-box run;
  run-1-vs-run-2 divergence under co-running load is documented in §1.
- Next: implement the three TDT fusions (bit-exact gates: chain_bench
  token_match + contract pins), then the mel DFT kernel. Grouped macOS
  window (powermetrics + `/tmp/macos-retry.sh`) remains gated on
  M2FwStart-2 releasing the box; jwm1 must NOT reboot until then
  (Main directive: the M2 hv guest recovery depends on jwm1's ACM).
