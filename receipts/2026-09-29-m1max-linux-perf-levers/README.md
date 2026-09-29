# 2026-09-29 — M1 Max (T6001) Linux performance levers landed after the macOS pairing

Follows `receipts/2026-09-28-m1max-macos-parity-legs` (all seven paired GPU cells and the
whole encoder were losses to macOS). Host m1max-host, Linux 7.1.6, same protocol as the pairing
(n=5 processes/passes, greedy, one prompt, warmup 1). Every change below is bit-identical by
construction and was gated on (1) output-bit hashes of the affected ops against the previous
wheel, (2) `ordered_records_sha256` identical in every measured cell, (3) the Parakeet contract
`all_green` (mel/hidden/transcript pins). The 2026-09-28 Linux medians are the baseline.

## Findings that directed the work
- Per-module split of the 2.38 s prefill-2048 (eval-synced, module-level): MLP 852 ms, GDN mixers
  724 ms, attention mixers 231 ms, lm_head over all 2048 positions 464 ms (the bench evaluates full
  logits); reconciles with the measured wall within 0.4%. macOS on the same machine: mixers 2.0-2.3x
  faster, MLP/lm_head 1.27-1.29x faster.
- The general elementwise kernel and the fused-chain interpreter run at 0.25 ns/element
  (~4 Gelem/s, 32 GB/s) independent of the op; the 16-bit vec path runs at 0.016 ns/element.
- Decode is submit-latency bound in stepwise loops: Parakeet TDT does 278 submit+wait round trips at
  1.38 ms each.

## Landed (mlx-omarchy main)
| commit | change | evidence |
|---|---|---|
| 00400ea7a | lean `-DLITE` builds of elementwise.comp for ops 0-10 | f32 mul/add/exp at 12.6M elements 3.16 -> 0.35 ms (8.9x); 365/365 output hashes identical |
| 98650249f | standalone silu chain -> swiglu.comp `SILU_ONLY` | compiled nn.silu [1,2048,6144] bf16 2.13 -> 0.22 ms; 455/455 hashes identical |
| 7addbbe9d | depthwise 1-D conv kernel (conv_dw1d.comp) | conv [1,2051,6144] bf16 2.93 -> 0.53 ms; 494/494 hashes identical (padded/strided/dense controls stay on conv.comp) |
| c94baca86 | default `HK_SUBMIT_POLL_US=2000` at device init | Parakeet tdt_decode 341 -> 254 ms (-25%) with the driver below |
Refuted and dropped: scalar-register fused-chain interpreter (2.13 -> 2.59 ms, slower);
HK_APPBAR diagnostic (dependency-tracked barrier is already in the installed driver lineage).

## Driver (joshuaswarren/mesa-1, branch `jw16/submit-poll-on-flush17f`)
`2a9762ef6ec` (installed dependency-tracked CDM barrier lineage) plus the three
`hk/submit-latency` commits (opt-in bounded syncobj poll with backoff). Installed as the system ICD
`libvulkan_asahi.so.poll9d949d4` (sha256 `eaab047e979e...`), previous ICD JSON backed up;
previous driver binary left in place. No mesa-1 main merge: main's history diverges from this lineage.

## Result (production stack, no env overrides; digests identical to baseline in every cell)
| cell | 09-28 baseline | now | macOS | now/macOS |
|---|---:|---:|---:|---:|
| decode 64 tok | 80.40 | 82.28 | 180.01 | 0.457 |
| decode 128 | 79.49 | 81.34 | 179.28 | 0.454 |
| decode 256 | 78.28 | 80.20 | 178.28 | 0.450 |
| decode 512 | 76.11 | 78.02 | 177.12 | 0.440 |
| prefill 512 | 753.9 | 785.0 | 1327.2 | 0.591 |
| prefill 1024 | 832.6 | 878.2 | 1355.8 | 0.648 |
| prefill 2048 | 862.7 | 887.5 | 1379.6 | 0.643 |
| Parakeet warm total (10.4 s fixture, whole encoder) | 913.7 ms | 770.9 ms | 261 ms inference (ane arm) | 2.95x slower |
Parakeet stages now: mel 38.6, encoder 441.0 (macOS 142), decoder_load 44.3, tdt 233.4 (macOS 103),
detok 7.9. Every cell is still a loss against macOS; no parity is claimed.

## Remaining gaps by size (Linux minus macOS)
Encoder 300 ms (ANE clock; needs firmware perf-mode, ASC parked on T6001), GEMM 1.27x slower
(prefill Δ ~290 ms), SDPA prefill 22.7 vs 5.5 ms per layer (no fused prefill kernel),
gated_delta_update 9.6 vs 3.7 ms per layer, decode per-dispatch latency (405 tiny dispatches/token).

## Addendum (later 2026-09-29): dependency gating, read/write-split tracker, gated norm; PR to omacom/mesa
| commit / change | what | evidence |
|---|---|---|
| mlx-omarchy 242d4f409 | `MLX_OMARCHY_GATED_BARRIERS` default on | 8 interleaved pairs of the full 10-prompt x 10-pass contract (16 runs), digest `dbf70497` in every run, +2.9% decode; jwm1 (T8103) gated the default too: identical digests, no gain/regression (receipt f54ceb49) |
| mlx-omarchy ec02d565b | tracker splits read/write bindings via SPIR-V readonly/writeonly reflection | d64 84.46 -> 85.66 (+1.4%), digests identical |
| mlx-lm gated-norm patch (`patches/mlx-lm-qwen35-gated-norm.patch`, applied to the serving venv) | RMSNormGated 6 dispatches -> 1 (90/token) | with the tracker: 8 interleaved pairs, control 84.6-85.1 vs candidate 88.7-89.4 tok/s (+4.9%), all 16 digests `dbf70497` |
| mesa (joshuaswarren/mesa-1 `jw16/omacom-pr`) | curated 11-commit set rebased on omacom/mesa main | omacom/mesa PR #3; rebased driver re-validated: digests identical, decode 88.57 vs 88.21, prefill 900.9 vs 895.7, Parakeet contract green |
Refuted: forcing coherent device loads/stores does not make the USC-only barrier bit-exact (arm C corrupt, 76.5 tok/s) and costs -27% alone (arm D 59.8): the required CDM barrier bits carry kernel-completion ordering, not only cache visibility; the barrier-free ceiling is 135.6 tok/s (corrupt).

Production stack now (no env overrides, digests identical to the 09-28 baseline in all seven cells):
| cell | 09-28 | now | macOS | now/macOS |
|---|---:|---:|---:|---:|
| decode 64 | 80.40 | 88.21 | 180.01 | 0.490 |
| decode 128 | 79.49 | 87.62 | 179.28 | 0.489 |
| decode 256 | 78.28 | 86.61 | 178.28 | 0.486 |
| decode 512 | 76.11 | 84.16 | 177.12 | 0.475 |
| prefill 512 | 753.9 | 791.3 | 1327.2 | 0.596 |
| prefill 1024 | 832.6 | 883.0 | 1355.8 | 0.651 |
| prefill 2048 | 862.7 | 895.7 | 1379.6 | 0.649 |
| Parakeet warm total | 913.7 ms | ~795 ms | 261 ms | ~3.0x slower |
Every cell is still a loss against macOS. Remaining decode structure: ~315-370 dependent dispatches/token at ~4.5 us saved per removed dispatch; barrier-free ceiling 135.6 tok/s.
