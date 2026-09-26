# T8103 (m1-host) Vulkan submission/synchronization path: measured end-to-end, sync-bound premise falsified (2026-09-25)

Owner: Jwm1Submit2. Host: `m1-host` (T8103 M1, Omarchy, kernel `7.1.13-3-2-ARCH`,
ICD honeykrisp `7faf04c` at `/usr/local/lib/libvulkan_asahi.so.7faf04c`,
installed stack `/var/tmp/jwm1-parity3-venv` wheel
`0.32.3.dev202609252152+bfe2ddc`). GPU window coordinated with the ANE lanes
(AneClockM1 slot stood down; one coordinated reboot mid-lane with
M2FwStart-2's yes; final gates re-run on the clean post-reboot box).

## 1. Assignment and verdict

Assignment: measure the Vulkan submission/synchronization latency chain on
T8103 for one small dispatch and the mel/TDT/decode patterns; fix the
dominant segment at its source; hold the pins.

Verdict: **the dominant segment in every pattern is GPU kernel execution.
The host submission/synchronization path is <0.5% of wall in all three
serving shapes.** The premise that spawned this lane — dispatch/submit/sync
latency bound (mel "0.9 ms exec inside 21.5 ms wall"; TDT "~120 us
submit-sync per dispatch") — is **falsified by direct measurement**. The
runtime is already submission-optimal: one submit per iteration, in-order
completion timeline, pipelined ring (depth 4), dispatcher thread + recovery
ladder.

## 2. Method (all on m1-host, GPU lock held)

- ftrace: `gpu_scheduler` (`drm_sched_job_queue/run/done`) + `dma_fence`
  events, `trace_clock` mono (CLOCK_MONOTONIC), correlated with host
  `time.monotonic_ns` markers. Per-job segments parsed from
  `raw/mel_trace.txt`, `raw/trace.txt`.
- Vulkan timestamp-query microbench (`raw/vk_lat.c`, built with glslc+gcc;
  G13G B1, timestampPeriod 1 ns, 64-bit timestamps, absolute GPU times via
  calibration submit). Modes: single / poll / spinblock / batch±barrier.
- `HK_PERFTEST=nobarrier` (mesa `hk_CmdPipelineBarrier2` batch-end removal)
  decode A/B — measures the entire barrier/CS-switch pool with zero code.
- iso-vs-flood kernel timing (same dispatch isolated vs 50-deep in one
  submit) — separates clock ramp / queue depth from real execution.
- Runtime trace snapshot (`mlx_omarchy_trace_snapshot`): submits, dispatches,
  commits per window. `[rtmod]` SUBMIT/COMMIT-NOOP log counts.

## 3. One small dispatch, full chain (microbench)

| segment | p50 | notes |
|---|---:|---|
| record (begin+dispatch+barrier+end) | 0.7–2.8 us | |
| vkQueueSubmit ioctl | 18–47 us | never blocks |
| GPU start (empty queue) | 0–50 us | job picked up immediately |
| GPU exec, single dispatch job | 30–61 us | firmware job overhead; real compute <1 us |
| per-dispatch marginal, same CB, +barrier | 4.0–4.4 us | |
| per-dispatch marginal, same CB, no barrier | 0.06–0.47 us | |
| GPU-complete -> host wake (block vkWaitSemaphores) | 102 us | |
| GPU-complete -> host wake (poll counter) | 83 us | |
| GPU-complete -> host wake (spin 200 us then block) | 253 us | **worse** — spin keeps the CPU busy and delays the completion kworker; do not adopt |
| wall, one dispatch submit->wake | 174 us | |

CPU-side: `schedutil` 1332–2064 MHz under decode load (not parked);
`apple_idle` has only WFI (1 us) + CPU PD (10 us) — CPU freq/idle-state
levers are moot for this lane.

## 4. mel frontend (whole pipeline, 3001x512 fixture)

ftrace, 10 reps, 1 submit/rep, 6 dispatches/rep:
- queue->run: 14–47 us; run->done: **21.0–21.9 ms flat**; host turnaround
  (done -> next queue): 0.12–0.83 ms; host record ~27 us/rep.
- iso vs flood: isolated dft 10.87 ms == 50-deep queued dft 10.64
  ms/dispatch — **no clock ramp, no queue-depth effect; the wall is
  execution.**
- Stage budget (per profile): DFT 11.0 ms, mel-projection pair 7.7 ms,
  stats 1.6 ms, frames 0.9 ms, normalize 0.6 ms.
- The prior "0.568 ms queued dft" was measured on a different workload
  shape / under profiler-inflated barriers; the 21.5 ms wall is real work
  in the DFT and projection kernels.

## 5. TDT chain (device-chained slots)

- Python makes ONE `mx.eval(out.token_ids)` per chunk; measured submit
  count on the serving chain (`chain_bench` 64 slots x 3 reps): **18
  `[rtmod]` SUBMITs total = ~2 per 64-slot chunk** (6 round trips per
  137-148 ms run, <0.1% of wall). The chain is submission-clean;
  execution-bound.
- validate_chain (golden, post-reboot clean box): **5/5 PASS**
  (tokens/frames/durations/hidden/cell), best-of-5 host 417.0 ms vs
  **chain 137.3 ms (3.04x)** — inside the receipted 133-147 ms band.
- Prior per-kernel profile: 728 us/slot x 192 slots (chains 247, window
  joint 199, fold/fold_proj/control 281 — the three grid-1 kernels ~94 us
  each). 6->3 kernel fusion already falsified (bit-exact single-workgroup
  form 4.7x slower, `agent/jwm1-parity10-tdt`).

## 6. Qwen decode (installed stack, contract shape)

- 1 submit/token, 507 dispatches/token. Host runs ~1 token ahead (ring
  depth 4): GPU idle between tokens 30–60 us only. Job run->done 25.3 ms
  ≈ the whole 25.5 ms/token wall — GPU-side.
- **HK_PERFTEST=nobarrier A/B: 38.96 -> 38.81 tok/s — the entire
  barrier/CS-switch pool is ZERO on T8103/G13G.** (`hk_CmdPipelineBarrier2`
  ends the compute batch per barrier, but `merge_control_streams` plus
  cheap batch switches make barriers free here; the "11.4 us/dispatch"
  earlier estimate was attribution error, not barrier cost.)
  **Chip-specific:** the same pool is real on T6001/G13C — the m1max-host lane
  moved decode 80.9-81.2 -> 83.5-83.8 tok/s (+3.2%, p<0.01, 10x10
  interleaved, pins `dbf70497` bit-exact x100 records) with the corrected
  per-launch CDM barrier (0x17f flush set) + dependency-tracked barrier
  (`receipts/2026-09-25-jw16-levers5`, ane-linux-experiments `e5e82aa`).
  Barrier cost is chip/lineage-specific, not SoC-agnostic.
- Console `[rtmod]` logging: 150 submit lines + 146 COMMIT-NOOP lines per
  ~1.6 s decode window — unconditional fprintf hygiene, ~0.1% of wall.

## 7. Fix candidates from the assignment classes — measured verdicts

| candidate | verdict |
|---|---|
| fewer host round trips (GPU-resident loops, timeline chaining, batched CBs) | already implemented in the runtime (1 submit/iter, in-order timeline, ring depth 4); nothing left |
| spin-then-block fence wait | measured WORSE (253 vs 102 us); do not adopt |
| prerecorded command buffer reuse | ring reuse already lands per-slot; no measurable residual |
| CPU frequency / idle-state wakeup | CPU not parked under load; wake 83–102 us only matters per join, and joins are 1/iteration; GPU freq not exposed (no devfreq/clk node) |
| Mesa/asahi latency | barrier pool = 0 (NOBARRIER A/B); submit ioctl 18–47 us x1/iter ~0.1%; no asahi-side latency found worth a change |
| [hygiene] unconditional `[rtmod]` fprintf per submit/noop-commit | real but ~0.1%; should be env-gated; cosmetic |

**No submission-path fix can move the pass rule.** The parity gap lives in
kernel execution, which the measured numbers hand to the owning lanes:

- mel: DFT kernel (3001x512 naive, 11.0 ms) + projection pair (7.7 ms);
  bit-exact rewrite ceiling: 21.5 -> ~3 ms per chunk.
- decode: dispatch count (507/tok) + kernel mix (qmm/elementwise); macOS
  wall 21.25 ms/tok vs our 25.3 ms job.
- TDT: grid-1 kernel costs (94 us x3 x192); fusion falsified in the
  workgroup-1 form; per-CS GPU stamps (AGX_SUBMIT_TRACE, commit `f2cc0d3a`,
  currently only on the other host's clone) would resolve the split.

## 8. Gates on the installed result (post-reboot clean box)

Installed state verified: ICD `/usr/local/lib/libvulkan_asahi.so.7faf04c`
sha256 `09e3527dee4a365ee29085637c266291396666afb0039a6932b5be9dc7dd6a80`,
wheel `0.32.3.dev202609252152+bfe2ddc` in `/var/tmp/jwm1-parity3-venv`,
stock `ane` loaded refcnt 0, uptime 8 min at gate start.

Pins (all PASS, `raw/pins-1.json` / `raw/pins-3.json` /
`raw/contract-final.json`):

| pass | digest | expected |
|---|---|---|
| 1-pass | `486872c410629f1d` | identical PASS |
| 3-pass | `bc519c03c4ef5fd1` | identical PASS |
| 10-pass | `dbf704971617fdfc` | identical PASS |

Full contract vs macOS (10 passes x 10 prompts, n=100, greedy, 32 new
tokens, prefill 512, clean post-reboot box):

| metric | installed result | macOS | ratio | verdict |
|---|---:|---:|---:|---|
| decode tok/s | 39.17 | 47.05 | 0.83x | FAIL (unchanged, as predicted: no submission-path lever exists) |
| ttft tok/s | 57.11 | 99.12 | 0.58x | FAIL |
| pure prefill tok/s (512) | 236.72 | 343.73 | 0.69x | FAIL |
| e2e s (median of 100) | 1.0140 (min 0.979, max 1.080) | 0.7898 | 1.28x | FAIL |

Before/after for this lane: **before 39.24 / after 39.17 decode tok/s** —
the delta is run-to-run variance on the same bit-exact pin (`dbf70497` both);
the lane's conclusion is that no pin-safe submission/sync change exists that
moves these numbers, and the measurement proves why (§7). Parakeet golden
(validate_chain) 5/5 PASS, chain 137.3 ms; corpus gate **6/6 PASS rc=0**
(emissions 104/0/0/28/101/104 — identical to the receipted pattern,
`raw/corpus.out`). The Parakeet full-pipeline bar (298.6 vs macOS 271 ms)
is unchanged by this lane and is owned by the mel-DFT / TDT-kernel /
ANE-clock buckets named above.

## 9. Coordination record

- AneClockM1 held the ANE slot per program rules (corrected offset proof
  verified: 0xa04 from map PA 0x26b868000); stood down for my GPU window;
  declined a re-run after the acg write path hard-reset the box during
  AneAcgT8103's attempt (their receipt `9288833`, baseline clean at
  0x80000000, acg_hack=1 = PMU boot error — treat the write arm as
  falsified on this box).
- AneAcgT8103's acg slot + one m1-host reboot executed mid-lane WITH
  M2FwStart-2's yes; my lane idled during their slot; no USB/ACM contact;
  all final gates re-run on the clean post-reboot box.
- SoC-agnostic findings shared with Jw16Levers5/Jw16Levers6 via hub;
  Jw16Levers5's T6001 contrast (barrier pool real there, +3.2% pins-held)
  folded into §6.
