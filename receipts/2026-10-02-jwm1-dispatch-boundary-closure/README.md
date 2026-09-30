# 2026-10-02 jwm1 decode: the dispatch-boundary family, measured and closed

Host jwm1 (T8103, G13G), Linux 7.1.13-3-2-ARCH, Honeykrisp as deployed. Decode is 0.89x macOS (44.35 / 44.08 / 43.94 vs 49.36 / 49.26 / 49.33 tok/s, n=5, temp 0). This receipt records four measurements that ask whether the remaining decode gap (~2.3 ms/token from ~350 dependent dispatches) can be recovered at the dispatch boundary. All four say no. No ledger cell moved; all remain losses.

| Id | Question | Result |
|---|---|---|
| H136 | Is an in-kernel software grid barrier cheaper than a dependent dispatch? | Yes: 0.72-1.24 us per barrier, 1-64 resident workgroups of 32 threads (vs ~12.4 us p50 gap between dependent dispatches in decode); 128-thread workgroups complete to G=192, time out at 256 (H137a). 0 ordering violations. |
| H137b | Does a two-stage persistent Q4 GEMV kernel (barrier between stages) beat two dependent dispatches? | Bit-identical to the unfused pair at every G that fits (8, 16, 32, 64, 80; 16 weight sets, mid and out). Slower at every G: 129 us/pair best (G=64) vs 104 us unfused. The real GEMV workgroup (128 threads, register-heavy) is resident only up to 80-95 workgroups on the 8-core M1, so the persistent kernel keeps fewer workgroups streaming than the 256-tile unfused dispatch. Parallelism-bound, not synchronization-bound. |
| H138 | Do independent GEMV dispatches issued without any barrier overlap? | No: 51.1-53.2 us/dispatch with no barrier vs 50.96-52.46 with a full barrier vs 51.1-51.95 with a compute barrier. Skipping barriers does not shorten GEMV-class dispatches. |
| H139 | Does touching the next stage's weights from inside the current dispatch warm them? | No: pair 104-106 us plain vs 139.5-140.2 with the touch (control touch of unrelated weights 144.7-145.8). Warming saved ~5 us of the 35-40 us the extra 2 MB read costs. |

Also: the jw16 lane (G13X) closed the RMSNorm-into-GEMV prologue (bit-exact, -29% decode) and the CDM barrier word (nondeterministic corruption from 256 tokens). Together: fusion, barrier-free issue, cross-dispatch prefetch, barrier-word trimming and norm prologues are all measured negatives on this driver/hardware. The ~12 us per stage between a 2.36 MB stage's 51 us and its ~40 us streaming time is intrinsic per-dispatch ramp, not barrier wait.

Incident: the first fused run exceeded the driver's GPU watchdog (unbounded-in-practice spin, residency ceiling below the requested grid); the asahi recovery path oopsed in drm_sched_job_done_cb and every later GPU job hung. jwm1 was rebooted once (announced to the M2 agent; no USB/m2proxy session live; M2 untouched), 0 failed units after. Rule adopted: spin bound 2^17 polls (~40 ms), one short submission per check, escalating grid, stop at the first timeout; after any "GPU timeout" in the journal treat the boot as poisoned and reboot before the next GPU run.

Code (negative record, not merged): mlx-omarchy branch agent/grid-barrier-floor (tools/dispatch-floor-bench gridbar mode; tools/q4-bw-bench pair-bench.cpp, pair-gen.sh, touch-gen.sh). Notebook entries H136, H137a, H137b, H138, H139 in the lab notebook (uncommitted by design), artifacts under artifacts/jwm1-parity/.

What is left for decode is outside kernel and scheduler work: per-dispatch ramp inside the driver/hardware (Mesa/firmware level), or a change in dispatch count that is bit-exact and larger than the ~3% ceiling estimated at H45. The ANE encoder (0.81x) waits on the M2 lane's T8103 firmware boot.
