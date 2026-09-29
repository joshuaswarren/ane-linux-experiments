# jwm1 (M1, T8103) deployed Linux stack vs same-laptop macOS, 2026-09-29

What changed on jwm1 since the 2026-09-28 paired-legs receipt (receipts/2026-09-28-jwm1-macos-parity-legs):
1. mlx-lm q/k `rms_norm_scaled` routing and GDN decode-conv routing patches applied to the live venv (mlx-omarchy main 0bb09e7be, c81ee497c; both bit-identical, decode +2.0% and +1.5-2.0%).
2. `soundfile` installed (the live venv had only numpy; the Parakeet CLI's flac decode fell back to three ffprobe/ffmpeg spawns: audio_load 181 -> 4.7 ms; mlx-omarchy 560a64424).
3. Wheel rebuilt from mlx-omarchy main 560a64424 (was 42fbbc5f0, 44 commits behind, missing e.g. the 4-lane GDN prefill scan and lean elementwise kernels) and deployed to the live venv
   after an interleaved battery against the old wheel (raw/battery). The old venv is kept on jwm1 at /var/tmp/jwm1-venv-42fbbc5 for rollback.

Battery (control = old wheel + patches, candidate = new wheel + patches, interleaved, one flock hold per phase, loadavg(1m) < 0.4 at phase start), all pins identical
between arms (prefill ccb601895581d89f, decode64 7fe6badf4d560e25, decode128 da5568eeb4b6a1c1, Parakeet transcript sha db501a8c0803, status match in every run):

| cell | old wheel | new wheel | ratio new/old |
|---|---:|---:|---:|
| decode64 tok/s (n=15) | 40.64 | 40.73 | 1.002 |
| decode128 tok/s (n=10) | 39.69 | 39.78 | 1.002 |
| TTFT s (decode64 corpus, median) | 0.2286 | 0.1939 | 0.85 (1.18x faster) |
| prefill 512 tok/s (n=15) | 242.00 | 247.26 | 1.022 |
| prefill 1024 tok/s (n=5) | 241.44 | 247.26 | 1.024 |
| prefill 2048 tok/s (n=5) | 235.72 | 241.09 | 1.023 |
| Parakeet warm stage-sum ms (pipeline, n=10) | 365.6 | 374.0 | 1.023 (detokenize timer 10.4 -> 20.7 ms; cause not found) |
| Parakeet driver wall per run ms (n=10) | 940.6 | 691.1 | 0.735 (249 ms faster; what the untimed part consisted of was not analysed) |

Deployed live venv verification (after install; n=5 each; pins re-checked on the live venv itself) and same-protocol macOS cells from the 2026-09-28 window:

| cell | macOS (n=5) | Linux deployed (n=5) | Linux/macOS | pin |
|---|---:|---:|---:|---|
| prefill 512 tok/s | 345.31 | 247.26 | 0.716 | ccb601895581d89f |
| prefill 1024 tok/s | 345.76 | 247.34 | 0.715 | ccb601895581d89f |
| prefill 2048 tok/s | 341.80 | 240.31 | 0.703 | ccb601895581d89f |
| decode 64 tok/s | 49.36 | 40.61 | 0.823 | 7fe6badf4d560e25 |
| decode 128 tok/s | 49.26 | 39.83 | 0.809 | da5568eeb4b6a1c1 |
| decode 256 tok/s (5 x limit-1) | 49.33 | 38.91 | 0.789 | 828b55d6249d9679 |
| TTFT s (decode64 corpus) | 0.1248 | 0.1925 | 1.54x latency | - |
| Parakeet fixture, deployed warm: pipeline total incl. decoder_load (audio+mel+encoder+decoder_load+TDT+detok) | ~272 (CLI 'inference', n=10, excludes model load) | 374.4 / 378.4 / 389.2 (3 warm runs) | ~0.70-0.73 | db501a8c0803 match |
| Parakeet fixture, same boundary as macOS 'inference' (mel+encoder+TDT+detok; battery cand-arm medians 29.0 + 140.2 + 139.7 + 20.7 = 329.6) | ~272 | ~330 | ~0.82 | db501a8c0803 match |

No cell reaches 1.00x. Not re-measured here: whole-encoder ANE (138.9 ms vs macOS 113.24, unchanged) and the 6-clip Parakeet per-clip table (receipts/2026-09-29-jwm1-parakeet-corpus).
Rejected levers measured today, all logged in the private notebook and in mlx-omarchy receipts: gated barriers 1.002x; qmm coopmat 64-row 0.939x, K32 0.897x, K64 0.880x, SG4 0.978x;
CPU-frequency floor 1.0015x decode / -0.7% Parakeet; gated-norm fusion made ~1e-5 inexact (fixed from 36%) and not shipped.

Raw: raw/live (live-venv JSONs incl. Parakeet driver summary), raw/battery (per-phase JSONs and driver summaries), raw/*.sh, raw/h16-battery.log.

## Update (later 2026-09-29): bit-exact fused gated norm shipped, wheel 1daa1ad5d deployed

Change: mlx-omarchy a3be05040 (bit-exact `rms_norm_gated` kernel) + b9efdd92d (`patches/mlx-lm-qwen35-gated-norm.patch`, routed by default). Root cause found by measurement: compiler reassociation of two fmul chains
(`silu*normed`, and `value*norm*weight` where the reference kernel compiles `value*(norm*weight)`); the exp/sigmoid stage was bit-identical to `mx.exp`/`mx.sigmoid` throughout. Exhaustive gate sweep and rate check: 0 mismatches.
A/B vs the previous live stack (interleaved, digests identical): decode64 40.70 -> 41.66 (1.024, n=15), decode128 39.90 -> 40.58 (1.017, n=10); raw in `raw/gated-exact-ab`.
The deployed wheel is main-tip (ef05f2644) plus that change, so it also carries two earlier main prefill commits (`conv_dw1d.comp`, standalone silu chain); the prefill gain below is not from the gated-norm change.

Live verification after deployment (n=5 each, pins re-checked on the live venv; raw in `raw/gated-exact-live`):

| cell | macOS (n=5, 2026-09-28) | Linux live | Linux/macOS | pin |
|---|---:|---:|---:|---|
| prefill 512 tok/s | 345.31 | 256.23 | 0.742 | ccb601895581d89f |
| prefill 1024 tok/s | 345.76 | 256.29 | 0.741 | ccb601895581d89f |
| prefill 2048 tok/s | 341.80 | 250.27 | 0.732 | ccb601895581d89f |
| decode 64 tok/s | 49.36 | 40.66 | 0.824 | 7fe6badf4d560e25 |
| decode 128 tok/s | 49.26 | 40.80 | 0.828 | da5568eeb4b6a1c1 |
| decode 256 tok/s (5 x limit-1) | 49.33 | 39.86 | 0.808 | 828b55d6249d9679 |
| TTFT s (decode64 corpus) | 0.1248 | 0.196 | 1.57x latency | - |
| Parakeet warm pipeline ms (incl. decoder_load), 3 warm runs | ~272 (CLI inference) | 391 / 385 / 389 | ~0.70 | db501a8c0803 match |

Still no cell at 1.00x. Rollback venv on jwm1: /var/tmp/jwm1-venv-560a64424 (previous stack) and /var/tmp/jwm1-venv-42fbbc5 (the original installed wheel).
