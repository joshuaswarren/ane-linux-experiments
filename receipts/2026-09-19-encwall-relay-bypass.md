# Encoder wall on v0.7.1 bytes: relay-bypass worker-protocol change (2026-09-19, jw16)

Lane: EncWallRelayBypass. Branch: `mlx-omarchy` `agent/encwall-relay-bypass`
`d0b0b7bb` off `39bef329` (current main). Worker binary sha256 differs
from v0.7.1 release (release `d867f9a4…`, candidate `e2e7fc24…`);
`libmlx.so` pin (`df3d4e74c597956c`) unchanged — the wheel's libmlx.so
is the same, only the worker binary + `ane_resident.py` change.

## Verdict

**Cut: implemented, unit-tested, GPU A/B not run (soft budget exhausted).**

This lane implemented the relay-bypass worker-protocol change named in
`receipts/2026-09-19-encwall-v071-attribution.md` (EncWallTowardDivisor):
the C++ relay (`mlx-omarchy-ane-worker --serve`) parses frames between
the runner's stdin/stdout and the resident's socketpair, which costs
~12 host copies and 6 process-state transitions per payload round. The
change drops the relay entirely by:

1. Switching the resident's wire protocol from bundle INDEX to bundle
   NAME (the runner already has names; a small per-session name→index
   map is built inside `resident_child_loop`).
2. Adding `--relay-bypass` mode to `mlx-omarchy-ane-worker`: spawn the
   resident as before, then `splice(2)` bytes bidirectionally between
   `STDIN_FILENO` and the resident socketpair in two threads. EOF on
   either side tears the resident down. No parsing, no copy.
3. Adding a `relay_bypass` flag to `ResidentAneWorker`: when set, the
   runner builds the resident's wire format directly (`submit <name>\n`
   + `in <name> <len>\n` + bytes + `run\n`) and parses the resident's
   response (`iter\n` skipped, `out <name> <len>\n` + bytes, `done\n`).
   The existing `--serve` path is byte-identical when `relay_bypass` is
   false, so the default is unchanged.

## Proof (no GPU needed)

- **test_worker 16/16, 198 assertions**: all resident-session tests
  pass; one bounds-check test updated to the new API contract (the
  parent now throws `std::invalid_argument` on out-of-range bundle
  indices instead of dispatching to the resident which returned
  `DeviceFailed` — the parent can detect shape errors faster and not
  consume wire bytes).
- **test_ane_resident 10/10**: existing `--serve` protocol tests
  unchanged; the non-bypass path in `ResidentAneWorker` is byte-identical.
- **test_relay_bypass 3/3**: a scripted Python resident (`fake_resident.py`)
  speaks the resident's wire protocol directly; the runner round-trips
  one-process-one-load-many-submits, payloads with embedded NULs prove
  no filesystem write happens, and unknown bundles are rejected as a
  named `ResidentWorkerError`. End-to-end smoke at
  `/tmp/relay-bypass-build/test_sandbox/` proves 4 submits round-trip
  the resident protocol byte-identical and close releases the session
  cleanly.

## Diff stat

```
 overlay/mlx/backend/omarchy/ane/worker.cpp    |  26 +++--
 overlay/mlx/backend/omarchy/ane/worker.h      |  13 +++
 overlay/tests/omarchy/ane/test_worker.cpp     |  13 +--
 overlay/tools/coreml/ane_resident.py          | 136 ++++++++++++++++++++------
 overlay/tools/mlx-omarchy-ane-worker/main.cpp | 129 +++++++++++++++++++++++-
 5 files changed, 271 insertions(+), 46 deletions(-)
```

## A/B harness staged but not run

`encwall_relay.sh` at `/var/tmp/encwall-relay/`:
- 12 gated arms (AC serve ×3 base + 3 cand, ACO serve ×3 base + 3 cand)
  interleaved. AC launch / ACO launch / GPU-control arms deferred to
  follow the same v0.7.1 baseline-vs-candidate ladder as the previous
  lane (`encwall-v071`), but the change being measured is per-round
  protocol not per-call setup, so AC serve is the load-bearing cell.
- `take_release.sh` wraps the harness with `flock /tmp/m1-gpu.lock`,
  stops/restarts `llm-inference`, verifies `inode %i` never changes.
- Pre-window: `venv-identity-guard --expect df3d4e74c597956c` (the
  v0.7.1 libmlx.so pin) and worker-binary shasum.

`attr_row.py` is the parser from the prior lane (reused; the per-op
wall attribution is identical because the runner-side counters didn't
move).

## What the wall will (likely) move

The transport cut screen at `80ef5e16` (EncWallTowardDivisor) proved the
wall is round-trip-latency-bound, not copy/bandwidth-bound, and that
copy-chain removal moves the wall by ~−8 ms (noise). The relay-bypass
change removes the relay's PARSING (`getline`, `stdin.read`, `send_frame`
to socketpair, `recv_line/recv_bytes` from socketpair, `fwrite` to
stdout) — three more process-state transitions and two more C++ stdio
round-trips per round, all replaced by `splice(2)` (kernel pipe → pipe
or pipe → socketpair, zero copy in user space).

Per the prior lane's per-round p50 of 20-25 ms across reps and
~1.2 ms device compute on `a0`, a single splice-pump round should
recover 5-15 ms of the 21 ms/round. Median wall cut: estimate
1000-1500 ms on the AC serve cell (the prior receipt's 1023 ms
parent-read_ns is exactly the relay translation work).

## Pending

A/B on jw16 GPU window. The lane ran out of soft-budget before
coordinating the window with the peer fleet. The harness is staged
and self-checked; the next session that takes `agent/encwall-relay-bypass`
through `take_release.sh` will publish the wall numbers. Receipts
`2026-09-19-v071-ship.md`, `2026-09-19-encwall-v071-attribution.md`,
and `2026-09-19-q4-chainbatch-jw16` provide the baseline numbers for
delta.

## Artifacts

- Worktree: `~/src/mlx-omarchy-relay` (branch `agent/encwall-relay-bypass`),
  pushed at `d0b0b7bb`.
- jw16 staging: `/var/tmp/encwall-relay/{cand/bin/mlx-omarchy-ane-worker,
  cand/lib/ane_resident.py, encwall_relay.sh, take_release.sh,
  attr_row.py}`.
- Local scripts: `.local/encwall-relay/{encwall_relay.sh, take_release.sh}`.
- Build artifacts: `/tmp/relay-bypass-build/{mlx-omarchy-ane-worker-test,
  worker.cpp, worker.h, worker_libane.cpp, bundle.cpp, manifest.cpp,
  main.cpp, ane.h, libane/, doctest/, test_worker, test_sandbox/}`.
- Test sandbox: `test_ane_resident.py 10/10`, `test_relay_bypass.py 3/3`,
  `test_worker 16/16 (198 assertions)` on `/tmp/relay-bypass-build/`.
