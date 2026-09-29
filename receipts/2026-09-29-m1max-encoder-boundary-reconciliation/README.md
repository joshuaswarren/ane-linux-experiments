# 2026-09-29 — M1 Max whole-encoder: timing-boundary reconciliation (Linux vs macOS)

Scope: jw16 (T6001) only. Sources: 2026-09-22 anomaly receipt (worker slope, m1max vs m1-host), 2026-09-22
whole-program certified runs (`encoder_ane` = worker `exec_ns` of one submit through the resident session),
2026-09-28/29 warm contract runs, macOS CoreML window of 2026-09-28 (this receipt series).

| metric (same program `13c74423`, same inputs, bit-exact outputs) | boundary | ms |
|---|---|---:|
| Linux `encoder_ane` in fused_e2e, certified r5-r7 (2026-09-22) | resident worker, one ANE submit + wait, no bundle load | 440.6 / 440.3 / 440.0 |
| Linux worker slope over iterations 1..32 (2026-09-22) | incremental per-submit time, session open excluded | 441.3 |
| Linux contract runs 2026-09-28/29 (n=3 each, ~12 runs) | as row 1 | 440.7-441.7 |
| macOS CoreML `ane` arm, whole encoder (2026-09-28) | one synchronous `predict` incl. CoreML dispatch, 33 CPU-placed ops (ane 1341 / cpu 33), I/O copies; 3 warmups + 10 reps | 138.18 (134.10-141.72) |
| macOS sustained, 200 reps (2026-09-22 DVFS receipt) | as above | 140.1 median |

Reconciliation for T6001: the two Linux boundaries agree to 0.2% (440.4 vs 441.3), so no boundary artifact
exists on this host; the per-submit and end-to-end numbers are the same quantity. The macOS boundary is looser
(it adds CoreML dispatch and 33 CPU ops) so it overstates macOS engine time, never understates it: the Linux
engine gap is at least 3.19x (441.0 / 138.18). The 3.1x "e2e-metric" vs 1.7x "amortized" split in the 2026-09-22
receipt belongs to the T8103 comparison (jwm1: e2e 141 ms vs slope 260 ms); that discrepancy is not
reproduced on T6001 and is owned by the jwm1 lane.

Cross-SoC ratios (macOS: T6001/T8103 = 138.18/113.12 = 1.22x; Linux slope: 441/260 = 1.70x) leave a Linux-only
T6001 penalty of ~1.39x on top of the shared ~2.3-3.2x gap. Root-cause candidates unchanged from the anomaly
receipt: ANE clock (macOS raises PLL_ANE0 through firmware; ASC is parked on Linux T6001, no AP-visible DVFS
register) and DART2 16 KiB-page translation cost (the same class of TLB thrash measured for the GPU on this SoC).
No parity claim: every encoder cell is a loss (3.19x).
