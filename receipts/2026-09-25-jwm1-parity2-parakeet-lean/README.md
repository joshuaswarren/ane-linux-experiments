# t8103-host Parakeet lean lane — stage profile, in-process ANE island, rejected levers (2026-09-25)

Owner: Jwm1Parity2. Host: t8103-host (M1 / T8103, Omarchy, kernel
7.1.13-3-2-ARCH, honeykrisp `7faf04c065c` ICD). Parakeet installed path:
whole-encoder ANE (bundle `13c744231524d440b0a774155343df9ade0bbcbc37edc4b1ccf9698e580d5453`,
one submit) + host control TDT loop + fused decoder/joint kernels.
Wheel `mlx_omarchy-0.32.3.dev202609242216+f252747`, libane-strict
`d06222a86f3bff26`. Prior certified split: receipts `2026-09-24-jwm1-gpu-parity`
(cell 2, warm 1572-1620 ms) and `2026-09-22-t8103-divisor`.

## 1. Correctness first (all gates bit-exact)

- GPU-resident TDT (control=gpu-loop) PASSED 3 reps on the installed path
  (2026-09-25 05:10 local): hidden 554a3d66f6885a3552d531d509bbd30d632d5bd424296028e8c1523f9f6f4ec4 x3,
  transcript db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790.
  The earlier "flock hang" was the wrapper exec'ing `/dev/shm/launch_audio_gpu.sh`,
  which the reboot cleared — not a flock deadlock. (Neutral: prior wrapper log.)
- In-process contract (3 warmups + 10 timed reps, ONE process, ANE session
  open amortized): all gates green every rep — transcript matches golden,
  tokens equal `token_ids.json`, and encoder_hidden content sha
  **51830b6ffe992568c9fd19a3636373fd36939e14ff998c558fb85038acbd13b8**
  equals BOTH certified run outputs (`combined-20260924T185005/out-2`,
  `combined-20260925T051045/out-1`). The inproc shim is bit-exact vs the
  certified pins across 13 submits.

## 2. Stage profile (installed path, fresh process per rep — the protocol that produced 1572-1620 ms)

| stage | warm ms | note |
|---|---:|---|
| audio_load | 9 | flac decode + mx.array |
| mel_frontend | 184-192 | ~130 ms of this is per-process kernel compile; warm in-process = 53-55 |
| encoder_ane (stage) | 697-716 | 628 ms resident session open (spawn+init+bundle) + 143 ms ANE exec |
| decoder_load | 63-66 | mlpackage parse + weight pack, per process |
| tdt_decode | 576-588 | 145 full steps x 2.07 ms + 146 skip joints x 1.59 ms; bare sync floor 0.333 ms |
| detokenize | 37-49 | tokenizer.json parse |
| total | 1572-1620 | vs macOS rep10 0.271 s |

KEY FINDING — protocol mismatch: macOS 0.271 s rep10 amortizes CoreML load in
one process; the Linux 1572-1620 figure pays kernel compile AND 628 ms session
open every rep. The matched boundary is in-process warm reps.

## 3. Matched in-process contract (new harness, one process)

| mode | warm total ms | tdt | enc stage | mel | note |
|---|---:|---:|---:|---:|---|
| resident-batch (worker) | 1596 baseline (fresh-proc) / 1569.7 (one-proc b4 A/B) | 583 | 703 | 186 | **repeat rounds on the same resident session cost ~4.8 s each** (whole bundle, one batch scope) — the certified per-process path never exercised round 2+ |
| inprocess shim | **935.8 median** (min 896.2) | 610 | 293 | 63 | open 482-555 ms once, submit 143 ms engine + ~130 shim |
| inprocess + TDT_BATCH=8 | 969.7 | 612 | 294 | 64 | batch path ran (joint_calls 153), no wall change |
| inprocess + jointb prefetch | 1100 | 751 | — | — | REJECTED: extra dispatch costs more than the skip it removes |

Cold first rep (in-process): 1054-1492 ms incl. compile + open
(macOS cold anchor 0.295 s). Still the dominant single cost.

## 4. TDT decomposition (skip call = 1.59 ms; where it goes)

dispatch-only (defer eval) 1.454 ms/iter — the cost is HOST-side python glue
in `run_step` (view creations + fast.metal_kernel marshaling + output
allocation), not GPU exec, not the sync (bare eval floor 0.333 ms), not the
argmax (24 us), not the 6 flag uploads (removing them changed nothing:
610.2 vs 612.6 — measured, flag-lean patch on the v072 vintage).
Next Parakeet lever: main's `_JOINT_WINDOW_SOURCE` speculation (6 slots,
weights stream once per window) which the v072 pkg vintage predates, plus
removing the per-step python loop (vulkan_tdt_chain). NOTE: the flag-lean
diff must be rebased onto main — applied blindly it would delete the
`joint_window` feature (caught in review, not landed).

## 5. GPU roofline probe (t8103-host, decode cell)

- Pure read kernel (512 MB fp16 `mx.sum`): **54.2 GB/s** achieved read on
  Linux. (Lazy-chain caveat noted; add-kernel probe invalid due to MLX graph
  folding — read-only sum is the honest number.)
- Decode arithmetic: weights 1.059 GB (`Qwen3.8-2B-mlx-4Bit`,
  snapshot 0867d98bfb174b042d88461c0e7c97b86b34b381) + KV reads
  => Linux 37.39 tok/s ≈ 43-46 GB/s achieved; macOS 47.05 tok/s ≈ 54.6 GB/s.
- VERDICT: the Linux "bandwidth-bound at ~43 GB/s" roofline is DISPROVEN as
  a wall — 54 GB/s is demonstrably reachable on this DRAM and macOS decode
  already achieves that rate on the same laptop. Remaining bucket = q4 GEMV
  kernel efficiency (honeykrisp quantized matvec vs Metal MLX q4 kernel).
- Prefill 0.68x and TTFT are compute-side buckets (coopmat GEMM / clock),
  not DRAM.

## 6. ANE session tooling

- `libane_inproc_whole.so` rebuilt against the current overlay (whole-era
  manifest with `tile_shift`; the Sep-21 shim refused it:
  "manifest: unknown field 'tile_shift'"). sha256
  `40fe99fd5ad9b2cdc8f97e85ee15afe0bde41371c4cf888e609bec8505ff9f4b`,
  built from overlay `mlx/mlx/backend/omarchy/ane/{worker_libane,bundle,manifest}.cpp`
  + `ane_inproc.cpp`. Client: `inproc-tmp/ane_inproc.py`
  (`InProcessAne(shim, libane, bundles{name:dir}, deadline)`; submit contract
  equals the resident session minus the child process; deadline + quarantine
  safety contract inherited, condition-variable wait — no busy spin).
- The 2026-09-21 inproc A/B numbers (island era) do NOT transfer to the
  whole-encoder path; measured fresh in section 3.

## 7. macOS window boot gate (one-shot macOS boot for captures)

Before the reboot mandated for the Qwen ANE macOS captures: `/boot` sits on
btrfs (`/dev/nvme0n1p5[/@]`), so the btrfs-v7 GRUB gate applied.
`grub-fstest /dev/nvme0n1p5` byte-compare vs on-disk:
vmlinuz `c9764582601a847d64943d1a19008c589e87b9e79c5ad416773dee6a8a05a17c`
(35.8 MB) and initramfs `e388d633628504f134c2ea554efd74adb69a3e1dd4df75f8434cf4805756ef8f`
(19.9 MB) — both byte-exact through the installed grub 2:2.14-1.1 modules,
matching the Sep-20 rebuilt `BOOTAA64.EFI` (`fc9ea5c61430562168a62aaca592f8e6721dfe59c404246dc98fc2d35019cb3d`).
`asahi-bless --next --set-boot 1` confirmed ("Macintosh HD"); one gotcha:
`--get-boot` prints the DEFAULT (Omarchy) even when next-boot is set, and the
first non-interactive bless prompt answered itself N — pipe `y` or verify.

## 8. Remaining buckets (named, none hidden)

1. TDT: python-loop removal / main-window speculation rebase (parakeet 935 -> ~600
   needs the ~1.45 ms/call host glue gone; 265 calls x 0.5 ms = the whole gap to macOS dec).
2. Encoder stage overhead on the matched protocol: 293 ms vs 143 engine
   (shim marshal/unpack) vs macOS 136 total.
3. mel_frontend 63 ms warm (v072 vintage; re-profile on main).
4. GPU decode: honeykrisp q4 GEMV kernel vs Metal q4 (section 5).
5. GPU prefill/TTFT: compute buckets.
6. ANE encoder whole-program 143 vs macOS 113-122: clock lever falsified on
   m1max-host (receipt 2026-09-23-m1max-ane-clock — PMP not running, perf
   registers are the hard-reset class); macOS-side `powermetrics --samplers ane`
   frequency capture during the grouped macOS window names the clock delta
   with evidence instead of assumption.

## 9. Handoff

- Contract harness: t8103-host `/var/tmp/jwm1-parity2/contract.py`
  (`CONTRACT_ANE_MODE=inprocess|resident`, `CONTRACT_PKG`, `CONTRACT_TDT_BATCH`).
- Lever pkg copy: `/var/tmp/jwm1-parity2/pkg-lever1` (flag-lean + 6-tuple;
  UNBASED on main — do not land as-is, see section 4).
- Receipts repo: this file. mlx-omarchy: NOTHING landed this run
  (deliberate — the decoder-step diff must be rebased onto `joint_window`
  first; the inproc island port onto `AneIsland` is designed in section 3/6).
