# 2026-09-25 — jwm1 ANE "scheduler stall" root-caused to CPU-cluster DVFS coupling; driver-side boost lands the Qwen ANE cell at normal priority — Jwm1Parity7

Owner: Jwm1Parity7. Host: jwm1-linux (T8103, Omarchy 7.1.13-3-2-ARCH).
Denominator: macOS Qwen ANE run at ane-linux-experiments `fedd4da`
(`receipts/2026-09-25-m1-ane-clock-macos/qwen-ane-full/qwen38-macos-ane.json`,
sha256 `410dc4f7…`). Stack: staged-qwen kit + layout ANEC export as in
`receipts/2026-09-25-jwm1-qwen-ane-layout-gate` (venv
`/var/tmp/jwm1-parity3-venv`, runner `/var/tmp/window.sh`).

## 1. The premise was wrong: the ~154 ms stalls are not wakeup latency

`receipts/2026-09-25-jwm1-qwen-ane-ttft-rt` blamed the ane_exec completion
poll (read_poll_timeout, 1 us sleeps) for 77-83 of 489 decode steps
stalling at ~154 ms, cured by SCHED_FIFO. The assignment was to replace
that poll with an IRQ/hrtimer wait. Measured first (per-predict and
per-step `/proc/thread-self/schedstat` + `stat` deltas, instrumented
runner `raw/sqr-prof2.py`, one bench rep, normal priority, installed
a9a5f60 module):

| run (`raw/steps-summary.json`) | steps > 100 ms | step wall median / mean / max ms |
| --- | ---: | --- |
| normal priority, schedutil (rep A) | 0 | 77.1 / 87.1 / 174.7 |
| normal priority, schedutil (rep B, per-step instrumented) | **75** | 76.9 / 85.5 / 162.9 |
| both clusters `performance` governor | **0** | 69.9 / 72.6 / 86.3 |
| E-cluster only `performance` | 4 | 76.8 / 74.5 / 145.5 |
| P-cluster only `performance` | 0 | 76.7 / 74.0 / 97.4 |
| installed boost module 8e331f8, schedutil, normal priority | **0** | 77.0 / 74.6 / 85.3 |

Inside a slow step (rep B, 75 of them): the sum of the 38 `predict()`
walls rises from ~65 to 98-150 ms, and **every** program in the step is
~2x its normal wall (prog 2: 2.9 -> 6.3 ms, prog 6: 5.4 -> 10.6, prog 0:
1.0 -> 2.0); the submitter's CPU time in the step is unchanged (run_time
37-60 ms vs 39 median), its run-queue delay is 0.1-1.6 ms, no major
faults. Slow steps come in bursts of consecutive positions (2-11, 14-16,
7-10, 2-12 …). That is not a wakeup-latency spike (a spike adds a
constant to one wait); it is the engine, or its memory path, running at
half speed for a while.

Cause: on T8103 apple-soc-cpufreq writes `DVFS_CMD PS2 = PS1` on every
cluster p-state change (`soc_t8103_info.has_ps2`, AsahiLinux
drivers/cpufreq/apple-soc-cpufreq.c), i.e. the memory-side performance
state follows the CPU clusters. The Qwen step is a weight-streaming,
bandwidth-bound job (~1.2 GB of Q4 weights per 65 ms); a mostly-sleeping
submitter at normal priority lets schedutil park both clusters low, and
the ANE streams at the low memory p-state. Both clusters pinned at their
top p-state -> 0 slow steps in 489 (twice). SCHED_FIFO worked for the
same reason: schedutil runs an RT task's CPU at max frequency. The
compute-bound Parakeet encoder does not move (140.3-141.1 ms schedutil
vs 139.1-139.7 ms performance governor, `raw/parakeet-perfgov.log`),
which is consistent with a memory-side, not engine-clock, effect; the
1.243x encoder gap vs macOS stays with the ANE perf-state lever
(AneClockM1).

## 2. Fix: omarchy-ane `8e331f8` — engine-busy cluster boost (ane/src/ane_boost.c)

From the first submit until `boost_idle_ms` (module parameter, default
100, 0 = off) after the last one, the driver holds a `FREQ_QOS_MIN`
request at `cpuinfo.max_freq` on every cpufreq policy (cpufreq's own
constraint object: composes with any governor, touches no DVFS
register; requests are added on boost-on and removed on boost-off, so
nothing dangles while the engine is idle). The completion poll in
`ane_tm_execute` is unchanged: it was never the cause.

Observed on the installed module during one bench rep
(`raw/minfreq-boost.log`, 1 Hz): `scaling_min_freq` policy0/policy4 =
2064000/2988000 (= max) for the whole run, back to 600000/600000 within
a second of the last submit.

Installed: `/lib/modules/7.1.13-3-2-ARCH/updates/ane.ko` =
`v0.1.0-605-g8e331f8`, srcversion `32DC3F35CA4F4A20CEA9012`, sha256
`ee582b79…`, `depmod -a` done, loaded via `modprobe ane` (prior a9a5f60
module kept at `/var/tmp/parity7/ane-a9a5f60-installed-backup.ko`).
`boost_idle_ms=100`, `map_mode=3`, `dart_contain=Y`.

## 3. Contract on the installed module, normal priority (no chrt, no governor change)

Verify: `{"prompts_match": 10, "prompts_total": 10}` `STAGED-QWEN-LINUX
PASS`, first_diff=32 on all 10 (`raw/verify-run.log`).

Bench n=100 (3 warmups + 10 reps x 10 prompts), `compare_denominator.py`
against fedd4da:

Raw `raw/staged-qwen-bench-boost-8e331f8-n100.json` (sha256 `5dbadad9…`,
`tokens_matching_reference: true`, 100/100 records match, peak RSS
9.05 GB), ratios + paired-bootstrap CIs from `raw/compare-boost-n100.txt`:

| metric (median) | Parity6 RT (`chrt -f 50`) | **this run, normal priority** | macOS | ratio | 95% CI | bar | verdict |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| TTFT s | 0.9677 | **0.9494** | 1.1891 | **0.8449x** | [0.7750, 0.9283] | <= 1.00x | **PASS** |
| decode tok/s | 8.345 | **8.245** | 5.625 | **1.4718x** | [1.4370, 1.5087] | >= 1.00x | **PASS** |
| e2e s (32 tok) | 4.6814 | **4.7315** | 6.7178 | **0.6993x** | [0.6828, 0.7156] | <= 1.00x | **PASS** |
| ttft tok/s | — | 13.61 | 12.48 | 1.09x | — | (secondary) | PASS |

The cell sweeps 3/3 with no wrapper: plain `bash /var/tmp/window.sh
bench` at normal priority on the installed module, schedutil on both
clusters. TTFT spread collapses (stdev 0.167 s vs 0.496 s at normal
priority before the fix; min 0.808 max 1.394).

The n=100 run used the module built at `8e331f8` (the same change; the
final main commit `5a22ee3` only rewords comments): same srcversion
`32DC3F35CA4F4A20CEA9012`, and `objdump -d` of both .ko files is
byte-identical (4079 lines, `cmp` clean, `TEXT_IDENTICAL`). The
installed file is the `5a22ee3` build: `v0.1.0-605-g5a22ee3`, sha256
`57ceaddd…`, reloaded via `modprobe ane` after `depmod -a`.

## 4. Parakeet golden and battery on the installed module

All on the installed `5a22ee3` module, normal priority, schedutil:

| gate | result | evidence |
| --- | --- | --- |
| Qwen ANE verify | **PASS 10/10**, first_diff=32 on every prompt | `raw/verify-main-5a22ee3.log` |
| Parakeet golden (`combined-parakeet.sh t8103-host`, 3 reps) | **PASS x3**: encoder_hidden `554a3d66…` x3 identical, transcript `db501a8c…` exact, rc=0 x3; ane_exec 140.70 / 140.26 / 140.13 ms | `raw/parakeet-main-5a22ee3.log` |
| `omarchy_ane_bundle_tests` (mlx-omarchy ce91f5b8 `tools/ci/run-ane-bundle-tests.sh`) | **34/34 cases, 5904/5904 assertions, SUCCESS** | `raw/battery-main-5a22ee3.summary.log` |

The encoder stays at ~140 ms (macOS 112.99): compute-bound, untouched by
the cluster p-state, as section 1 predicted. That 1.243x is the ANE
perf-state lever (AneClockM1), not this one.

## 5. Not done here

- prefill-512 vs macOS 11.74 tok/s: the Linux staged export is compiled
  for `max_len` 50 (`manifest.json`); a 512-token prefill needs an
  export at max_len >= 513 built on jwm1's macOS (ANEForge
  `staged_qwen_manifest.py --max-len 513`, then `io_layout.py apply`).
  M2FwStart-2 has cleared a jwm1 macOS reboot window (their macOS
  catcher twin is staged); see the lane report for status.
