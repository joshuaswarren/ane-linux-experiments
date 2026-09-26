# jw16 Parakeet Part 2 — Resident-worker encoder + non-encoder exec/wait splits

Owner: Jw16Levers6.Part2Resident, 2026-09-25. Host: jw16 (M1 Max T6001, Asahi Linux).
Harness: /var/tmp/parakeet-recover on jw16 (fused_e2e.py 636-line stage contract,
audio fixture 10.435 s, Parakeet TDT 0.6b). llm-inference stopped for each measured
window and restored with health+completion probe every time (probe finish=length).

## 1. Resident-worker encoder path (deliverable 1)

The mlx-omarchy-ane-worker on jw16 (tree 925cfa64, built binary
/var/tmp/encoder-whole/build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker)
already implements `--serve` (serve_resident in overlay/tools/mlx-omarchy-ane-worker/
main.cpp): named resident bundles, stdin jobs `submit NAME [--inline n=BYTES]
[--emit o]`, responses `out NAME LEN` + bytes + `job status=0 ... elapsed_ms=...`.

New files (all in /var/tmp/parakeet-recover on jw16, nothing committed to any repo):
- ane_whole_worker_resident.py — drop-in runner module (same AneIsland/EncoderRunner
  surface as ane_whole_worker.py). Spawns the worker as a DETACHED daemon over two
  FIFOs (/tmp/ane-whole-resident/{in,out}); the daemon inherits its own stdin/stdout
  O_RDWR so client disconnects never EOF it; it releases the device only on "quit".
  Session flock serializes clients; banner lines are skipped in-loop; a broken
  protocol kills + cleans the daemon for clean respawn. CLI: --shutdown / --status.
- run-contract-resident.sh — run-contract.sh with 3 changed lines (RUNNER default,
  HID-pin case pattern ane_whole_worker*.py, daemon shutdown at battery end).
  diff vs original verified to contain exactly those changes.

Cross-process residency proof: probe submitted twice from two separate python
processes - same daemon pid 1939, deterministic outputs, warm submit 433.7 ms wall.

## 2. Contract battery (deliverable 3) — battery-20260925T193212

4 runs (smoke + 3 meas), ALL GATES GREEN: mel bit-exact, hidden pin 554a3d66...,
transcript db501a8c..., status match, matching_prefix_length 104 (all_green: True).

Per-stage medians ms [runs]:
  audio_load   6.7  [6.7, 6.7, 6.6]
  mel_frontend 137.2 [136.0, 139.7, 137.2]
  encoder_ane  440.7 [440.7, 440.6, 440.7]   (worker elapsed_ms=440 each run)
  decoder_load 43.2 [43.7, 42.6, 43.2]
  tdt_decode   255.4 [264.1, 255.4, 253.4]  (decoder ~154, joint ~99 inside)
  detokenize   7.9 [7.9, 7.9, 7.9]
  TOTAL        892.9 ms [899.1, 892.9, 889.0]   RTF = 0.0856 (10.435 s audio)

vs baseline: total 1825 -> 892.9 (-51%), encoder 1275 -> 440.7 (-65%, the ~1.07 s
one-shot 458 MB bundle load + session open is now paid once per battery).
macOS denominator 264 ms total (mel 15, encoder 140.9, tdt+decode 102).

Note: even the smoke run shows encoder 440.5 - the battery inherited a warm daemon
from the first battery attempt that crashed at report-assembly (island.log schema
fix); cross-process residency is exactly what made that invisible.

## 3. Non-encoder exec-vs-wait split (deliverable 2) — profile-20260925T194801

Method: Jwm1Submit2's - /sys/kernel/tracing, events gpu_scheduler:* + dma_fence:*,
trace_clock mono, stage boundaries written as PARAKEET_BEGIN/END trace_marker from
a patched copy (fused_e2e_trace.py, markers via root because trace_marker needs
CAP_SYS_ADMIN; measured pipeline ran as root with user-side flock). 6190 lines,
280 asahi GPU jobs, run->done paired on fence=(context,seqno).

stage          wall_ms  busy_ms(engine) wait_ms  busy%  jobs  run->done p50/max  q->run p50
audio_load     9.4      0.6             8.7      6.9    1     0.648 / 0.648     0.026
mel_frontend   140.2    22.9            117.3    16.4   1     22.947 / 22.947    0.016
encoder_ane    634.8    0 (ANE, not drm) 634.8   -      0     -                  -
decoder_load   43.1     0               43.1     0      0     -                  -
tdt_decode     311.1    253.1           58.0     81.4   278   0.897 / 1.497      0.007
detokenize     19.9     0               19.9     0      0     -                  -

Findings:
- mel_frontend: exactly ONE GPU submission (battery report: vk_submissions=1);
  engine executes it in 22.9 ms (macOS whole stage: 15 ms). The 137-15 gap is
  ~117 ms HOST WAIT - in-process pipeline build/dispatch, not GPU. The harness
  env deliberately unsets MLX_OMARCHY_SPIRV_CACHE, so every fused_e2e invocation
  recompiles; a warm-cache or pipeline-cache run is the obvious lever.
- tdt_decode: 278 tiny jobs, per-job engine 0.9 ms (p50), no overlap (union 253
  ~= sum). The gap vs macOS 102 ms is dominated by per-job engine cost on 278
  serial decoder+joint submits (~2.4x macOS per-op all-in), host wait is only
  58 ms. Lever: fuse/batch ops per frame to cut the 278-job serial chain.
- encoder_ane under ftrace shows +195 ms CLIENT-side transport overhead
  (client 634.8 vs worker-internal elapsed_ms 439-440, identical engine time);
  absent in the user-run battery. Measurement-env artifact, noted not chased.

## Artifacts (this dir)
battery-20260925T193212/  (summary.json, identity.txt, logs, e2e-reports, shutdown log)
profile-194801/           (trace.txt, log, identity, e2e-report, trace-analysis.json, stage-split.txt)
profile-194512/ profile-20260925T193359/  (failed/intermediate attempts, kept)
ane_whole_worker_resident.py, run-profile.sh, make_trace_copy.py, analyze_trace.py
SHA256SUMS
