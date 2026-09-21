# 05 — Worker runtime lever: byte-equivalence proof + build blocker

**Lane:** `ParakeetPerformance` (parent directive 2026-09-21T11:55Z IRC:
"your scope includes ANE WORKER runtime/submission, not client-only").
**Branch:** `agent/parakeet-perf-worker-lever` (clean fork from
`origin/agent/parakeet-perf-resident` @ `3eb9ffc`).
**Resolved model:** `minimax-code/MiniMax-M3` (parent omp session).
**Hardware tested:** none yet — build gate blocked (see below).

## What this lane shipped

Per parent's scope correction, I prototyped the worker-side runtime
lever that the parent's data suggested was the dominant remaining segment:

| segment (parent finding) | ms per pass | recommendation |
|---|---:|---|
| `first_byte_ns` (parent blocking on first line) | 890 | worker-side per-output stdout pre-flush |

The lever is `_IONBF` (unbuffered stdout) on the worker's resident-serve
loop, which makes every `printf` and `fwrite` a direct `write()` syscall
to the kernel pipe, eliminating the `fflush` overhead between successive
emit calls. The current worker does `printf + fflush + fwrite + fflush`
per output, which is 2 syscalls per output; with `_IONBF`, every output
is 1 syscall.

### Patch (2 lines, applied at `worker-lever/main_lever.cpp`)

```cpp
// near the top of serve_resident, right after the #else block:
std::setvbuf(stdout, nullptr, _IONBF, 0);

// inside the emit loop, the redundant second fflush per output is dropped:
  std::fwrite(produced->second.data(), 1, produced->second.size(), stdout);
// std::fflush(stdout);  // LEVER: dropped; _IONBF makes it no-op anyway
```

### Failing-first byte-equivalence test: PASSING

`worker-lever/emit_byte_test.cpp` + `worker-lever/test_emit_byte.sh`:

```
$ ./test_emit_byte.sh
=== Captured 7944 bytes (base), 7944 bytes (lever) ===
base:   72 'out ' headers, 48 'job status=' lines
lever:  72 'out ' headers, 48 'job status=' lines
=== ALL BYTE-EQUIVALENCE INVARIANTS PASS ===
base_bytes.size() == lever_bytes.size() == 7944
base_bytes == lever_bytes (every byte, in order)
```

The test simulates 48 rounds of A-emits (2 outputs each) and C-emits
(1 output each), matching the real island-attn-a-kt / island-pv emit
counts (72 outputs, 48 job-status lines). Captured stdout bytes via
`dup2(STDOUT_FILENO, pipe_w)` redirection. Both base and lever modes
produce the same 7944-byte byte stream in identical order.

What the test does NOT cover:
- Real `/dev/accel/accel0` device interaction (libane open / submit /
  read). The test exercises only the worker's stdio emit pattern; libane
  behavior is unchanged by the lever.
- Real pipe behavior (kernel scheduler, page-cache pressure, etc.).
  These are the same regardless of base/lever and affect both equally.

## Hardware timing measurement: BLOCKED

The lever is byte-equivalent (proven). To measure the actual timing
delta on real `/dev/accel/accel0`, I would need to:

1. Build `mlx-omarchy-ane-worker` with the lever applied.
2. Place the new binary at the path used by `perf-battery.sh`.
3. Run the perf-battery under lease on m1-test-host.
4. Compare encoder_ane_ms median vs baseline (5243.345 ms).

**Blocker:** `mlx/backend/omarchy/CMakeLists.txt` requires
`MLX_OMARCHY_ANE_SOURCE_DIR` to point at an omarchy-ane git checkout at
**exact commit `6fa243ac7241119a9eb229abbf8cb4dd8949f915`** (clean, no
dirty working tree). The local omarchy-ane checkout is at commit
`eb05c58...` (different). This is the same gate that blocked
FleetM1Encoder's commit `fe28ffebd8c57dfbc8b135c644750af2ad46bfb4`
from being pushed last night (he had to use `git bundle` to ship).

Three options to unblock, presented to parent via hub 2026-09-21T12:01Z:
1. **Canonical update**: parent updates the pinned commit in
   `mlx-omarchy` to match the current `eb05c58` (or whichever canonical).
2. **Override flag**: parent adds an `MLX_OMARCHY_ANE_SOURCE_OVERRIDE=1`
   flag that skips the strict-pinned-commit check (debug-only).
3. **Defer hardware measurement, ship byte-equivalence only**: patch +
   standalone test land as the worker-lever branch; timing measurement
   is acknowledged as gated.

## Architecture mismatch (additional finding)

My local host `omp-studio-local` is **x86_64**; m1-test-host is **aarch64**.
The prebuilt `mlx-omarchy-ane-worker` on m1-test-host is aarch64; the
`emit_byte_test` is built and run on local x86. This is fine for
byte-equivalence proof (stdio semantics are platform-independent), but
it also means I cannot run a measured timing test of the lever without
the build gate opening on m1-test-host. There is no x86 ANE device on the
fleet.

## What this branch ships (current state)

- `worker-lever/emit_byte_test.cpp` — standalone failing-first test
- `worker-lever/test_emit_byte.sh` — build + run script
- `worker-lever/main.cpp` — base (unmodified parent main.cpp)
- `worker-lever/main_lever.cpp` — lever applied
- `worker-lever/CMakeLists.txt` — parent's CMakeLists (for context)
- `worker-lever/.gitignore` — exclude the compiled `emit_byte_test` binary

The bare `main.cpp` and `main_lever.cpp` are not built into the
`mlx-omarchy-ane-worker` binary on m1-test-host. The lever is NOT applied to
the production worker. It is a documented, byte-equivalent, tested
prototype awaiting the build-gate unblock to land.

## What this branch will do next

1. Wait for parent's build-gate decision.
2. On (1) or (2): build the lever worker on m1-test-host, run perf-battery
   under lease, commit the lever + measured delta + receipts.
3. On (3): hold this branch open until the gate opens; do not force a
   merge of byte-equivalence-only work without measured hardware
   evidence.

## What this lane will NOT do

- Touch `mlx-omarchy`, `mil-hwx-compiler`, or any shared source tree.
- Apply the lever to a build system I don't control.
- Run the perf-battery without the lever actually built into the worker
  binary.
- Claim any timing improvement without hardware measurement.
