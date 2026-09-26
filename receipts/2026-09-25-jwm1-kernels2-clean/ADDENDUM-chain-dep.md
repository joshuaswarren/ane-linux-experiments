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

## Addendum 2: v0.7.4 installed-from-release gate — FAIL (installer)

Ran the RepoReleaseSweep handoff battery (clean install.sh from the
published v0.7.4 tag, GPU matmul smoke, ANE smoke, 10-prompt compact
digest). FAILED at the installer patch stage, before any model ran:

```
/tmp/v074-install.sh: line 177: ~/.local/share/
mlx-omarchy/apply-mlx-lm-patches.sh: Permission denied
FAIL install.sh rc=126
```

Line 177 executes the curl-fetched patch script directly (`"$PREFIX/
apply-mlx-lm-patches.sh" "$VENV"`); curl wrote it 0644. This is the same
defect class af1222e44 fixed for a different callsite (invoke via `bash`) —
the fix is an ancestor of bb4901a80 but this second direct invocation
survived. On any machine without a +x leftover from an older installer
generation, v0.7.4 cannot install. Evidence: raw/v074-gate-fail.log
(full installer log). No promotion; release stays prerelease for
RepoReleaseSweep to re-cut with `bash "$PREFIX/apply-mlx-lm-patches.sh"`
at line 177 (or an explicit chmod). Note the digest control itself was
pre-verified this same day: my saved pass-1 full digest equals the
486872c4...aa5c control bit-exact.

## Addendum 3: v0.7.4 gate — installer fix proven, content green

Re-ran the battery with the published v0.7.4 wheel + the one-line installer
fix (bash-invoked patch script): install completed
(0.32.3.dev202609260237+bb4901a), GPU matmul smoke OK, ANE bundles present
in the installed wheel (mlx/share/mlx-omarchy/parakeet-1/bundles/*.anec),
and the 10-prompt compact digest (10x1x32, greedy, warmup 2, prefill 512):

- digest 486872c410629f1d4e019beb90c94d60229ec2abe154ae6b04712f9aedb5aa5c
  — DIGEST-MATCH vs the same-day same-box control, bit-exact
- decode 39.21 tok/s on the release wheel

(The first attempt's ANE-smoke snippet crashed on mlx.__file__ being None —
harness bug, replaced by the direct bundle check above.) Promotion waits
for RepoReleaseSweep's re-cut tag (42fbbc5f0, wheels rebuilding); the
official battery rerun on that tag is a formality — only install.sh line
177 differs from what this run proved.

## Correction (Jwm1Kernels3, mlx-omarchy 2d3a77b99)

The "keep TDT fold/fold_proj/control on one CS" lever above is VOID: the
production run_tdt_chain already records one CS per 64-slot chunk (1152
dispatches, 3 submits). The 958783d9 per-kernel table carried ~54us of
timestamp pollution per kernel (~27us/write); the real in-CS cost is ~25us
per dependent dispatch (RAW vs WAW: no difference) — mesa-owned, as is the
~128us CS-boundary hop this addendum measured (reproduced on current jwm1
mesa). Remaining TDT levers: bandwidth to the 79% ceiling + the two
mesa-owned dispatch costs. No mlx-omarchy runtime change needed.
