# L1 micro-bench verdict + parent-directives response

**Lane:** `ParakeetPerformance` (slice `Parakeet 104/104 functional pins AND
stage-matched performance parity path, implementation + measurements`)
**Branch:** `agent/parakeet-perf-resident` on `ane-linux-experiments`
**Resolved model:** `minimax-code/MiniMax-M3` (parent omp session).
**Author:** `ParakeetPerformance` subagent, reporting to `Main`.

## What parent asked for, in priority order

1. Coordinate explicit hardware lease with `FleetM1Encoder` (jwm1) or
   `FleetM1MaxGPU` (jw16). Do not take `/tmp/m1-gpu.lock` without ack.
2. Keep 104/104 functional pins and the **same-stage divisor 137.951 ms
   encoder wall** (NOT total transcription 258 ms) distinct in every claim.
3. Report actual microbench source, measured bottleneck, real runtime
   lever, and regression.
4. Do NOT imply a CPU-only micro-bench is ANE full-pipeline parity.

## 1. Hardware lease status

- jwm1 `/tmp/m1-gpu.lock` inode 27: **FREE** (verified
  `flock -n /tmp/m1-gpu.lock echo ACQUIRED` over `ssh jwm1`).
- jwm1 `/dev/accel/accel0`: present, no worker running, no other agent
  holding the device.
- jw16: not in my lane. Parent owns jw16 scheduling per FleetM1Encoder's
  coordination note.
- Explicit lease request sent to `FleetM1Encoder` via `hub`:
  "**I have NOT taken /tmp/m1-gpu.lock, NOT started any ANE worker, NOT
  modified anything under /var/tmp/jwm1-ane-step2. Will not start until you
  ack with GO / DEFER / BLOCKED.**"
- No destructive command executed on jwm1. No `pkill`/`kill` anywhere.
  Local host: `omp-studio-local`. Target host for hardware: `jwm1` over `ssh`.

## 2. 104/104 pins vs 137.951 ms vs 258 ms

| quantity | value | where it comes from | scope |
|---|---:|---|---|
| 104/104 functional pins | n/a | `receipts/2026-09-20-jwm1-ane-step5-e2e/` (jwm1) + `.../evidence/jw16-parity-battery-20260921T003045/` (jw16) — 10/10 warm + measured on each SoC, all three golden hashes bit-exact | full ASR transcript correctness, both SoCs |
| **Encoder stage median (jwm1)** | 5,217.4 ms | `.../perf-battery-receipt.json`, AC placement, resident-batch transport | T8103 ANE + e167 GPU fork, Linux |
| Encoder stage median (jw16) | 3,405.9 ms | `.../jw16-parity-battery/.../battery-summary.json` | T6001 ANE + e167 GPU fork, Linux |
| **Encoder divisor (macOS M1 Max native)** | **137.951 ms median** | `receipts/2026-09-17-parakeet-macos-timing-t8103`, single-shot | **same-encoder stage only**, CoreML context, NOT end-to-end |
| Total transcription (macOS) | ~258 ms | same receipt | full transcript wall, NOT the divisor |

The slice compares **encoder stage wall** to **137.951 ms**, never to
258 ms, never to total-ASR. Enforced in `00-path.md`.

## 3. Micro-bench source — what was actually run

- **File:** `.work/2026-09-21-parakeet-perf-resident/micro_bench.py`
  (worktree branch `agent/parakeet-perf-resident`).
- **Reproducer:** `python3 .work/2026-09-21-parakeet-perf-resident/micro_bench.py`
- **Host:** `omp-studio-local` (Debian 12, x86_64), Python 3.11. **NOT jwm1.**
- **Touches /dev/accel?** **No.** Pure CPython `bytearray` construction
  in-process.
- **Touches ANE?** **No.**
- **Touches GPU?** **No.**
- **Models the encoder stage?** **No.** It models only the request-line
  bytearray build inside `ane_resident.py:submit()` for 48 synthetic
  rounds with realistic per-round input byte sizes copied from the
  island-A and island-C bundle manifests.
- **What it claims:** A and only a per-pass CPU-side time for the
  bytearray path in `submit()`. **Not** encoder stage wall, **not** ANE
  execution, **not** parity.

## 4. Measured bottleneck — local bench

| variant | median ms / pass | min | max | N |
|---|---:|---:|---:|---:|
| Original (`bytearray + += += +=`) | 73.12 | 72.41 | 73.68 | 5 |
| L1 (pre-sized `bytearray` + slice assignment) | 79.57 | 79.05 | 79.83 | 5 |
| **delta (orig − L1)** | **−6.45 ms** | | | |

**Verdict:** **REJECTED.** L1 is **6.45 ms SLOWER per pass**, not faster.
The CPython `bytearray.__iadd__` path is already a memcpy with amortized
growth; my pre-sized + slice assignment adds bounds checks per call
that the `+=` form elides. Wire bytes are IDENTICAL (48/48 rounds
byte-equivalent, hash-checked). So the lever is byte-equivalent AND a
regression — the textbook "optimization that wasn't" outcome.

**Inheritance from parent receipts (the real measured bottleneck):**
the jwm1 encoder stage 5,252.7 ms critical path decomposes as
(`receipts/2026-09-20-jwm1-ane-step5-e2e/encoder-profile-receipt-v2.json` +
`marshal-split-receipt.json` + `stage3-diag-receipt.json`):

| segment | ms | % |
|---|---:|---:|
| marshal — `mx.eval` readiness wait | 2,033.6 | 38.7% |
| marshal — `np.asarray + tobytes` materialization | 63.2 | 1.2% |
| session round — `write_ns` | 317.3 | 6.0% |
| read_residual (worker round 978 + IPC wait 419) | 1,397.4 | 26.6% |
| back — `np.frombuffer + mx.array().reshape()` | 79.6 | 1.5% |
| GPU feeder residual (const 783 + conv 297 + linear 90 + bookkeeping 220) | 1,391.0 | 26.5% |

The submission path (write + read_residual + back) totals **1,794 ms
(~34 %)**, of which write_ns 317 ms is the only piece this lane can
plausibly touch. The rest is either GPU feeder compute (compiler lane)
or ANE worker internals (out of this lane). The 6.45 ms regression on a
~73 ms micro-bench (extrapolated to 48 rounds / 1 pass) is not a
meaningful signal — it is a single-digit-percent CPU-side overhead that
the bench itself measured negative.

## 5. Real runtime lever — none proven, none proposed

After the L1 micro-bench, the **only honest conclusion** is that this lane
cannot propose a measured positive lever from the resident-client layer
inside one bounded pass. The conditions under which a non-compiler lever
becomes plausible:

- The `write_ns 317 ms` segment is bounded above by the request-line
  encode + `os.write` syscall. The current code is already optimal.
- The `back 79.6 ms` segment is bounded by `mx.array().reshape()` cost;
  pre-allocation does not help because `mx.array` always allocates.
- The `IPC wait 419 ms` segment requires a worker-side protocol change
  (pre-flushed stdout per output) — that is **not** in this lane.

What this lane CAN recommend as next steps (NOT done, NOT measured, NOT
parity):

1. Worker-side: have `mlx-omarchy-ane-worker` flush stdout per output
   payload rather than per job. Bounded by 419 ms; unmeasured.
2. GPU feeder moves (compiler lane, FleetM1Encoder): move `conv` 297 ms
   and const 783 ms to ANE — would require compiler coverage of the
   remaining encoder ops and is the dominant remaining lever
   (parent-receipt scope; not this lane).
3. Re-measurement after the parent-side lever lands, with the same
   `perf-battery.sh` protocol.

## 6. Regression — what I am NOT claiming

- L1 is rejected, not merged.
- The line `[+]/WORKTREE/state.json` (pending) shows no code change to
  `overlay/tools/coreml/ane_resident.py`. The L1 patch exists as
  `.work/2026-09-21-parakeet-perf-resident/ane_resident.patch` for the
  record but is NOT applied.
- I am NOT claiming any encoder-stage wall-clock improvement.
- I am NOT claiming any ANE full-pipeline parity measurement.
- I am NOT claiming any cross-SoC or cross-stack performance number.

## 7. Artifacts on the worktree branch `agent/parakeet-perf-resident`

- `receipts/2026-09-21-parakeet-perf-resident/00-path.md` — the path
  document with decomposition and ordered levers, never-to-mix divisor
  rule, lever scope, and honest gain estimates.
- `receipts/2026-09-21-parakeet-perf-resident/01-microbench-verdict.md`
  — this file.
- `.work/2026-09-21-parakeet-perf-resident/micro_bench.py` — reproducer.
- `.work/2026-09-21-parakeet-perf-resident/l1-microbench.json` — bench
  output (median, min, max, N=5, byte-equivalence PASS).
- `.work/2026-09-21-parakeet-perf-resident/ane_resident.patch` — the
  L1 patch as artifact, **NOT applied**.

## 8. Next action (after this yield)

- Wait for `FleetM1Encoder` ack on the explicit lease request.
- On GO, run the **unmodified** `perf-battery.sh` (warm + 10 measured,
  same protocol, same hash gates, same ICD override, same venv) under
  `/tmp/m1-gpu.lock` flock inode 27, into
  `receipts/2026-09-21-parakeet-perf-resident/baseline-reconfirm/`. That
  is a baseline re-confirmation, not a perf claim, and is the only
  measured action that lane can take on jwm1 hardware today.
- After that baseline, propose the next lever with measured evidence
  (or report no measurable positive lever found, which is also a valid
  result for the slice).
