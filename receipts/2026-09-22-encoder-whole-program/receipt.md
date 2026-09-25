# Encoder whole-program device gates — receipt (2026-09-22)

Owner: EncoderWholeProgramGates (sub of the encoder whole-program objective,
item 2). Scope: certified E2E x3 per device host from the BRANCH bytes, gate
runs, runtime-pin provenance. Non-goals honored: no new code beyond pin /
provenance entries, no M2, no GPU lanes.

## Branch bytes (verified byte-for-byte on both hosts before any run)

| artifact | source | sha256 / rev |
|---|---|---|
| mlx sources (staged tree) | mlx-omarchy `agent/encoder-whole-program` | `868fa7f1e` (vulkan_encoder.py `2dbaace1…`, build_whole_encoder_bundle.py `83c32747…`, bundle.cpp `e2c1559e…`) |
| libane sources | omarchy-ane `agent/encoder-whole-program` | `df5c553` (ane.c `f1294578…`, ane.h `cdd19a55…`) |
| whole-encoder bundle | program-0.anec, 458,018,816 B | `13c744231524d440b0a774155343df9ade0bbcbc37edc4b1ccf9698e580d5453` (byte-exact converter rebuild), manifest v4, operation `whole-encoder`, 13701 TDs, tile_shift 9 |
| libane-strict.so (production) | built WITHOUT `LIBANE_CONFIG_STRICT_BIND`: `gcc -shared -fPIC -O2 -Wall -I libane -I/usr/include/libdrm -I ane-uapi ane.c -o libane-strict.so` | `d06222a86f3bff26aaf1cec1223ade32f27cad84b994dccb1af9cca965a7da8c` (byte-reproducible; `nm -D` shows `__ane_init_shift`) |

Note on STRICT_BIND: an earlier `fdc5b670…` build WITH the define passes the
whole-encoder path identically (the container names every surface), but
island-attn-a-kt / island-pv bind surfaces positionally and must load, so the
production build ships without the define (flagged by EncoderWholeProgramLand,
verified here). The certified runs below use `d06222a8…`.

## m1max-host (m1max-host, T6001, kernel 7.1.6-1-1-ARCH, divisor 158 ms)

Staging: `/var/tmp/encoder-whole` (prepared mlx tree, build, bundle, libane).
Run: `fused_e2e` with `MLX_OMARCHY_WHOLE_ENCODER_BUNDLE=/var/tmp/encoder-whole/bundle`,
`ANE_ISLAND_MODE=resident-batch`, worker `mlx-omarchy-ane-worker` (branch
build), `--libane /var/tmp/encoder-whole/libane-strict.so`, GPU lock
`flock -w 1200 /tmp/m1-gpu.lock` (never stolen; coordinated with
DecodeQmmDequant's window).

Certified set r5-r7 (reports `m1max-host/e2e-report-r{5,6,7}.json`):

| rep | status | encoder_ane ms | ane_submissions | cpu_tensor_events | total pipeline ms | matching prefix | emissions |
|---|---|---|---|---|---|---|---|
| r5 | match | 440.578 | 1 | 0 | 2380.389 | 104/104 | 104 == native 104 |
| r6 | match | 440.303 | 1 | 0 | 2352.177 | 104/104 | 104 |
| r7 | match | 439.972 | 1 | 0 | 2368.622 | 104/104 | 104 |

- tokens_match / transcript_match / durations / frame_indices / mel bit-exact /
  encoder_hidden bit-exact: **all true, all reps**; max_abs_err 0.0.
- `encoder_hidden.npy` sha256 identical across reps: `554a3d66f6885a35…`;
  transcript sha `db501a8c…` == pin.
- ane mode: `encoder_gpu_ops 0`, `encoder_ane_ops 13701`, worker_starts 1,
  timeouts 0; bundle served: `parakeet-encoder-whole` (whole path, no island
  fallback).

**Anomaly vs divisor, flagged not explained:** encoder_ane 440 ms vs the 158 ms
island-chain divisor (ratio 2.8). m1-host whole-submit measured 141.4 ms vs its
113 ms divisor (1.25). The 440 ms is stable across 7 runs (r1-r7), across a
post-reboot quiet machine (llm-inference inactive, load 0.12), and across both
libane builds — so it is machine-state-independent as far as measurable here.
Context: it is still 2.7x faster than m1max-host's island-chain encoder stage
(1187.7-1228.7 ms, receipts/2026-09-22-encoder-pipelining). Possible factors
not ruled out: stock 7.1.6 driver vs m1-host 7.1.13, T6001 ANE clock state,
concurrent unmanaged llama-server on the GPU. No defect of the whole-program
path is implicated (output bit-exact, one submit, no timeouts).

Known first-load cost: each E2E process opens one resident worker session,
which validates the 458 MB bundle (full payload read + sha256 + `ane_init`
458 MB pread) inside the timed encoder stage. Independent legs that kept the
submit but paid the session open on a cold path measured 6.3-8.1 s stage walls
(EncoderWholeProgramLand out-r1..r3, also `status match`, submissions 1) — the
submit itself is 141 ms-class by CLI smoke. An mmap/reuse follow-up could hide
the validation; out of scope here.

Gates (built from branch bytes with `MLX_BUILD_TESTS=ON` on the staged tree;
`omarchy_ane_runtime_tests` does not link on m1max-host — out of the gate set and
untouched by this branch):

| gate | result |
|---|---|
| runtime (`omarchy_runtime_tests`) | rc=0 |
| primitive (`omarchy_primitive_tests`) | rc=0 |
| capsim (`omarchy_capability_sim_tests`, all 5 profiles: m1-honeykrisp-fork, m1-stock-no-coopmat, subgroup-size-64, small-shared-memory, no-cooperative-matrix) | rc=0 ×5 |
| bundle (`omarchy_ane_bundle_tests`) | 5904 assertions passed, 0 failed |

## Pins (mlx-omarchy `agent/encoder-whole-program`, commit `5c2d60577`)

`overlay/tools/mlx-omarchy-parakeet/share/mlx-omarchy/parakeet-1/parakeet-runtime-pin.json`:

| field | value |
|---|---|
| assets.libane["libane-strict.so"] | `d06222a86f3bff26aaf1cec1223ade32f27cad84b994dccb1af9cca965a7da8c` (was `56b46234…` @ omarchy-ane 6fa243ac) |
| provenance.libane | omarchy-ane `df5c553f3f60…`, built without LIBANE_CONFIG_STRICT_BIND, per-container tile-count unit `__ane_init_shift`, byte-reproducible on m1max-host |
| provenance.whole_encoder (new) | program-0.anec `13c74423…`, manifest v4 `parakeet-encoder-whole`, 13701 TDs, hwx graph `020428fca545648f…`, opt-in via `MLX_OMARCHY_WHOLE_ENCODER_BUNDLE`, not a shipped wheel asset |
| provenance.receipt | receipts/2026-09-22-encoder-whole-program.md (this receipt) |

Frozen expectations untouched: transcript `db501a8c…`, encoder_hidden
`38c73261…` family, mel `5b54f4a9…`, 104 emissions, cpu_tensor_events 0.

## m1-host (m1-host, T8103, divisor 113-122 ms)

Divisor correction (Main, 2026-09-22): the T8103 macOS divisor is **113-122 ms
depending on measurement path** — 122.1 ms CoreML-path median (15 reps after 3
warmups, outputs bit-exact vs gold; conservative for Apple because of boundary
fp32 casts) per `receipts/2026-09-22-t8103-divisor` (commit `90234a2`), with
the leaner-path native figures of 113.0-115.8 ms consistent with it. The
259.9 ms figure in 2026-09-21-encoder-wall-decomposition is discredited (no
surviving harness). On this basis the m1-host Linux one-submit 141.4 ms is
**1.16-1.25x** the macOS divisor — near parity, not past it.

Pending — host was held in macOS for the M2 serial window until ~15:15, then
flipped to Linux (plain reboot, no boot-config changes; divisor battery by
T8103DivisorMacOS completed first). Staging `/var/tmp/encoder-whole-m1-host`:
prepared mlx tree `868fa7f1e`, libane `df5c553`, bundle `13c74423…`,
`libane-strict.so` **byte-identical to m1max-host's** (`d06222a8…`, same gcc 16.1.1).

Certified set r1-r3 (reports `m1-host/e2e-report-r{1,2,3}.json`):

| rep | status | encoder_ane ms | ane_submissions | cpu_tensor_events | total pipeline ms | matching prefix | emissions |
|---|---|---|---|---|---|---|---|
| r1 | match | 141.913 | 1 | 0 | 13994.91 (cold SPIRV/pipeline compile) | 104/104 | 104 == native 104 |
| r2 | match | 141.509 | 1 | 0 | 2026.82 | 104/104 | 104 |
| r3 | match | 141.888 | 1 | 0 | 2073.777 | 104/104 | 104 |

- tokens / transcript / durations / frame_indices / mel / encoder_hidden: all
  bit-exact, all reps; `encoder_hidden.npy` sha256 `554a3d66f6885a35…` —
  **identical to the m1max-host runs** and to the prior m1-host direct-exec output
  family; transcript sha `db501a8c…` == pin.
- encoder_ane 141.4-141.9 ms vs the corrected T8103 macOS divisor 113-122 ms →
  **1.16-1.23x**, consistent with the direct-exec leg's 141.4 ms (1.16-1.25x).
  No 158/113-figure confusion survives in this receipt: m1max-host uses its own
  divisor, m1-host uses 113-122 ms with the range and both measurement paths
  stated.
- Gates on m1-host: runtime rc=0, primitive rc=0, capsim all 5 profiles rc=0,
  bundle rc=0 (`m1-host/gate-*.out`, `m1-host/capsim/`).

## Artifacts

- Evidence: `receipts/2026-09-22-encoder-whole-program/m1max-host/` (per-rep
  e2e-report JSON + logs, gate outputs, capsim per-profile outputs).
- Run scripts: `.local/m1max-host-whole-gates.sh`, `.local/m1-host-whole-gates.sh`,
  `.local/m1-host-setup-run.sh` (staged to each host under
  `/var/tmp/encoder-whole*/`).
- Host state: m1max-host staging `/var/tmp/encoder-whole` (gate binaries under
  `build/tests/omarchy/`); m1-host staging `/var/tmp/encoder-whole-m1-host`.
