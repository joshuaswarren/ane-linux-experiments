# 13-inch M1 (T8103): paired macOS run of the whole Parakeet encoder, 2026-10-11

Question: what is the macOS CoreML wall of the whole Parakeet TDT 0.6B v3 encoder on the same 13-inch M1 the Linux
cell was measured on, with the fixed harness (`encoder_bench.swift`, compute-unit configuration applied)?

| arm | rep 1 median (ms) | rep 2 median (ms) | pooled median, 30 reps (ms) |
|---|---:|---:|---:|
| cpuAndNeuralEngine (`ane`) | 111.62 | 111.52 | **111.56** |
| all | 111.61 | 111.68 | 111.66 |

Four arms interleaved (ane, all, ane, all), 3 warmups + 15 timed reps each, one synchronous `MLModel.prediction` per rep
over the whole encoder. MLComputePlan placement in every arm: ane 1345 ops, cpu 29 ops. The hidden output of every arm
is bit-exact against the Linux gold (0 mismatched words of 240000, `analyze.py`). Inputs are the Linux parity tensors
(features fp32 [1,3000,128], mask int32 [1,3000]); model: HF revision b650695c, `encoder.mlpackage`.

Linux cell of record (13-inch M1, exclusive window, five 20-call medians): 137.914 ms. Speed ratio Linux / macOS =
111.56 / 137.914 = **0.809x** (best Linux run 137.789 ms: 0.810x). The earlier corrected macOS reference (113.12 ms,
2026-09-23) reproduces within 1.4%.

Conditions (see `identity.txt`): macOS 27.0 (26A428), CoreML 3600.25.2; load average 2.76 at the start; two background system
services (audio and configuration daemons) used 76% and 40% of one core for the whole window and could not be stopped;
`caffeinate` held and system sleep disabled for the run (restored afterwards); no thermal warning recorded. The four arms
agree within 0.1%, so the background load did not move the timing. The Mac ran nothing else.

Files: `raw/run-*.json` (per-arm JSON with the sorted per-rep times), `identity.txt`, the harness `receipts/2026-09-22-t8103-divisor/encoder_bench.swift` (byte-identical to the file that ran, sha256 ac3c41cb8eb4), `macos-run.sh`, `analyze.py`. Host name and user name are replaced by placeholders.
