# Parakeet end-to-end decomposition + audio-fast-path landing, both hosts (2026-09-22)

Lane: ParakeetE2EParity. Branch of this repo: `agent/parakeet-perf-worker-lever`.
Raw batteries (e2e-report.json per run, logs, identity files): archived at
`~/.local/state/omarchy-private-evidence/receipts-raw-2026-09-22-parakeet-decomp/`
(maxhost-decomp-raw.tgz, m1host-decomp-raw.tgz). Hosts named m1max-host (T6001) and
m1-host (T8103) below.

## Stack under test (current, per receipts/2026-09-21-ane-inprocess-submit)

In-process ANE island submission (`ANE_ISLAND_MODE=inprocess`, shim
`libane_inproc.so`), cached-BO ane.ko (`writecombine=N` verified on m1-host),
const batching + zero-copy readback, all-ops async issue on m1max-host only
(`MLX_OMARCHY_PIPE_OPS=`; m1-host e167 driver serializes pathologically under
all-ops and keeps the conv-only default). `MLX_OMARCHY_FUSED_AB=1` is currently
BROKEN on m1max-host: the runner's A->B splice check rejects the committed
encoder source ("layer 0: producer of matrix_bd_5_cast_fp16 is not an add
statement") — the exact command from last night's green 1233.0 ms battery now
fails, with every input file bit-identical (sha-verified). All numbers below are
FUSED_AB=0 (encoder_ane reads ~1210 ms on m1max-host, consistent with the
unfused 1233/1310 stack). EHC should reconcile the out_ab package/source state;
this is not a Parakeet-lane defect.

m1-host batteries require `VK_DRIVER_FILES=/var/tmp/mesa-e167-m1host/icd.json`
(stock mesa 26.2.3 segfaults rc=139 at ~8 submits, reconfirmed today).

## Method

`parakeet-e2e-decomp.sh` (this directory, deployed to both hosts at
`/var/tmp/encwall-decomp/`): interleaved A/B around ONE landed change
(soundfile audio fast path), 1 smoke + 3 meas per arm, full e2e via
`fused_e2e.py` on the certified per-host stack. Gates per run: status match,
104/104 prefix (p104), mel `5b54f4a9`, hidden `38c73261`, transcript
`db501a8c` all bit-exact. ALL RUNS ALL GREEN on both hosts, both arms.

## Landed change: soundfile audio decode (designed-in fast path activated)

`fused_e2e.py::decode_flac` already prefers `soundfile.read(dtype="int16")`
over the ffmpeg subprocess; the venvs simply lacked the package. Installed
`soundfile 0.14.0` into `/var/tmp/V071REL-venv` (m1max-host) and
`/var/tmp/<m1-v072rc1>/venv` (m1-host). FLAC is lossless, so int16 PCM is
identical; transcript pins confirm end-to-end identity.

| host | audio_load A (ffmpeg) | B (soundfile) | delta | total |
| --- | ---: | ---: | ---: | ---: |
| m1max-host | 76.9 ms | 7.5 ms | **−69.4 ms** | 3174.7 → 3115.8 ms |
| m1-host | 173.3 ms | 9.5 ms | **−163.8 ms** | 4910.9 → 4660.5 ms |

(m1-host A-arm audio was noisy — 133-273 ms — the delta is conservative.)

## Per-stage decomposition (medians, current stack, post-landing arm B)

| stage (ms) | m1max-host | /T6001 encoder 158.1 | m1-host | /T8103 encoder 113.0 |
| --- | ---: | ---: | ---: | ---: |
| audio_load | 7.8 | — | 9.5 | — |
| mel_frontend | 142.1 | 0.90x | 185.8 | 1.64x |
| encoder_ane | 1210.1 | **7.65x** | 3505.6 | **31.02x** |
| decoder_load | 54.2 | — | 83.2 | — |
| tdt_decode (loop + decoder/joint) | 974.7 | 6.79x* | 833.5 | 5.81x* |
| detokenize | 55.4 | — | 40.5 | — |
| total pipeline | 2448.6 | vs macOS full | 4660.5 | |

*macOS decoder+joint TDT loop divisor 143.5 ms; linux `tdt_decode` wall also
includes one-time per-process metal-kernel transpile (see below), so the
steady-state loop ratio is lower.

Totals to beat: m1max-host 2448.6 ms (was ~2578 with fused AB + 69 ms slower
audio), m1-host 4660.5 ms (was ~4911).

## Where the non-encoder time goes (measured this session)

Probes in this directory (run on both hosts under `/tmp/m1-gpu.lock`, all
source sha-recorded in identity.txt):

- `probe_tdt_step.py`: per-step wall on the real fixture encoder output.
  m1max-host: LSTM step 2.25 ms, joint-only step 1.58 ms; m1-host 2.57/1.51 ms.
  The `mx.eval` after the dispatches adds ~0.005 ms — the wall is inside the
  dispatch path itself, not host-argmax or the redundant eval.
- Per-step cost scales with DISPATCH COUNT, not FLOPs: the fused_e2e loop is
  104 emissions x 5 dispatches + ~42 silent frames x 2 = ~604 dispatches.
- `probe_tdt_overhead.py` could not run (trivial MSL kernel outside the
  backend's transpiler subset).
- `probe_tdt_gpukernel.py` (m1max-host, eval after each dispatch): chains
  0.51 / fold 0.43 / proj 0.90 / joint 0.89 ms — each dispatch carries a
  ~0.4 ms pipeline round trip regardless of work (fold does almost nothing).
- Negative results, all bitwise-clean where applicable:
  - threadgroup split of fold/proj (640 -> 10x64): 0 change (2.416 both arms).
  - `TDT_JOINT_THREADS` 128/512/1024 sweep: full step 2.21-2.30 ms (flat).
  - non-rtmod libmlx (v068REL venv): 2.23/1.58 ms — the rtmod instrumentation
    in the v071 build costs nothing measurable.
  - proj+joint single-dispatch fusion, two variants (single-threadgroup and
    redundant-proj-per-group, both bitwise 0/200 mismatches vs stock):
    4.59 ms and 3.55 ms vs stock 2.35 ms — the fused kernels' own execution
    more than eats the saved round trip. ABANDONED; variants deleted.
- One-time cost: `tdt_decode` wall (975 ms m1max-host) far exceeds the
  steady-state step math (~104x2.25 + 42x1.58 ≈ 300 ms) — the remainder is
  first-use metal_kernel transpile/compile per process plus loop control.
  Not amortized in a single-shot pipeline; macOS CoreML pays an equivalent at
  load.

## Conclusion / next levers

The TDT loop is dispatch-count x ~0.4 ms pipeline-round-trip bound on the
Vulkan backend, plus one-time kernel compile. The levers that would actually
move it are backend-level: (a) cheaper per-dispatch submission (batch command
buffers / avoid per-op fence round trip), or (b) whole-loop batching of silent
frames (state is constant between emissions, so each silent run's joint calls
are independent and could issue as 2 batched dispatches instead of 2x len).
Both are mlx-omarchy backend work, not runner patches — every runner-level
fusion variant tried today was slower.
