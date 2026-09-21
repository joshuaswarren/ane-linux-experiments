# 02 — Profile instrumentation: end-to-end per-segment timing

**Lane:** `ParakeetPerformance`, branch `agent/parakeet-perf-resident`.
**Directive:** Main 2026-09-21 IRC: "profile read_residual 1397 ms and
write 317 ms end-to-end, separating blocking execution/IPC/copies without
double-counting, then implement smallest measured bottleneck fix with
failing-first check and real 104 pin/time rerun under lease."

## What was built (Phase 1 of this directive)

Two additive instrumentation layers, both gated by `ANE_RESIDENT_PROFILE=1`:

### Layer 1 — `ane_resident.py` per-submit profile (parent-side, IPC-visible)

File: `.work/2026-09-21-parakeet-perf-resident/ane_resident_profiled.py`
(drop-in replacement of the parent `overlay/tools/coreml/ane_resident.py`).

Adds the following fields to each `record` in `self.log` when the env var
is set (zero behavior change otherwise):

| field | meaning |
|---|---|
| `encode_ns` | parent CPU time to build the request bytearray (precedes `started`; OUTSIDE `elapsed_ns`) |
| `write_call_ns` | time inside `_write_bytes` (parent syscall + kernel pipe copy) |
| `first_byte_ns` | blocking time from `_write_bytes` return until the FIRST line arrives on stdout (pipe transport + worker recv + worker exec + first IPC roundtrip — inseparable from parent) |
| `output_read_ns` | sum of `_read_exact` times for all output payloads |
| `header_lines_ns` | sum of `_readline` times for "out <name> <length>" header lines (excluded from `first_byte_ns` for rounds with N>=2 outputs) |
| `trailing_ns` | time from last `_read_exact` return until the trailing "job status=" `_readline` returns |
| `sum_ns` | `write_call_ns + first_byte_ns + output_read_ns + header_lines_ns + trailing_ns` |

**Invariant:** `sum_ns ≈ elapsed_ns` (within 5 % measurement slop).

### Layer 2 — `vulkan_encoder.py` per-round profile (vulkan_encoder-side, parent + child visible)

File: `.work/2026-09-21-parakeet-perf-resident/vulkan_encoder_profile_wrapper.py`
(monkey-patches the base `AneIsland._submit_resident` and
`_ensure_session` via `importlib`; `--encoder-runner` drop-in).

Adds the following fields to each round record:

| field | meaning |
|---|---|
| `marshal_eval_ns` | sum of `mx.eval + np.asarray + tobytes` per input |
| `session_round_ns` | delegated to `ane_resident.submit()` (`= elapsed_ns`) |
| `back_conv_ns` | sum of `np.frombuffer + mx.array().reshape` per output |
| `sum_ns` | `marshal_eval_ns + session_round_ns + back_conv_ns` |
| `session_profile` | the Layer-1 record.profile dict for the same round (joined) |

## Failing-first invariant test

File: `.work/2026-09-21-parakeet-perf-resident/test_profile_invariants.py`

What it enforces:
1. With `ANE_RESIDENT_PROFILE=0`, no record has a `profile` key (zero-
   behavior-change gate).
2. With `ANE_RESIDENT_PROFILE=1`, every record has a `profile` dict.
3. Every per-segment field is `>= 0` and `<= elapsed_ns + 1 ms`.
4. `sum_ns == elapsed_ns` within 5 %.
5. End-to-end: 5 mock submits produce 5 records with byte sizes matching
   the wire payload.

What it uses:
- `mock_worker.py` — replays the exact wire protocol
  (`resident bundle=...`, `resident loaded ...`, `submit <bundle>
  --inline name=length ... --emit name`, `out <name> <length>` + payload,
  `job status=0 ...`, `batch ...`, `batch-end`, `quit`) in a subprocess,
  with optional `--exec-delay-ms` to simulate worker compute.
- The instrumented `ane_resident_profiled.ResidentAneWorker` is the
  client side under test.

## Test result (this run, local)

```
=== Phase 1: baseline (profile OFF) ===
  3 rounds, no profile keys: OK (3 records)
=== Phase 2: profile ON ===
  5 rounds OK. Sample profile[0]:
    encode_ns: 4.43 us
    write_call_ns: 8.95 us
    first_byte_ns: 20157.08 us
    output_read_ns: 7.25 us
    header_lines_ns: 0.00 us
    trailing_ns: 0.18 us
    elapsed_ns: 20190.23 us
=== ALL PROFILE INVARIANTS PASS ===
```

Reproducer: `python3 .work/2026-09-21-parakeet-perf-resident/test_profile_invariants.py`

## What is NOT measured

- `first_byte_ns` is inseparable into (a) pipe-write-transport, (b) worker
  recv, (c) worker exec, (d) first IPC roundtrip, all from the parent.
  Worker-side timestamping would be required to split. Out of this lane's
  scope; the parent-side data is the most we can honestly attribute.
- `mx.eval` readiness wait inside `marshal_eval_ns` is a parent-side CPU
  wall; it does NOT include the GPU feeder time that is the actual
  bottleneck of that segment per inherited receipts. Splitting eval-readiness
  vs materialization requires per-op GPU timing (already attempted in
  `marshal-split-receipt.json`).
- `np.frombuffer + mx.array().reshape` inside `back_conv_ns` is not split;
  both are small (~80 ms total per pass) and the marginal cost of a
  splitting micro-bench exceeds the actual gain.

## Phase 2 (next): m1-test-host hardware lease re-run with profile on

- Script: `.work/2026-09-21-parakeet-perf-resident/profiled_lease_run.sh`
- Staged at `/tmp/parakeet-perf-resident/` on m1-test-host.
- Acquires `/tmp/m1-gpu.lock` inode 27 (bounded 25 min), runs warm + 5
  measured with `ANE_RESIDENT_PROFILE=1` + the wrapper overlay, releases
  lock.
- Per-segment breakdown across 5 measured runs aggregated in
  `profiled-reconfirm-<TS>/profiled-summary.json`.
- Gates: 104/104 + mel/hidden/transcript golden sha bit-exact on every run.
- Hash gates are enforced by the existing perf-battery post-processing.

## Phase 3 (after hardware): pick smallest measured bottleneck

The smallest non-zero segment that has actual slack becomes the lever
target. Likely candidates given the inherited decomposition:

| segment | expected range from inheritance | realistic lever |
|---|---|---|
| `trailing_ns` (parent IPC wait after worker exec done) | 0 - 200 ms | worker-side stdout pre-flush per output (out of lane; recommend to worker owner) |
| `header_lines_ns` (per-output header line reads) | 0 - 50 ms | buffered drain (small) |
| `back_conv_ns` (np.frombuffer + mx.array.reshape per output) | 60 - 100 ms | pool mx.array outputs (small; ~30 ms expected) |
| `encode_ns` (parent CPU request-line build) | 5 - 15 ms total | already in micro-bench scope; L1 rejected |

If the new measurement shows the `trailing_ns` segment is large (> 100 ms),
that's the dominant lever and it requires worker-side changes; this slice
will share the data with the ANE worker owner.

## Status

- Phase 1 (instrumentation + mock test): DONE, PASSING.
- Phase 2 (m1-test-host hardware lease): WAITING for FleetM1Encoder ack on second
  lease window. Lease request sent 2026-09-21T11:38Z, no ack yet.
- Phase 3 (lever implementation): pending Phase 2 measurement.

## No-double-counting guarantee

Every segment is parent-side and uses `time.monotonic_ns()` taken at the
moment of the parent CPU event. No segment includes the wall time of a
sibling segment:
- `marshal_eval_ns` ends before `session.submit()` is called.
- `session_round_ns == elapsed_ns` is the wall of `_submit_resident`'s
  `submit()` call, which equals `record.elapsed_ns` recorded before
  `back_conv_ns` runs.
- `back_conv_ns` starts after `submit()` returns.
- Inside `submit()`, `encode_ns` runs before `started`, and the remaining
  five segments are strictly sequential over the read phase, each
  measured at the call site. Sum equals wall within 5 % (test confirms).

## What is NOT claimed

- This instrumentation does NOT change runtime behavior when the env var
  is unset (verified by Phase 1 of the test).
- The mock-worker test is NOT an ANE full-pipeline measurement. It only
  validates the wire-protocol timing invariants.
- The hardware lease has not run yet. The real m1-test-host per-segment
  breakdown is pending.
