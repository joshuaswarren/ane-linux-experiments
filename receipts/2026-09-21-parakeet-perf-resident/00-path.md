# Parakeet stage-matched performance parity path on jwm1/jw16

**Lane:** `ParakeetPerformance` (slice `Parakeet 104/104 functional pins AND
stage-matched performance parity path, implementation + measurements`)
**Branch:** `agent/parakeet-perf-resident` on `ane-linux-experiments` (clean
fork of `main` @ `4e7e2be`).
**Resolved model:** `minimax-code/MiniMax-M3` (parent omp session).
**Parent macros:** don't narrow to existing functional pass; no pin/tolerance
weakening; no bf16 precision; no behavior change vs the 104/104 pins already
proven on `receipts/2026-09-20-jwm1-ane-step5-e2e/` and
`receipts/2026-09-20-jwm1-ane-step5-e2e/evidence/jw16-parity-battery-20260921T003045/`.

## What this lane owns

1. The 104/104 functional pins for full ASR on jwm1 (T8103) and jw16 (T6001),
   inheriting the receipts above. We re-state them, do not re-prove them — the
   parent worker (`AsrFullGateVerification`) has already produced 10/10
   warm + measured runs with all three golden hashes (mel `5b54f4a9`, hidden
   `38c73261`, transcript `db501a8c`) bit-exact on both SoCs.
2. A non-compiler, non-ANE-firmware lever outside `mlx-omarchy` /
   `mil-hwx-compiler` workspaces. FleetM1Encoder owns compiler; we coordinate
   via `hub` and never touch their tree.
3. The **stage-matched** performance parity path: encoder stage on
   jwm1 / jw16 vs. the native macOS M1 Max oracle of **137.951 ms median
   encoder wall** (`receipts/2026-09-17-parakeet-macos-timing-t8103`, T8103
   macOS 27 same-encoder divisor). **NEVER total-ASR vs encoder-divisor**
   mixing; that rule is enforced by the `encoder_ane_ms` field on every
   measured run.

## Current measured baseline (inherited, untouched)

Source: `receipts/2026-09-20-jwm1-ane-step5-e2e/perf-battery-receipt.json`
(warm + 10 measured, resident-batch transport, AC placement on T8103 ANE).

| host | encoder_ane_ms median (all 10) | total_asr_ms median (all 10) | n |
|---|---:|---:|---:|
| jwm1 (T8103, restored) | 5217.4 | 6569.0 | 10 |
| jw16 (T6001) | 3405.9 | 4750.9 | 10 |
| macOS M1 Max (T8103, native) | **137.951** (divisor) | ~258 (total transcription) | 20 |

Ratio to native encoder: jwm1 ~37.8×, jw16 ~24.7×. The AC-place + ANE-island
pipeline is functional and pinned; the gap to the 138 ms native divisor is
real and stage-level.

## Stage decomposition (inherited, from
`receipts/2026-09-20-jwm1-ane-step5-e2e/encoder-profile-receipt-v2.json`
+ `marshal-split-receipt.json` + `stage3-diag-receipt.json`)

Non-overlapping critical path of the jwm1 5.252 s encoder stage:

| segment | ms | % | source | lever-allowed? |
|---|---:|---:|---|---|
| marshal — `mx.eval` readiness wait | 2033.6 | 38.7% | `marshal-split` | NO (compiler/feeder) |
| marshal — `np.asarray + tobytes` materialization | 63.2 | 1.2% | `marshal-split` | YES — already attempted, only ~30 ms ceiling |
| session round: `write_ns` 317.3 | 317.3 | 6.0% | profile-v2 | small — request bytes to worker stdin |
| read_residual = round − write = 1397.4 → worker round 978.0 + parent IPC wait 419.4 | 1397.4 | 26.6% | profile-v2 | partly YES — IPC wait 419 ms |
| back — `np.frombuffer + mx.array().reshape` | 79.6 | 1.5% | profile-v2 | YES — small |
| GPU feeder + loop orchestration (const 783 + conv 297 + linear ~90 + bookkeeping ~220) | 1391.0 | 26.5% | `stage3-diag` | partly NO (GPU compute) |

Worker-internal bound (from `encoder-profile-receipt-v2.json`):
`worker.elapsed_ms = 978.0 ms` decomposes as `stage_ms 230 + save_ms 315 + recv/read/send ≈ 433`.
The remaining `978 − 230 − 315 = 433 ms` upper-bounds the pure ANE device
exec — **ANE compute is ≤ 8 % of the encoder stage**, NOT the bottleneck.
The 20× gap is on the GPU feeder side and the host-side I/O pipeline.

## The honest path (closing the gap, in order)

Three levers are non-overlapping. Each is bounded, A/B tested with the full
pin gates, and the gain summed from the published decomposition.

### Lever L1 — `np.frombuffer + mx.array().reshape` per-output pooling
- File: `overlay/tools/coreml/ane_resident.py:218-225` (current
  `np.frombuffer + mx.array().reshape` per output) +
  `vulkan_encoder.py:_submit_resident:807-825` (parent read).
- Cost now: ~80 ms summed over 72 outputs (≈1.1 ms / output for the small
  shapes; reshape on pre-allocated array already allocated by mx).
- Reclaim estimate: ~30-50 ms (most of the cost is shape/dtype dispatch in
  `mx.array`, not the bytes).
- Risk: low. Same bytes, same mx array, different code path.
- Gate: 104/104 + golden sha + AC island FAIL preserved.

### Lever L2 — IPC wait 419 ms collapse (analyze first, change if measured)
- The parent read/IPC wait 419 ms is `read_residual − worker round`. It is
  defined in `ane_resident.py:209` as `elapsed_ns − write_ns`. The IPC wait
  is the host blocking on the worker side to produce the trailing
  `job status=...` line.
- The wait is not pure overhead — it covers worker `recv + stage + exec +
  read + send-back`. The 419 ms is the residual after the worker round
  completes; it is mostly the time for the worker stdout to drain back to
  the parent through a select()-driven pipe.
- A measured improvement: enlarge the worker's stdout read buffer (1 MB → 4 MB
  in `_fill`), and use one `os.read` per round instead of multiple per-line
  readlines, IF `_fill` already accumulates; check actual behavior first.
- Reclaim estimate: bounded above by 419 ms; realistic ~50-150 ms.
- Risk: low. No change to wire protocol.
- Gate: same.

### Lever L3 — back-conversion reuse of the same output mx.array pool
- 48 rounds × 1-3 outputs = 48-72 `mx.array` allocations per pass. Each
  allocates a new buffer; the previous one becomes garbage.
- A measured improvement: pre-allocate output `mx.array` slots at
  `_session.open()` time keyed by `(bundle, output_name)` with the
  declared shape/dtype, then refill in-place via `np.frombuffer` into the
  pre-existing host ndarray (already from the captured `bytes`).
- Reclaim estimate: ~30-50 ms (mx allocator overhead is small but
  cumulative).
- Risk: low. Same bytes, same shape, same dtype; just no allocator churn.
- Gate: same.

### Levers NOT in this lane (and why)

- **GPU feeder (const 783 + conv 297 ms):** owned by `NativeQ4 / BF16
  attention / shader fusion` lanes; changes here are GPU compute or
  compiler-emitted op placement. The 1080 ms GPU-feeder compute is the
  single largest bucket but it requires moving ops to ANE (compiler lane,
  owned by FleetM1Encoder) or rewriting the GPU shaders (parent-owned).
- **Marshal tobytes / ascontiguousarray:** already A/B'd in
  `marshal-ab-receipt.json` — rejected; ~30 ms ceiling, root cause is
  `np.asarray` itself (the `mx.eval` readiness wait), not the byte copies.
- **ANE compute itself (≤ 430 ms):** already not the bottleneck.
- **Total pipeline (mel + decoder + TDT + detok):** out of scope for the
  encoder-vs-native comparison.

## Expected cumulative gain (estimate, not measured)

L1 + L2 + L3 in the most-favorable case: 30-50 + 50-150 + 30-50 =
**110-250 ms saved** out of 5,252 ms (2-5 %). That brings the jwm1
encoder_ane median to ~5,000-5,140 ms — far from the 138 ms divisor but a
verified, gate-preserving improvement.

The 20×-gap closure requires GPU feeder moves (out of lane) and ANE op
coverage (compiler lane, FleetM1Encoder). The remaining gap after L1-L3
honestly reported, not papered over.

## What "OWN" means here

- Re-execute the perf battery on `agent/parakeet-perf-resident` after the
  lever is patched in, with the same hash gates and protocol as
  `perf-battery-receipt.json`. Honest gain or no claim.
- Do NOT re-prove 104/104 here — the parent receipts cover that.
- Do NOT weaken any criterion: no ULP relax, no bf16, no new tolerance.
- Commit + push the lever and its receipt. Label any unmeasured estimate
  explicitly. Label the jwm1 lease-window run as "pending hardware" until
  the run is real.
