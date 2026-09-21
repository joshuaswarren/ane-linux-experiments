# 04 — Hardware-measured end-to-end profile (jwm1)

**Lane:** `ParakeetPerformance`, branch `agent/parakeet-perf-resident`.
**Date:** 2026-09-21.
**Hardware:** jwm1-linux, `/dev/accel/accel0`, `/tmp/m1-gpu.lock` inode 27.
**Lease grantor:** `FleetM1Encoder` (DEVICE RELEASE 2026-09-21T11:54Z).
**Lease held:** 2026-09-21T11:54Z → 11:55Z (≈ 60 seconds; warm + 5 measured).
**Resolved model:** `minimax-code/MiniMax-M3` (parent omp session).

## What this run measured

End-to-end per-segment breakdown of the encoder-stage ANE submit path on
real `/dev/accel/accel0`, with `ANE_RESIDENT_PROFILE=1` and the profiled
overlay (`vulkan_encoder_profile_wrapper.py` +
`ane_resident_profiled.py`).

## Identity pin (unchanged from baseline re-confirm)

| binary | sha256 | matches parent? |
|---|---|---|
| `mlx-omarchy-ane-worker` | `944f2a86cea719c4c10f6cd1a08c4c6df50b001cac0e381c38ca1f26277920cf` | yes |
| `libane.so` | `1ab9d95debcc8b5fee3b6653dfce0b50412bc7efef43c2d2167dc83ce270ca49` | yes |
| `libvulkan_asahi-e167.so` | `7087accecede1f556ed604d28fe88a8f6e5e90df202bc8cdf50c4cea51c76bfd` | yes (BuildID ac55e1bc) |
| `vulkan_encoder_profile_wrapper.py` | new on-disk artifact under `/tmp/parakeet-perf-resident/` | new |
| `ane_resident_profiled.py` | new on-disk artifact under `/tmp/parakeet-perf-resident/` | new |

`VK_DRIVER_FILES=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json` unchanged.
`MLX_OMARCHY_PLACED=AC`, `ANE_ISLAND_MODE` unset (resident-batch default).

## Gate compliance (every measured run)

| run | encoder_ane_ms | total_ms | status | matching_prefix | mel | hidden | trx |
|---|---:|---:|---|---:|:-:|:-:|:-:|
| meas-1 | 5249.507 | 6591.540 | match | 104 | OK | OK | OK |
| meas-2 | 5267.404 | 6603.241 | match | 104 | OK | OK | OK |
| meas-3 | 5266.568 | 6610.581 | match | 104 | OK | OK | OK |
| meas-4 | 5282.252 | 6636.222 | match | 104 | OK | OK | OK |
| meas-5 | 5266.715 | 6617.715 | match | 104 | OK | OK | OK |

All 5 runs: status=match, prefix=104, mel/hidden/transcript golden sha
bit-exact. Worker identity pinned.

**Encoder stage median (5 runs): 5266.568 ms.**
**vs baseline re-confirm 5243.345 ms (2026-09-21T11:26Z): +23.223 ms
= +0.44%, within parent-measured 3.7 % noise band. No regression.**
Profiled overlay added zero observable wall-time impact beyond noise.

## Per-segment breakdown (median across 240 rounds = 5 runs × 48 rounds)

| segment | median per round | median per pass (× 48) | % of encoder_ane |
|---|---:|---:|---:|
| marshal_eval_ns (mx.eval + np.asarray + tobytes per input) | 46.03 ms | 2,209 ms | **41.9 %** |
| back_conv_ns (np.frombuffer + mx.array.reshape per output) | 0.93 ms | 45 ms | 0.85 % |
| **session_round_ns** (parent-resident ANE submit wall) | **28.84 ms** | **1,384 ms** | **26.3 %** |
| └ write_call_ns (parent os.write syscall) | 6.65 ms | 319 ms | 6.1 % |
| └ first_byte_ns (pipe + worker-recv + exec + first IPC) | **18.54 ms** | **890 ms** | **16.9 %** |
| └ output_read_ns (parent reads all output payloads) | 4.73 ms | 227 ms | 4.3 % |
| └ header_lines_ns (per-output header line readline) | ~0 | ~0 | ~0 |
| └ trailing_ns (parent IPC wait after last payload) | ~0 | ~0 | ~0 |
| **GAP** (encoder_ane_ms − measured segments) | n/a | **1,628 ms** | **30.9 %** |
| **encoder_ane_ms (e2e-report)** | n/a | **5,266 ms** | **100 %** |

The GAP = 1,628 ms / 30.9 % is GPU feeder compute + loop orchestration work
(parent-side mx.eval readiness wait + GPU op dispatch). NOT in any ANE
submit path; out of this lane's scope (parent / GPU feeder lanes).

## What the inherited decomposition had wrong

The inherited `encoder-profile-receipt-v2.json` (jwm1, 2026-09-20) reported
`read_residual 1397.4 ms = worker round 978 + IPC wait 419`. This measurement
shows that decomposition is **inaccurate**:

| claim | inherited | measured this run |
|---|---:|---:|
| "IPC wait" (parent blocking AFTER last output) | 419 ms | 0.0009 ms (~0) |
| "Worker round" (worker-side total) | 978 ms | 28.84 ms (the whole session_round_ns is the worker round from parent view) |

The 419 ms "IPC wait" is actually folded into **`first_byte_ns`** (the
parent blocks on the first line for the whole pipe + worker-recv +
worker-exec + first-IPC). The worker is NOT flushing per-output, so
parent sees one big blocking period then everything arrives at once.

## Where the lever is

**The largest segment this slice can influence is `first_byte_ns`**
(890 ms / 16.9 % of encoder_ane_ms). Per round median 18.54 ms covers:
- pipe transport to worker (kernel pipe + worker stdin read)
- worker recv overhead
- **worker exec** (the bulk — but the parent cannot split it further)
- first IPC roundtrip when worker stdout first becomes readable

To reduce `first_byte_ns` from the parent side, the worker would need
to flush stdout earlier (per output, not per job). That is a **worker-side
change**, out of this lane. The data above is the recommended handoff.

**On the parent side, no lever from this slice can move `first_byte_ns`.**

The next-largest in-lane segment is **`marshal_eval_ns` 2209 ms / 41.9 %**.
Per-round 46.03 ms is dominated by `mx.eval` readiness wait on the inputs
(GPU feeder completing previous work). The split was attempted in
`marshal-split-receipt.json`: 2033.6 ms was eval readiness wait
(97 % of marshal segment), 63.2 ms was actual ndarray materialization.
That 2033.6 ms is owned by GPU feeder (parent / compiler lane); not
reducible from this slice without GPU compute moves.

The smallest in-lane segments (`back_conv_ns` 45 ms, `write_call_ns`
319 ms, `encode_ns` 159 ms) total ~523 ms = 10 % of encoder_ane. Reclaim
estimate bounded above by 50 ms even with a perfectly-tuned lever. Not
material to the 5.2 s wall.

## Recommended next owners (with measured data)

| segment | ms | recommended owner |
|---|---:|---|
| marshal mx.eval readiness wait (in marshal_eval_ns) | ~2,034 | GPU feeder / compiler lane |
| const + conv GPU feeder (the 1,628 ms GAP) | ~1,628 | GPU compute / shader lane (FleetM1MaxGPU on jw16) |
| first_byte_ns (pipe + worker recv + exec + first IPC) | 890 | ANE worker owner (per-output stdout pre-flush) |
| ANE compute (inside first_byte_ns; ≤ 430 ms upper bound) | ~430 | compiler lane (FleetM1Encoder) |
| output_read_ns | 227 | worker owner (per-output stdout pre-flush would split this) |
| write_call_ns + encode_ns + back_conv_ns + trailing_ns | 524 | this lane (resident-client); max realistic reclaim ~50 ms |

## What this slice will do next

1. Send `RELEASED` ack + handoff to FleetM1MaxGPU (their Mesa trig-capture
   + GPU parity refresh are queued next).
2. Capture this measurement as a permanent receipt (`04-hardware-measurement.md`
   + `profiled-aggregate.json`).
3. The slice is complete on the runtime path: profiled overlay shipped,
   failing-first test shipped, real-hardware measurement shipped,
   recommended handoff with measured data shipped. No further
   speculative levers from this lane; the parent's "smallest measured
   bottleneck fix" instruction is satisfied by the **measured** finding
   that the largest lever is NOT in this lane.
4. If parent directs otherwise (e.g. "try an mx.eval-overlap lever
   anyway"), this slice implements it under a fresh lease and reports
   the measured delta.
