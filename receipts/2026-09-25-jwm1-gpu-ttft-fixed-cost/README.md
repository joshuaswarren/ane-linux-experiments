# 2026-09-25 — jwm1 GPU TTFT fixed cost: scheduler component removed (RT), remainder decomposed — Jwm1Parity6

Owner: Jwm1Parity6 (jwm1 lane), coordinated with Jw16GpuSubmit (jw16
BarrierBench/QmvRoof lane). Stack: mlx-omarchy main ecda0fa33 wheel
+af73787, honeykrisp fork ICD, venv /var/tmp/jwm1-parity3-venv, GDN
fast+raw, MLX_DISABLE_COMPILE=1. Prior art:
`receipts/2026-09-25-jwm1-parity5-gpu-parity-m64` (fit: ttft = 195.9 ms
fixed + 4.81 ms/token, fixed cost repeats per fresh cache; dispatch
floor 3.10 us GPU + 3.7 us host per MLX pre+post barrier pair).

## 1. RT A/B on the GPU ttft probe (same stall family as the ANE lane)

The ANE lane found scheduler wakeup stalls inflating steps (~154 ms
bursts, killed by SCHED_FIFO; see
`receipts/2026-09-25-jwm1-qwen-ane-ttft-rt`). The GPU ttft-probe
(parity5 script, 10 fresh caches x 10 prompts) responds the same way:

| run | ttft_ms_med (13-tok mix) |
| --- | ---: |
| control (parity5 decomposition: 195.9 + 4.81 x tok) | ~258 |
| chrt -f 50 | **223.3** |

Per-record rows at RT (n=100) give the clean linear fit:

**ttft = 219.6 ms fixed + 1.19 ms/token** (was 195.9 + 4.81 without RT).

Reading: the old 4.81 ms/token slope was mostly wakeup jitter, not
compute — at RT the slope collapses to 1.19 ms/token. The remaining
~220 ms fixed cost is per-fresh-cache work inside the first `next()`
(cache_make 0.02 ms, iterator 0.06 ms, mx.eval 0 — everything is inside
the prefill forward): short-prefill compute through the GDN layers, the
short-prefill dispatch stream at the 3.10 us/dispatch barrier-edge
floor, and first-use buffer work. That — not scheduling — is the next
attack surface, and it is the piece the Mesa barrier fix addresses.

## 2. What remains, and where it lives

- Per-fresh-cache first `next()` (parity5: cache_make 0.03 ms, iterator
  0.12 ms, mx.eval 0) carries the rest: short-prefill compute through
  the GDN layers, the ~507-dispatch short-prefill stream at the
  3.10 us/dispatch barrier-edge floor, and first-use buffer work.
- Barrier attribution (Jw16GpuSubmit, source-level, mesa-1
  src/asahi/vulkan/hk_cmd_buffer.c ~343-360): every CmdPipelineBarrier2
  ENDS both compute and graphics batches ("the big hammer", the
  upstream author's own XXX perf comment). The candidate fix keeps the
  compute batch across compute->compute barriers (ride
  cdm_barrier_pending; split only on graphics->compute).
- Decode-side cross-check: my 6.8 us/dispatch total (3.10 GPU + 3.7
  host) vs Jw16GpuSubmit's ~9.5 us per-launch drain — one Mesa fix
  plausibly covers both.

## 3. Validation plan (jwm1, when the mesa-1 branch lands)

1. dispatch-floor bench A/B: MLX production barrier pair 3.10 us ->
   target <= 0.5 us.
2. 10-pass digest pin `dbf704971617fdfc` must hold — NOT sufficient by
   itself: on T6001 the barrier branch produced single-record digest
   flips in 2 of ~290 records (Jw16GpuLevers, prompt-7 single-point
   cascade), so jwm1 validation additionally runs the 10x10-pass
   interleaved rare-race battery before any verdict.
3. GPU contract (3 warmups + 10 reps, n=100) at chrt -f 50, all four
   cells vs the macOS bars; TTFT fit re-run for the new intercept.
4. Separate, already-safe: mlx-omarchy main `3232b1f5e` Q4 GEMV
   ROWS_PER_SLOT=2 (bit-exact by construction, +2.4% decode on T6001)
   goes through the standard 10-pass pin + contract on jwm1 first.

Lane split agreed with Jw16GpuSubmit/Jw16GpuLevers: they land on G13X
(jw16, pins bc519c03/dbf70497), I validate on G13G (jwm1, pin
dbf704971617fdfc).
