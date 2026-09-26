# jw16-levers6 part 2 — Parakeet non-encoder overhead: resident worker landed, stages split (2026-09-25)

Owner: Jw16Levers6 (consolidation). Device execution + profiling:
Jw16Levers6.Part2Resident on jw16 (T6001). Harness /var/tmp/parakeet-recover
(fused_e2e stage contract, 10.435 s audio fixture, Parakeet TDT 0.6b).
Starting point: total 1825 ms median (levers5 cutover), macOS denominator
264 ms (mel 15, encoder 140.9, tdt+decode 102). llm-inference was stopped
per window and restored with health 200 + real completion probe every time.

## 1. Resident-worker encoder path (the 834 ms cut)

The mlx-omarchy-ane-worker already ships `--serve` (serve_resident,
overlay/tools/mlx-omarchy-ane-worker/main.cpp, tree 925cfa64). New
`/var/tmp/parakeet-recover/ane_whole_worker_resident.py` runs it as a
detached daemon over FIFOs (/tmp/ane-whole-resident/{in,out}); the daemon
holds its own stdin/stdout O_RDWR so client exits never EOF it, releases
the device only on "quit", session-flock serializes clients, auto-respawns
on protocol death; `--shutdown`/`--status` CLI. `run-contract-resident.sh`
= run-contract.sh + 3 lines. Cross-process residency proven: two python
processes, one daemon (pid 1939), deterministic outputs, warm submit
433.7 ms. Nothing committed to mlx-omarchy yet (see open items).

## 2. Contract battery battery-20260925T193212 — ALL GATES GREEN

smoke + 3 meas: mel bit-exact, hidden pin `554a3d66f6885a35…`, transcript
`db501a8c…` prefix 104/104, status match, all_green on every run.

| stage (median ms) | before (levers5) | now | macOS |
|---|---:|---:|---:|
| audio_load | 6.7 | 6.7 | — |
| mel_frontend | 137.6 | 137.2 | 15 |
| encoder_ane | ~1275 | **440.7** (flat, worker elapsed 440) | 140.9 |
| decoder_load | 43.2 | 43.2 | — |
| tdt_decode | 333–368 | **255.4** (decoder ~154 + joint ~99) | 102 |
| detokenize | 7.9 | 7.9 | — |
| **total** | **1825** | **892.9** [899.1, 892.9, 889.0] | 264 |
| RTF | 0.175 | **0.0856** | — |

Total −51 %, encoder stage −65 % (the one-shot 458 MB bundle load +
session open now paid once per battery).

## 3. Exec-vs-wait profile (profile-20260925T194801)

Method: Jwm1Submit2's gpu_scheduler + dma_fence ftrace, mono clock,
PARAKEET_BEGIN/END trace_marker stage windows; 6190 lines, 280 GPU jobs,
run→done paired on fence (context,seqno).

| stage | wall | engine busy | host wait | jobs | run→done p50 |
|---|---:|---:|---:|---:|---:|
| mel_frontend | 140.2 | 22.9 | 117.3 | 1 | 22.9 |
| tdt_decode | 311.1 | 253.1 | 58.0 | 278 | 0.897 |
| audio_load | 9.4 | 0.6 | 8.7 | 1 | 0.65 |

Findings:
- **mel**: one GPU submission, engine 22.9 ms (macOS whole stage 15) — the
  ~117 ms is host-side, dominated by the harness unsetting
  MLX_OMARCHY_SPIRV_CACHE so every invocation recompiles pipelines.
  Warm-cache A/B = next lever, worth ~100 ms.
- **tdt**: 278 serial decoder+joint jobs, per-job engine 0.9 ms, zero
  overlap. The gap vs macOS 102 ms is per-job engine cost (~2.4x macOS
  per-op all-in); per-frame op fusion/batching is the lever. Host
  dispatch/sync is 58 ms total — not the gap.
- **encoder** 440.7 flat = pure engine window (part-1 receipt: kprobe
  dispatch 13–139 µs); the +195 ms client-side excess seen under
  ftrace/root is a transport artifact of that measurement mode, absent
  in user-run batteries.

## 4. Open items

1. Post-DART-containment comparison battery (Part2Resident queued): one
   run-contract-resident.sh vs today's 892.9/440.7 — the containment
   activation delta. (Executed after this receipt; see part-3 addendum.)
2. mlx-omarchy landing: ane_whole_worker_resident.py +
   run-contract-resident.sh promotion to the canonical Parakeet runner
   (needs a measured decision on daemon lifecycle across run-contract
   invocations; nothing committed yet).
3. Levers surfaced, not started: mel SPIRV-cache A/B (~100 ms), tdt
   per-frame op fusion (~150 ms class).

## Artifacts

`artifacts/part2/`: RESULTS.md (full), SHA256SUMS (32 files),
ane_whole_worker_resident.py, run-profile.sh, analyze_trace.py,
trace-analysis.json, stage-split.txt, battery-20260925T193212/,
profile-*/. Raw also on PVE /tmp/jw16-part2/, deployed scripts on jw16
/var/tmp/parakeet-recover/.
