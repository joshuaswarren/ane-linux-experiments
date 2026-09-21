# 03 — Pre-hardware lever triage (honest)

**Lane:** `ParakeetPerformance`, branch `agent/parakeet-perf-resident`.
**Date:** 2026-09-21.
**Status:** pending real-hardware measurement; this is a triage.

## What this slice discovered pre-hardware

The new instrumentation in `ane_resident_profiled.py` + the
`vulkan_encoder_profile_wrapper.py` will produce, on real jwm1, a per-
segment breakdown of:
- `encode_ns` (parent CPU request-line build)
- `write_call_ns` (parent os.write syscall)
- `first_byte_ns` (parent blocking on first line; pipe + worker-recv + exec + IPC)
- `header_lines_ns` (per-output "out <name> <length>" _readline time)
- `output_read_ns` (per-output payload _read_exact time)
- `trailing_ns` (last payload → "job status=" line, parent's view of post-exec IPC wait)

Plus, from the vulkan_encoder layer:
- `marshal_eval_ns` (mx.eval + np.asarray + tobytes per input)
- `session_round_ns` (= elapsed_ns of the ane_resident round)
- `back_conv_ns` (np.frombuffer + mx.array.reshape per output)

## Mock-worker empirical numbers (this run, local)

The mock worker is NOT the real ANE worker. It is a wire-protocol twin
that runs in-process, so these numbers measure only the resident client
behavior with simulated exec:

| segment | per-round median (mock) | per-pass total (48 rounds) |
|---|---:|---:|
| encode_ns | 1.98 us | 0.10 ms |
| write_call_ns | 4.84 us | 0.23 ms |
| first_byte_ns | 20120.67 us | dominated by mock's `--exec-delay-ms 20` |
| output_read_ns | 3.19 us | 0.15 ms (96 outputs) |
| header_lines_ns | ~0 | ~0 |
| trailing_ns | 0.15 us | ~0 |

Reproducer: `python3 .work/2026-09-21-parakeet-perf-resident/lever_zoo.py`

**Honest finding:** the resident client-side submit path totals
~0.5 ms per pass on the mock worker. The dominance by `first_byte_ns`
is the simulated exec delay, not a client-side bottleneck.

## L1 (bytearray pre-sized) verdict unchanged

Already REJECTED in `01-microbench-verdict.md`: 6.45 ms slower per pass
on a CPU-only `bytearray` construction bench, byte-equivalent. The
micro-bench simulated per-round input bytes at the real island-attn-a-kt
and island-pv sizes (768 KB - 2.25 MB per input, 48 rounds = 164 MB).
The lever exists at `.work/2026-09-21-parakeet-perf-resident/ane_resident.patch`
for the record; NOT applied.

## Buffered-drain lever (`LEVER_BUFFERED_DRAIN`)

Implemented at `.work/2026-09-21-parakeet-perf-resident/ane_resident_buffered.py`
under env-var gate. Failing-first byte-equivalence test PASSES on mock
worker:

```
=== Phase A: lever OFF (base) ===
  10 rounds, all results captured
=== Phase B: lever ON (buffered_drain) ===
  10 rounds, all results captured
  All 10 rounds: byte-identical, hash-identical
=== ALL BYTE-EQUIVALENCE INVARIANTS PASS ===
```

Reproducer: `python3 .work/2026-09-21-parakeet-perf-resident/test_buffered_drain_byte_equivalence.py`

The lever as currently written changes the field name only — both paths
do per-output `_read_exact`. A true buffered drain that reads all output
bytes in one call would require knowing the total output byte count
upfront (or reading until "job status=" line, which conflates output
with the trailing IPC wait). That requires either a worker-side
protocol change (out of lane) or parsing the sum of per-output
lengths after reading all "out " headers (which is what `_readline` +
`_read_exact` already does efficiently).

**Realistic reclaim from a resident-client-only change:** < 1 ms / pass
(0.02 % of stage). Not material to the 5.2 s stage wall.

## What this implies for the slice

Per parent directive: "implement smallest measured bottleneck fix with
failing-first check and real 104 pin/time rerun under lease."

The mechanism for finding the **largest** sub-segment is in place; the
hardware lease will produce the numbers. Three cases:

1. **`trailing_ns` is large (> 100 ms):** the dominant lever is worker-
   side stdout pre-flush per output. Out of this lane's scope;
   recommend to ANE worker owner with measured data.

2. **`first_byte_ns - first-round-exec ≈ 0` AND `trailing_ns ≈ exec`:**
   the worker is buffering all output until job complete, then sending
   it in one flush. No client-side change helps; the parent wait is
   bounded by worker behavior.

3. **`first_byte_ns - exec ≈ IPC wait` is non-trivial:** the parent
   could do useful work during that time. Possible lever: `mx.eval`
   for the NEXT round's inputs while waiting for the CURRENT round's
   outputs. This is a non-trivial change to the round ordering and
   needs measurement to justify.

In all three cases, the resident-client lever is bounded at < 1-5 ms
(per the mock-worker numbers). The slice will report the real
measurement after the jwm1 hardware lease, with whichever case
applies, and recommend the appropriate next owner.

## What this slice WILL do on hardware lease

1. Run `profiled_lease_run.sh` on jwm1 (`/tmp/parakeet-perf-resident/`),
   warm + 5 measured, `ANE_RESIDENT_PROFILE=1`.
2. Aggregate per-segment breakdown across the 5 runs.
3. Identify the largest non-worker-exec segment.
4. Implement a byte-equivalent lever in the resident client layer that
   addresses that segment. Failing-first byte-equivalence test first.
5. Re-run under the same lease with the lever on. Compare medians.
6. Report the measured delta vs the baseline re-confirm (5243.345 ms).
   If positive and gate-preserved (104/104 + golden sha), commit +
   push the lever as a clean patch. If zero or negative, document
   honestly and recommend the worker-side change for the dominant
   remaining segment.

## What this slice will NOT do

- Touch `/tmp/mil-ln-rank3`, mil-hwx-compiler, or any compiler source.
- Run GPU feeder analysis (parent-owned, FleetM1MaxGPU on jw16).
- Claim any encoder-stage wall-clock improvement without hardware-
  measured evidence.
- Re-prove the 104/104 pins on jwm1 (already proven by parent receipts).
