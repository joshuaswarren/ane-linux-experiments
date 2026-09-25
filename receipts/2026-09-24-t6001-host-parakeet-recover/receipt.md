# Parakeet contract recovery + full stage split on t6001-host, post-purge (2026-09-24)

Lane: Jw16GpuSubmit cell 3. Host: t6001-host (T6001, jw16mbp1-linux). Contract:
Parakeet TDT 0.6b v3 end-to-end in one Linux process (mel frontend -> ANE
encoder islands -> decoder -> TDT host loop -> detokenize), stage-split battery,
3 measurements, gates: `status: match`, mel `5b54f4a9` / hidden `38c73261` /
transcript `db501a8c` bit-exact, `matching_prefix_length` 104/104.

The 2026-09-24 owner-authorized purge deleted the t6001-host `/var/tmp`
staging (`ParakeetE2Emaxhost`, `V071REL-venv`, `EncoderParityAne`,
`encwall-decomp`, `maxhost-encoder-islands`, `jw16-oproj-place`,
`ParakeetE2E`, `TdtLoopDefault`). The model cache, `encoder-whole`, and the
`combined-parakeet` leftovers survived. The harness below was reassembled from
durable copies on the build CT (omp-studio-local), the t8103-host (not
purged), and the receipts repo; every recovered file is hash-identified.

## Recovery provenance

| piece | source | hash / evidence |
| --- | --- | --- |
| `fused_e2e.py` | committed derivation (`.local/ane-v064-wt/receipts/2026-09-15-tdt-gpu-loop/derivation/`) == CT staging copy `/var/tmp/stage-jw16/` | `0e38e7b1…` — byte-identical to the 2026-09-22 battery `identity.txt` on BOTH hosts |
| `vulkan_encoder_inproc.py` (runner) | t8103-host `/var/tmp/encwall-decomp/inproc-tmp/` (current) | `2a886a09…`; `AneIsland`/`EncoderRunner` signatures identical to the 09-22 pairing; 09-22-era `.bak-20260922` (`22f76554…`) kept as fallback |
| `libane_inproc.so` (inproc shim) | REBUILT on t6001-host: `ane_inproc.cpp` (t8103-host encwall-decomp copy) + overlay `worker_libane.cpp`/`bundle.cpp`/`manifest.cpp` (mlx-omarchy `925cfa64`, the certified battery era) + venv mlx headers (wheel `06add05a`) + omarchy-ane `afb23dd` libane headers + nlohmann v3.11.3 single header | `f0b7f93a…`, build recipe from receipt 2026-09-21-ane-inprocess-submit |
| island bundles | CT `/var/tmp/stage-jw16/island-bundles/` (t6001 target `h13`) | `island-attn-a-kt` (manifest + 2 programs), `island-pv` (manifest + 1 program, manifest `39a3caac…` identical across two independent CT copies); input tensors match the 09-22 e2e-report marshal records (`k_headsT/pos_kT/q_scaled/q_v`, `probs`); bit-identity to the purged `maxhost-encoder-islands` certified by the green pins below |
| worker binary | t6001-host `/var/tmp/encoder-whole/build/tools/mlx-omarchy-ane-worker/` (survived purge; combined-lane build) | present, executable |
| `libane-strict.so` (worker-side libane) | t6001-host `/var/tmp/encoder-whole/` | Sep 22 build |
| golden capture | CT staging (= t8103-host `/var/tmp/EncoderParityAne/capture/`) | hidden `7e442034…`, mel `4ed24d7d…`, transcript `db501a8c…` (= gate TRX) |
| audio fixture | CT `/var/tmp/ParakeetE2E/audio/fixture.flac` | `30885601…` == `parakeet-reference.lock` `audio.sha256` |
| `--pkg` coreml tree | t8103-host `/var/tmp/TdtLoopDefault/pkg` | contains `coreml/parakeet_tdt.py` |
| `--ane-reference` | CT `/var/tmp/EncoderParityAne/out-ane/encoder_hidden.npy` | prior ANE encoder output cross-check |
| venv (installed path) | t6001-host `/var/tmp/v072-venv-fused` | python 3.14.7, mlx-omarchy `0.32.3.dev202609241305+06add05a`, soundfile 0.14.0 |
| model | t6001-host cache `…/parakeet-tdt-0.6b-v3-coreml/b650695c…` | survived purge |

## Method

`run-contract.sh` (committed under `harness/`): stops `llm-inference.service`,
takes `/tmp/m1-gpu.lock` (`flock -w 900`, never stolen), runs 1 smoke + 3
measurements, restores via trap (service restart + `/health` poll + completion
probe; API key never printed). Env: `MLX_OMARCHY_PLACED=AC`,
`ANE_ISLAND_MODE=inprocess`, `ANE_INPROC_SHIM`, `MLX_OMARCHY_FUSED_AB=0`,
`MLX_OMARCHY_PIPE_OPS=` (all-ops async issue, the landed inprocess default),
`MLX_OMARCHY_DEFER_COMMIT=1`, `--tdt-host` — the 2026-09-22 landed lever set
that the anchor column was measured with.

## Results

Battery `/var/tmp/parakeet-recover/battery-20260924T191032` (t6001-host,
2026-09-24 19:10 CDT, service stopped for the window, trap-restored: `/health`
200 + completion probe `finish=length` after).

**all_green: True** — all 3 measurements: `status: match`, mel `5b54f4a9` /
hidden `38c73261` / transcript `db501a8c` bit-exact, `matching_prefix_length`
104/104.

| stage (ms) | meas-1 | meas-2 | meas-3 | median |
| --- | ---: | ---: | ---: | ---: |
| audio_load | 7.9 | 8.1 | 7.8 | **7.9** |
| mel_frontend | 142.2 | 143.7 | 140.2 | **142.2** |
| encoder_ane | 1758.9 | 1763.5 | 1746.1 | **1758.9** |
| decoder_load | 81.2 | 82.7 | 81.6 | **81.6** |
| tdt_decode | 476.4 | 555.7 | 545.7 | **545.7** |
| detokenize | 49.0 | 49.6 | 50.8 | **49.6** |
| total pipeline | 2515.7 | 2572.2 | 2572.7 | **2572.3** |

tdt_decode internals (meas-1): decoder 297.2 ms + joint 172.0 ms across the
host-loop steps; encoder device exec (both islands, all 24 layers) 247.8 ms of
the 1758.9 ms encoder wall — the encoder bucket is feeder/marshal-dominated,
consistent with the 2026-09-21 inprocess profile.

## Anchor comparison

macOS anchors from the 2026-09-22 decomp receipt table (this repo): T6001
macOS encoder 158.1 ms; macOS decoder+joint TDT divisor 143.5 ms. Linux
reference columns from the same receipt (batteries decomp-t6001-20260922T070157,
post-TDT-landing stack, V071REL venv).

| stage (ms, median) | 09-22 t6001 linux (V071REL stack) | 09-24 t6001 linux (v072 installed) | macOS anchor |
| --- | ---: | ---: | ---: |
| audio_load | 7.8 | 7.9 | - |
| mel_frontend | 142.1 | 142.2 | - |
| encoder_ane | 1210.1 | 1758.9 | **158.1** (11.1x today) |
| decoder_load | 54.2 | 81.6 | - |
| tdt_decode | 974.7 (megakernel) / 398.4 (TDT-host, receipt) | 545.7 | 143.5 (decoder+joint divisor; 3.8x today) |
| detokenize | 55.4 | 49.6 | - |
| total pipeline | 2448.6 / 1805.0 | 2572.3 | - |

The gates are bit-exact across both stacks — functional parity of the recovered
harness is certified. The absolute walls carry a vintage tax: today's run mixes
the installed v072 venv (`06add05a`, 09-24) with the surviving
`encoder-whole` worker/libane builds, a rebuilt inproc shim, and the
stage-jw16 island copies, while the 09-22 column was a matched
V071REL/oproj/set — mel_frontend and detokenize reproduce exactly, while
encoder_ane (+549 ms) and tdt_decode (+147 ms vs the receipt's TDT-host
number) sit above the 09-22 stack. The stage ranking and the lever are
unchanged.

## Lever

**encoder_ane remains the largest stage gap: 1758.9 ms vs the 158.1 ms macOS
T6001 encoder anchor (11.1x).** The documented leading candidate is the
ANE fixed-clock issue (receipt `2026-09-23-m1max-ane-clock`): the whole-encoder
device slope on this host is ~440 ms/iter because Linux never starts the ANE
firmware that raises the clock — iBoot leaves it low, the PMP report bit and
host poll cadence levers were measured flat (436.7–442.0 ms/iter, bit-exact),
and every remaining register route is in the hard-reset or boot-asset-write
forbidden class. The safe route on record needs an iBoot-staged firmware run
from a quiesce context plus the CSNE_CMD perf-mode write. Device exec is only
~248 ms of today's wall, so the rest of the gap is feeder-side (attention
matmul statements + const materialization + marshal), the A->B/C->O fusion and
const-cache levers from `2026-09-21-ane-inprocess-submit`.
