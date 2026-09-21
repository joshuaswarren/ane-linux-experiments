# 07 — Interleaved B/C/C/B replication: NEUTRAL verdict

**Lane:** `ParakeetPerformance`, branch `agent/parakeet-perf-worker-lever`.
**Run:** `BCBC-20260921T073623` on jwm1, lock inode 27, held ~166 s,
released and verified free (flock readback) at 12:39:31Z; runid-stamped
RELEASE sent to EncoderHardwareContinuation.
**Order:** B1 → C1 → C2 → B2 (interleaved, counterbalanced).
**Protocol:** warm + 5 measured per pass, `ANE_RESIDENT_PROFILE=1`,
**all 20 measured runs kept** (no runs-2-5 cherry-pick per Main).

## Result — NEUTRAL (pre-registered rule applied)

| pass | worker | encoder_ane median | gates |
|---|---|---:|:-:|
| B1 | base `f039e5fc` | 5208.376 ms | 5/5 ✅ |
| C1 | lever `afd612c4` | 5178.859 ms | 5/5 ✅ |
| C2 | lever `afd612c4` | 5234.906 ms | 5/5 ✅ |
| B2 | base `f039e5fc` | 5127.323 ms | 5/5 ✅ |

| paired comparison | delta |
|---|---:|
| **C vs B pooled** (the lever effect) | **+68.892 ms** |
| B1 vs B2 (arm-order drift, same binary) | −81.053 ms |
| C1 vs C2 (arm-order drift, same binary) | +56.047 ms |
| noise band (3.7 % of stage, pre-registered) | ±190 ms |

**|+68.9| < 190 → NEUTRAL.** The arm-order drift between identical
binaries (−81 ms, +56 ms) is LARGER than the supposed lever effect.
The earlier single-shot −44 ms did not replicate; in this counterbalanced
design the lever median is slightly slower, not faster.

**Per Main's directive: labeled NEUTRAL, bench receipt retained, NO
performance claim.**

Per-segment stdout cost fields returned null in this run's aggregation
(the base `vulkan_encoder.py` runner does not propagate the resident
session's `profile` sub-dict into `e2e-report.json` the way the profiled
wrapper does) — noted as an instrumentation gap; the wall-clock verdict
does not depend on it.

## Interpretation

The `_IONBF` lever eliminates per-output `fflush` syscalls (byte-stream
proven identical), but on this stack the flush cost was never the
binding constraint — `first_byte_ns` is dominated by worker exec + ANE
compute, which no flush strategy moves. The single-shot −44 ms was
noise; the counterbalanced replication is the honest measurement.

## Disposition of the lever

- The lever patch (`worker-lever/main_lever.cpp`) stays on this branch
  as a **bench artifact with a NEUTRAL verdict**, NOT promoted.
- Not landed into mlx/omarchy-ane worktrees: Main's condition was
  "land source change if repeat gain is real" — the repeat gain is not
  real. Landing a neutral-to-slightly-negative change adds churn with
  no measured benefit.
- The A/B harness, byte-equivalence test, and this verdict remain
  reusable for any future worker-side lever candidate.

## Next (per Main)

Target the next measured larger bottleneck with the GPU owner
(FleetM1MaxGPU / GPUHardwareContinuation): the 1,628 ms GPU-feeder GAP
(30.9 % of stage) and the ~2,034 ms `mx.eval` readiness wait are the
two dominant non-ANE segments from the 04-hardware-measurement
decomposition. No full parity claim.
