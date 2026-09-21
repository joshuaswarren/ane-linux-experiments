# L1 micro-bench verdict + parent-directives response

**Lane:** `ParakeetPerformance` (slice `Parakeet 104/104 functional pins AND
stage-matched performance parity path, implementation + measurements`)
**Branch:** `agent/parakeet-perf-resident` on `ane-linux-experiments`
**Resolved model:** `minimax-code/MiniMax-M3` (parent omp session).
**Author:** `ParakeetPerformance` subagent, reporting to `Main`.

## What parent asked for, in priority order

1. Coordinate explicit hardware lease with `FleetM1Encoder` (jwm1) or
   `FleetM1MaxGPU` (jw16). Do not take `/tmp/m1-gpu.lock` without ack.
2. Keep 104/104 functional pins distinct from any cross-SoC native
   reference (the 137.951 ms M1 Max number is CROSS-SOC context, NOT
   same-SoC parity evidence). The 259.9 ms jwm1 macOS-27 number is
   CROSS-OS-GENERATION and is **removed entirely** from this slice per
   Main directive. **No ratio-to-native is computed.**
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

## 2. 104/104 pins and the (now-stripped) native references

| quantity | value | where it comes from | scope |
|---|---:|---|---|
| 104/104 functional pins | n/a | `receipts/2026-09-20-jwm1-ane-step5-e2e/` (jwm1) + `.../evidence/jw16-parity-battery-20260921T003045/` (jw16) — 10/10 warm + measured on each SoC, all three golden hashes bit-exact | full ASR transcript correctness, both SoCs |
| **Encoder stage median (jwm1)** | 5,243.345 ms (this run 2026-09-21) | `.../baseline-reconfirm/battery-summary.json`, AC placement, resident-batch transport | T8103 ANE + e167 GPU fork, Linux |
| Encoder stage median (jw16) | 3,405.9 ms (inherited) | `.../jw16-parity-battery/.../battery-summary.json` | T6001 ANE + e167 GPU fork, Linux |

**Native macOS references are NOT a comparison divisor in this slice:**

- 137.951 ms jw16 native macOS M1 Max single-shot encoder wall — CROSS-SOC
  (T8103/M1 vs T6001/M1 Max); **NOT same-SoC parity evidence**.
- 259.9 ms jwm1 native macOS-27.0/CoreML-3600 same-SoC T8103 — removed
  entirely; CROSS-OS-GENERATION vs the M1 Ultra reference (macOS
  26.6.2 / CoreML 3520); per Main directive, no ratio computed.
- 258 ms jw16 total transcription (not the encoder wall) — same
  cross-SoC caveat, not used as a divisor.

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

## 5. Real runtime lever — end-to-end profile of read_residual/write_ns

Per Main directive (2026-09-21 IRC): "profile read_residual 1397 ms and
write 317 ms end-to-end, separating blocking execution/IPC/copies without
double-counting, then implement smallest measured bottleneck fix with
failing-first check and real 104 pin/time rerun under lease."

What the inherited decomposition does NOT separate (gap this slice will
close in next step):

- `write_ns 317 ms` is one wall number; it does not separate (a)
  parent CPU encode + `os.write` syscall cost, (b) pipe transport to
  worker stdin, (c) worker recv overhead, (d) anything else.
- `read_residual 1397 ms = round - write` lumps (a) blocking-on-
  worker-exec 978 ms, (b) parent IPC wait after worker exec done, (c)
  parent CPU copy of output bytes, all into one bucket.
- `back 79.6 ms` = `np.frombuffer + mx.array().reshape()` per output;
  doesn't separate the frombuffer copy from the mx.array allocation.

What this lane WILL do next (in this lane, on jwm1):

1. Add explicit `time.monotonic_ns()` instrumentation inside
   `ane_resident.py:submit()` around (a) the pre-write `_write_bytes`
   call, (b) the per-output `_read_exact` calls, (c) the trailing
   `_readline` that returns the job status line. Use a per-round
   `record` dict extension (additive, no schema break) under a new
   env var `ANE_RESIDENT_PROFILE=1` so the existing code path is
   untouched when the flag is off.
2. Add explicit timing inside `vulkan_encoder.py:_submit_resident`
   around (a) `mx.eval + np.asarray + tobytes` per input, (b)
   `session.submit` (already times this), (c) `np.frombuffer +
   mx.array().reshape` per output. Same `ANE_RESIDENT_PROFILE=1`
   guard.
3. Build a **mock worker harness** (`tools/mock_resident_worker.py`)
   that replays the exact wire protocol with synthetic data so the
   instrumentation is unit-tested without `/dev/accel`. Failing-first
   check: instrumented round-trip produces non-overlapping per-
   segment breakdowns that sum to within 1 % of the round wall.
4. Failing-first unit test:
   `tests/test_resident_profile_invariants.py` that (a) runs N rounds
   through the mock worker with the profile flag on, (b) asserts
   `marshal_ns + round_ns + back_ns == wall_ns ± 1%`, (c) asserts
   `write_ns + read_residual_ns == round_ns`, (d) asserts all
   segments ≥ 0. The test FAILS pre-fix because the code lacks the
   instrumentation.
5. Real jwm1 lease re-run with `ANE_RESIDENT_PROFILE=1`, capture
   per-segment breakdown across 1 warm + 5 measured runs.
6. From the measured breakdown, identify the **smallest** segment that
   has actual slack (e.g. `parent IPC wait after worker exec done`).
   Implement a byte-equivalent lever there with a focused failing-
   first test that proves the change moves the right thing.
7. Re-measure under lease with hash gates intact (104/104 + mel/
   hidden/transcript golden sha).

What this lane CANNOT do (out of scope):

- Worker-side protocol changes (e.g. per-output stdout flush) —
  belongs to the ANE worker owner.
- GPU feeder ops (const 783 + conv 297 ms) — belongs to the GPU
  compute lane (FleetM1MaxGPU on jw16); this slice will share
  measurements, not take the implementation.
- Compiler-emitted op coverage (ANI matmul/conv/silu/norm/linear/
  concat remaining) — FleetM1Encoder's lane.

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
