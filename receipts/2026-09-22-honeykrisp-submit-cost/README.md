# 2026-09-22 — Honeykrisp per-dispatch submit cost, decode path, m1max-host (m1max-host)

Lane: HoneykrispSubmitCost. **Verdict: the per-dispatch submit-cost hypothesis
is refuted. Decode is GPU-bound (96.2% busy). Host submit+record cost is
~10 us/token (0.06% of wall). The only measurable submit-side residual is a
uniform ~231 us firmware job-boundary latency x 3 jobs/token (4.3% of wall),
removable only by app-level submit batching (3 commits -> 1 per token), which
belongs to the mlx-omarchy backend (decodecut lane), not the driver. No
production driver change made; the diagnostic harness is committed.**

Host: m1max-host (M1 Max, G13C). Driver: joshuaswarren/mesa-1 @
5deac1c806 (system ICD, the system ICD). MLX wheel:
decodecut-venv `0.32.3.dev202609221401+diag.1493078` (agent/decode-dispatch-cut,
diagnostics build). Bench: `qwen38-mlx-bench.py` 10 prompts x 3 passes,
prefill 512, 32 new tokens, under `/tmp/m1-gpu.lock`. llm-inference was already
inactive (exit-code 1) before my runs; lock free. llm-inference left untouched
(not restarted by this lane).

## 1. Decode shape (before, production path)

Per token: **3.0 submissions, 3 CDM jobs, 567 dispatches** (tripel
243+243+81 dispatches; one control stream per submission — Honeykrisp merges
adjacent dispatches into one CS).

## 2. Per-submit cost breakdown (AGX_SUBMIT_TRACE, `/var/tmp/hkc-submit/trace2.log`)

| component | per submit | per token | share of 16.05 ms/tok |
|---|---:|---:|---:|
| command-buffer/payload build | 1.3 us p50 | 3.9 us | 0.02% |
| vkQueueSubmit ioctl | 21.8 us p50 | 65 us | 0.41% |
| dispatch recording (profiler, upper bound) | — | 0.90 ms | 5.6% host, overlapped |
| **GPU busy (kernel execution)** | 5.60/5.53/4.30 ms | **15.42 ms** | **96.2%** |
| GPU job-boundary gaps | ~231 us x 3 | 0.69 ms | 4.3% |

Notes:
- QueueSubmit never blocks on the production path (p99 82 us, max 0.6 ms;
  zero >1 ms). The 3.6 ms p50 blocking seen under the MLX GPU profiler was
  the profiler's own per-dispatch ALL_COMMANDS barriers backpressuring the
  queue (profiled decode shows 25.4 tok/s vs 62.8 unprofiled) — profiling
  artifact, not a real cost.
- Command-buffer rebuild and descriptor updates are noise-level (build p50
  1 us; Honeykrisp reuses CS state, no per-dispatch descriptor churn visible).
- The ~231 us boundary latency is uniform across all 3 boundaries (intra- and
  inter-token): firmware kick/job-switch latency, not host feed delay (host is
  ~5 ms ahead when each job starts).

## 3. decode tok/s + identity (m1max-host)

| arm | decode tok/s (median) | ordered-records sha256 |
|---|---:|---|
| baseline (system driver, no trace) | **62.77** | `bc519c03c4ef5fd1…` |
| traced driver + AGX_SUBMIT_TRACE | 62.30 | `bc519c03c4ef5fd1…` (identical) |

Identity HELD across stock and traced arms (same wheel, same outputs).
Context reference digest `ac1b2695…` was produced on the production
integration wheel; this lane's gate is before/after on the same wheel — exact
match.

## 4. Known lever, recorded decision (not re-litigated)

The 4.3% boundary gap and part of job-busy ride the per-launch CDM barrier:
mesa-1 `5deac1c806` message records the 12-round packaged A/B — barrier trim
on G13X gives **short decode +13.0%** but **ctx1053 -3.17%**, so G13X stays on
the sink by decision of 2026-09-19 (in-repo). Any flip of that trade-off is
Joshua's call, not this lane's.

## 5. Change landed (local branch, not pushed)

mesa-1 branch `hkc-submit-cost-trace`, commit `f2cc0d3a546`: AGX_SUBMIT_TRACE
harness in `hk_queue.c` — per-submit host build/ioctl timing + per-CS GPU
start/end stamps via a kernel timestamp ring (4096 slots, ts_freq 1 GHz
confirmed). Zero cost when `AGX_SUBMIT_TRACE` unset; digest unchanged with it
set. Built at `/var/tmp/hkc-submit/build2` (`trace2.icd.json`), no system
driver touched.

## 6. Not done / follow-ups

- m1-host arm: m1-host is booted to macOS (Main fleet operation, 2026-09-22);
  cannot run the Omarchy decode stack there. Repeat sections 2-3 on m1-host
  when it returns to Linux.
- The real submit-side lever (3 commits/token -> 1, removing 2 x ~231 us
  kicks = ~+3% decode, plus removing any sampling stall) is an mlx-omarchy
  encoder change (commit batching across the token forward pass) — handoff to
  the decodecut lane suggested.
- GPU busy itself (15.4 ms/tok) is kernel-execution bound — out of scope per
  assignment (kernel mix exhausted; QmmVecQ4 at 90% of copy ceiling).
