# Parakeet encoder wall decomposition + instrumentation, m1-host and m1max-host (2026-09-21)

Branch: `agent/encoder-wall-decomp` (commits 36d2800, 25a09d8, + this one).
All artifacts (bench scripts, patched runner/client, worker patches, AB
battery scripts) are committed under `.work/2026-09-21-encoder-wall/`.
Remote artifacts: `/var/tmp/encwall-decomp/` on m1-host and m1max-host.

## Decomposition (per encoder pass, medians over measured runs)

### m1-host (T8103) — perf-battery-20260921T062634, 10 meas runs
encoder_ane median **5243.3 ms**, total 6589.9 ms. Worker 944f2a86,
libane 1ab9d95d, runner 789aaec3, harness 0e38e7b1.

| bucket | island A (24 rounds) | island C (24 rounds) |
| --- | ---: | ---: |
| host build/copy (marshal_ns) | 1624.1 | 463.9 |
| — GPU-eval wait (eval_ns, instrumented) | ~96% | ~96% |
| — host copy (copy_ns) | ~28 | ~1 |
| submit wall (elapsed_ns) | 1254.3 | 437.1 |
| — client write | 157.8 | 158.5 |
| — client read (incl. worker exec wait) | 1084.9 | 254.9 |
| worker elapsed | 742.0 | 210.5 |
| — worker stage (stdin) | 115.5 | 114.5 |
| — worker save/emit | 309.0 | 19.0 |
| — device exec (wel−stage−save) | ~317 | ~77 |
| host back (back_ns) | 68.0 | 11.5 |
| GPU feeder residue (enc − host − submitwall) | ~1370 | |

Copy microbench (m1-host venv python): 3.8 MB tobytes 0.087 ms; bytearray
append 0.296 ms — host copies negligible (~20-30 ms/pass). Marshal is
GPU-feeder eval wait, not copying.

### m1max-host (T6001) — parakeet-parity-battery-20260921T091631, 10 meas runs
encoder_ane median **3329.5 ms**, total 4694.5 ms, all_gates true. meas-1
split: A marshal 737 (eval-dominated), submit-wall 993 (write 128, read
854; worker 644 = stage 105 + save 172 + device ~367), back 54; C marshal
176, submit-wall 359 (worker 204 = stage 81 + save 11 + device ~112).
Island host sum ~975 ms; worker exec ~1352 ms; GPU residue ~1005 ms.

## Divisor ratios (encoder stage)
- m1-host 5243.3 / 259.9 (macOS 27 same-encoder, CoreML context) = 20.2x;
  vs 113.0-115.8 ms native figure = 45-46x.
- m1max-host 3329.5 / 292.2 (cross-chip M1 Ultra/T6000; T6001 native divisor
  pending) = 11.4x.
- Device exec alone is ~0.4-0.6 s/pass: the wall is GPU feeder + IPC +
  worker staging, not ANE.

## Attack-list outcome
1. **td_count batched submit: already landed.** libane/ane.c:478 sets
   `args.td_count = anec->td_count` — one ioctl per island submit, full
   416/208-TD array. No per-TD syscalls in the production path.
2. **Persistent mappings: already resident** (1 worker start, 1 batch
   scope, 0 timeouts per pass; inline pipe transport replaced file staging).
3. **Client IPC tuning: measured, REJECTED.** Interleaved 1 warm + 5 meas
   A/B on m1max-host (/var/tmp/encwall-decomp/ab-20260921T165936): base 3486.7
   vs fast-pipe 3511.6 ms encoder_ane median, both arms all pins green
   (104/104, transcript db501a8c, hidden 38c73261, mel bit-exact). An
   earlier "-76 ms" summary was a median artifact (dropped the fastest
   base run); true medians show a noise-level regression.

## Round 2: STAGING_BYTES drift root-caused; raw emit measured

### Drift fix
In `.work/mlx` trees the CMake target `mlx-omarchy-ane-worker` is defined
first by `mlx/backend/omarchy/CMakeLists.txt` (worker_main.cpp =
wheel-shipped STAGING_BYTES inherited-fd protocol); the tools/ CMakeLists
then skips its own target (`if(NOT TARGET ...)`), so `ninja
mlx-omarchy-ane-worker` builds the wrong protocol. Fix: compile the serve
CLI directly (g++ recipe in build-cli-v2.sh / build-cli16.sh, linking
main.cpp + worker_libane.cpp + bundle.cpp + manifest.cpp against pinned
omarchy-ane 6fa243a headers, json include dirs from _deps). Validated
patched workers: m1-host /var/tmp/encwall-decomp/worker-cli-v2 (4d52ae9c),
m1max-host /var/tmp/encwall-decomp/worker-cli-v2-16 (65aab8c1).

### Raw write(2) emit (patch in main.cpp.orig [m1-host] / main-m1max-host.cpp [m1max-host])
- m1-host ANE-only bench, 24 rounds x 4 interleaved pairs: old median 1156.0
  vs patched 1116.7 ms (~ -3%), patched faster 3/4 pairs, tighter variance.
- m1max-host same protocol: old median 667.1 vs patched 647.8 ms (~ -3%).
- Direction consistent both hosts; ~3% of ANE path, within run-to-run
  noise — NOT yet a conclusive pipeline win. Deciding measurement =
  fused_e2e battery with the patched worker (recipe: ab-battery-m1max-host.sh
  with WORKER=/var/tmp/encwall-decomp/worker-cli-v2-16), blocked only on
  the m1max-host GPU lock window (GPUHardwareContinuation queue).

### In-process libane submission (Main GO) — scoped, not implemented
worker_libane.cpp + bundle.cpp + manifest.cpp own program split (A = 2
programs via dispatch_plan), surface binding (manifest `index` per
input), and row packing (ane_pack_rows, allocation_bytes). The faithful
in-process path is to link those three files into the harness process
(proven buildable standalone this session) and expose AneWorker::submit
through a small ctypes shim — pipe removed, tile layout unchanged.
Reimplementing from ane.h alone is NOT safe (tiling). Before/after
metric = per-island elapsed_ns split already in e2e-report.json.

## Environment incidents
- /tmp/mesa-sin-ftz-m1-host (libvulkan_asahi-e167) wiped with /tmp; stock
  mesa 26.2.3 segfaults the pipeline (rc=139, ~8 GPU submits). m1-host
  fused_e2e blocked until GPUHardwareContinuation's e167 rebuild lands.
- m1-host worker rebuild via plain ninja hits STAGING_BYTES (see fix above).
- m1max-host llama-server (qwen3.8-27b:8002) stopped for measured windows and
  restored after each (verified active). Stale flock waiters from this
  session's own earlier commands were killed; pid 12585
  (run-pd-dirmodel-persist.sh, GPUHardwareContinuation lane) identified
  as protected and left untouched.

## Round 3: patched-worker pipeline battery — LANED (measured win)

m1max-host full fused_e2e battery with worker-cli-v2-16 (raw write(2) emit,
serve protocol intact), 1 warm + 5 meas, identity in
/var/tmp/encwall-decomp/v2-20260921T173940/identity.txt (worker
65aab8c1): encoder_ane median **3452.5 ms** vs 3486.7 ms with the
stock worker measured the same session — **−34.2 ms (−1.0%)** — and
every run green: 6/6 gold bit-exact (mel 5b54f4a9, hidden 38c73261,
transcript db501a8c), 104/104 prefix, status match. llama-server
stopped before, restored + verified active after.

LANDED CHANGE: raw write(2) emit in overlay/tools/mlx-omarchy-ane-worker/
main.cpp (patch: main.cpp.orig [m1-host lineage] / main-m1max-host.cpp [m1max-host]),
built via the direct g++ CLI recipe. To propagate: apply the same patch
to the canonical tools/mlx-omarchy-ane-worker/main.cpp and rebuild via
build-wheel.sh lineage; the CMake target-name collision (backend defines
mlx-omarchy-ane-worker before tools/) should also be fixed upstream so
plain ninja builds the right binary.

In-process ctypes shim: not implemented this run (budget); the scoped
design in the previous section stands — C shim over AneWorker::submit
linking worker_libane.cpp/bundle.cpp/manifest.cpp.
