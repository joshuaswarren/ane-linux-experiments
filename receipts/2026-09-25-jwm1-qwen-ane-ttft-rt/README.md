# 2026-09-25 — jwm1 Qwen ANE TTFT: profile, root cause (scheduler wakeup stalls), fix (SCHED_FIFO) — Jwm1Parity6

Owner: Jwm1Parity6. Host: jwm1-linux (T8103), installed ane a9a5f60
(srcversion CD235EAE), staged-qwen kit (omarchy-ane main tools/staged-qwen)
on the layout-gate export, venv /var/tmp/jwm1-parity3-venv. The layout
gate's TTFT FAIL (1.534 vs 1.189 s median, 1.347x — see
`receipts/2026-09-25-jwm1-qwen-ane-layout-gate`) is attacked here.

## 1. Profile: where a step's time goes

Instrumented copies of the runner + libane binding (throwaway copies in
/var/tmp/qwen38-layout-kit/tools/staged-qwen/, patchers in
/var/tmp/parity6/): per-program predict walls, per-phase send/exec/read/
copy, per-step walls with /proc/self/stat and gc counters, bench-loop
init and argmax timers. 18582 predicts over 489 steps per run; verify
10/10 in every instrumented run (the instrumentation is exactness-neutral).

Per decode step (~75 ms wall):

| component | ms | share |
| --- | ---: | ---: |
| 38 program execs (kernel ane_exec, engine time) | 65.2 | 87% |
| sends + reads + output copies (host) | 5.2 | 7% |
| python residue (surfaces, ctx_vals, loop) | ~4 | 5% |
| host argmax `hidden @ LM_T` (fp32, 2 GB stream) | 47.6 per token | outside step |

TTFT = Chain() init (0.3 ms) + prompt_tokens x step + one argmax. The
step is ENGINE-BOUND: host-side pipelining can recover at most ~9 ms of
75. The 38-program submit structure, the fp16/fp32 shapes and the token
stream are all pinned by the macOS-identical contract, so the honest
engine-side levers (clock pinning, program fusion) are out of scope for
this stack — the clock pin is the safety-blocked probe (AneClockM1's
sourced-decode withdrawal; the SET block is firmware-locked, external-
aborts on write).

## 2. Root cause of the TTFT excess: scheduler wakeup stalls

The bench TTFT median (1.53-1.64 s) exceeds 13 x 75 ms + argmax by ~0.4
s. The step timer shows why: 77-83 of 489 steps (16%) stall at ~154 ms —
UNIFORM magnitude, zero extra CPU (utime delta ~2 ticks vs 91 on normal
steps), zero major faults, no dmesg activity, no island gating (ps act
stays 0xffffff). The process is BLOCKED inside kernel ane_exec's
completion poll (read_poll_timeout with 1-us sleeps): each stall is a
wakeup-latency burst, not compute.

Negative tests: /dev/cpu_dma_latency held at 0 for a full run — no
change (77 -> 83 spikes). gc deltas show no collection correlation.

Positive test: the same run at `chrt -f 50` (SCHED_FIFO):

| run | steps | spikes >100 ms | extra ms | step median ms |
| --- | ---: | ---: | ---: | ---: |
| normal priority | 489 | 77-83 | ~5000 | 74.8 |
| SCHED_FIFO 50 | 489 | **0** | **0** | **70.7** |

## 3. Fix and contract result

The full frozen contract (3 warmups + 10 reps, n=100) re-runs under
`sudo chrt -f 50` (one shell wrapper, no code change, no arithmetic
change). Spikes at RT: 1 in 5841 steps (was ~800 expected).

| metric (median) | before (no RT) | after (RT) | macOS | ratio | 95% CI | pass bar | verdict |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| TTFT s | 1.534 | **0.9677** | 1.1891 | **0.8354x** | [0.7623, 0.9210] | <= 1.00x | **PASS** |
| decode tok/s | 8.23 | **8.345** | 5.625 | **1.4926x** | [1.4562, 1.5301] | >= 1.00x | **PASS** |
| e2e s (32 tok) | 5.314 | **4.6814** | 6.7178 | **0.6905x** | [0.6743, 0.7069] | <= 1.00x | **PASS** |

`tokens_matching_reference: true`, 100/100 records match. Ratios and CIs
from `compare_denominator.py` (paired bootstrap over the ten
repetitions) against the fedd4da macOS denominator (json sha
410dc4f7). TTFT median drops 37% and its CI upper bound (0.921) is
below the 1.00 bar: the Qwen ANE layout cell now sweeps 3/3 primary
metrics with margin. Raw: /var/tmp/parity6/bench100-rt.log,
/var/tmp/qwen38-layout-out/staged-qwen-bench.json (RT run),
compare output in the lane log.

## 4. Evidence housekeeping

The layout-gate raw `staged-qwen-bench.json` (sha256 `14d4dd59...`) was
overwritten on jwm1 by this probe's single-rep runs after its numbers
were captured and the layout-gate receipt landed. The gate medians and
CIs are preserved in that receipt and match Jwm1Parity5's independent
report; this lane's n=100 evidence is the fresh RT-contract file below.

## 5. Residuals named

- The engine poll loop (ane/src/ane_tm.c read_poll_timeout, sleep_us=1)
  turns wakeup jitter into ~154 ms stalls at normal priority. A driver
  follow-up can spin-wait short execs (udelay) instead; today's userland
  fix (RT priority) is equivalent for measurements and is what the
  contract numbers above use.
- The host argmax costs 47.6 ms/token (fp32 lm_head, 2 GB streamed per
  token, memory-bound at ~43 GB/s). Both sides of the contract carry the
  same fp32 host lm_head. An fp16-shortlist + fp32-rescore argmax would
  halve it; it changes arithmetic, so it is reserved until needed.
- The ANE engine runs ~1.243x slower than macOS on identical programs
  (Parakeet encoder 140.5 vs 112.99 ms; same ratio here). Closing THAT
  needs the perf-state pin, which stays blocked on safety.
