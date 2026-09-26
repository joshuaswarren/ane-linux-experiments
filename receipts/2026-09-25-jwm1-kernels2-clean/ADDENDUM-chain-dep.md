# Addendum: task-4 TDT turnaround located — chain-dep-bench first results

Owner: Jwm1Kernels2, 2026-09-25 late. Companion to
`receipts/2026-09-25-jwm1-kernels2-clean/` (steps 1+2).

Tool: `tools/chain-dep-bench/` on mlx-omarchy main (`b4024a6cf`, from branch
`agent/jwm1-chain-dep-bench`, first working version `0d51097d3`). Same
3-dispatch chain (grid-1 trivial writes, TDT fold/fold_proj/control shape),
every dependency encoding Vulkan offers, host walls, 31 reps, GPU lock held.

## Result (jwm1, G13G B1)

| chain encoding | wall med (us) | per-hop cost |
|---|---:|---:|
| one CS, no deps | 193.3 | — |
| one CS, full barriers | 191.9 | ~0 |
| one CS, event pair | 195.5 | ~0 |
| 3 CSes, timeline semaphores, one QueueSubmit | 448.3 | ~128 us |
| 3 CSes, timeline semaphores, three submits | 453.4 | ~130 us |
| host fence join per hop | 581.2 | ~195 us |

The ~93 us dependent command-stream turnaround seen per TDT slot
(958783d9) is the CS-boundary timeline-semaphore resolution: dependencies
inside one CS are free (barrier fields exonerated, confirming the earlier
mesa A/B), each dependent-CS hop costs ~128 us, and batching the CSes into
one QueueSubmit ioctl saves nothing — the boundary is the cost.

Fix levers, in ownership order:
1. mlx-omarchy runtime: keep dependent dispatches on one encoder/CS when
   they are already queue-ordered (TDT slot's fold/fold_proj/control are
   trivially one-CS material).
2. mesa-1 honeykrisp: CS-boundary semaphore resolution path (why a
   dependent CS costs 128 us — firmware semaphore round trip?).
3. asahi kernel/firmware submission path: only if (1)+(2) exonerated
   (report for approval first).

Driver hazard (new, repro documented in the tool's RESULTS file):
unisolated back-to-back vkCmdWriteTimestamp pairs around dispatches fault
the queue asynchronously — submit+waitidle pass, next submit reports
VK_ERROR_DEVICE_LOST. The mlx gpu_profiler's per-pair execution barriers
are load-bearing, not cosmetic.

## State of step 3 (decode QMM 66% -> 79%)

Not landed within this run. Assets produced: profiling wheel
(`out-prof/mlx_omarchy-0.32.3.dev202609252026+0abf33e6` with
MLX_OMARCHY_GPU_PROFILING, built from the hygiene merge), profiler NDJSON of
a full contract pass (`/tmp/prof-windows/prof-decode.jsonl` on jwm1),
analyzer + window harness committed here
(`harness/analyze_profile.py`, `harness/profile_decode_window2.sh`,
profiling venv `/var/tmp/prof-venv2`). Established en route: profiled
per-dispatch times are ~2x-polluted by the profiler itself (decode 22.07
tok/s profiled vs 37.3 unprofiled), so per-kernel ground truth must come
from isolated shape benches (q4-bw-bench pattern) with the profile used for
dispatch structure only. The steady-state submit groups in the profile
(s=114/115: ~150-172 dispatches/token — dispatch count already reduced by
the MULTI+fold stack) are the extractable shape set.
