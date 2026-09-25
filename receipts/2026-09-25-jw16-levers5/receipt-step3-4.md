# jw16 steps 3+4 — ANE perf-state lever (blocked, evidence) + pipeline encoder path moved to the whole-program ANE submit (2026-09-25)

Owner: Jw16Levers5. Host: jw16 (M1 Max, T6001, 7.1.6-1-1-ARCH), Omarchy side.

## Step 3 — ANE perf state on Linux T6001: BLOCKED upstream of any probe

The step needed macOS's exact ANE perf-state write (PA + value) or the
ane-acg-hack path to replicate behind a default-off omarchy-ane param. Neither
input exists, each with named evidence:

1. **dtrace capture: blocked by SIP.** jw16 macOS has SIP enabled
   (`csrutil status`: "System Integrity Protection status: enabled"); dtrace
   refuses fbt (`failed to match fbt:com.apple.driver.ApplePMGR:*PerfState*:entry:
   System Integrity Protection is on`; probe listing empty —
   `artifacts/step3/perfstate-probelist.txt`). AneClockM1's name-based
   ane-perfstate.d (sha e1edfffb…) remains unexecuted until fbt is available.
   Main's call (2026-09-25): hold SIP — disabling needs hands-on recoveryOS;
   static route first.
2. **acg-hack path: T8103-only (closed).** From the disassembly of
   AppleT6000PMGR in the jw16 22G74 kernelcache (PVE
   `/var/tmp/jw16-kc/t6001-pmgr.asm`, macstudio `/tmp/t6001-pmgr.asm`;
   writeReg32 @ 0xfffffe0009b54ee8, setPerfState @ 0xfffffe0009b52f1c),
   AneClockM1's verified verdict: writeReg32 has NO ANE branch — the
   map==2/reg==0xc00/die==0 special case is `workaroundPSRegsForceWakeUP`;
   general path is a plain BIT(29) RMW; no 0x470 compare, no
   0x1868a04/0x26b868a04 constants; the T6001 ADT carries no ane-acg-hack
   property. Folded into omarchy-ane main 7628b05 (ACG lever marked
   T8103-only; per-chip setPerfState domain sets recorded: T6021 2/5/13,
   T8103 8/14, T6001 1-5/13).
3. **No probe was built.** Per the standing rule (no candidate PA, no host
   MMIO write without a captured address+value), no omarchy-ane param code
   was installed. The template for the future param is
   omarchy-ane main `ane/src/ane_boost.c` (module_param + submit-path hook);
   remaining routes to the input: a one-time recoveryOS SIP window (Main
   holds), or a deeper static trace of the T6001 CLPC/domain-13 perf path
   (AneClockM1's lane).

## Step 4 — pipeline encoder moved to the whole-program ANE submit

Starting state: the installed pipeline (`/var/tmp/parakeet-recover/
run-contract.sh`, fused_e2e) ran the encoder as the island hybrid
(`vulkan_encoder_inproc.py`: ANE attention islands A/B/C submit-dense +
GPU epilogue) — encoder_ane ~1438-1452 ms, everything transcript-bit-exact.

**Result: the default encoder path is now the whole-program ANE submit**
(`ane_whole_worker.py`: one-shot `mlx-omarchy-ane-worker --bundle
/var/tmp/encoder-whole/bundle` per encoder call, single 13701-TD program,
libane carried by the worker). Same-session A/B and cutover verify:

| stage (median, ms) | island hybrid (control) | whole-program (new default) |
|---|---:|---:|
| mel_frontend | 140.8 | 137.6-139.0 |
| encoder_ane | **1451.6** | **1273.7-1275.5** |
| tdt_decode | 361.7 | 333.4-368.4 |
| total | **2047.6** | **1825.4-1851.7** |

- Pure encoder exec: **440 ms** single submit (certified slope,
  (n32-n1)/31) vs the hybrid's ~1452 ms of submit-dense island work
  (-69.7%). The harness stage additionally carries one worker program load
  (~458 MB anec + buffers, ~1.07 s wall incl. exec per one-shot call) — a
  resident `--serve` session is the noted upgrade if a future pipeline ever
  issues repeated encoder calls per pass.
- **Correctness:** transcript gates green on every run of every leg
  (status match, matching_prefix 104, transcript db501a8c); the whole
  path's hidden is bit-exact vs the CoreML gold fp16
  (`fca96f1355485ec3`, reproduced post-reboot and post-module-reload) and
  its harness npy pin is the deterministic upcast `554a3d66f6885a35…`
  (x3 runs). The hybrid's npy pin (38c73261…) reflects the island path's
  fp32-boundary rounding; the hidden pin is therefore runner-specific and
  run-contract.sh now selects it by runner.
- **Incidents, disclosed:** (a) the raw-libane ctypes route
  (`ane_whole_encoder.py`) fails on jw16 (`ane_exec rc=-1` through
  libane-strict.so) and its failure wedged the TM exactly like the
  Levers3 kill-race signature (`ane_exec failed for program 0`); fixed by
  `rmmod ane && modprobe ane` (no reboot), after which the worker route
  ran green; (b) an intermediate cutover script put the runner-specific
  pin inside the quoted heredoc (python SyntaxError) and missed the `os`
  import — both repaired and the final verify is the all_green run above.

## Installed state after steps 1-4

- mesa flush17f+depskip ICD, smoke bit-exact (step 1 receipt).
- `run-contract.sh` default = whole-program encoder; `run-contract-island.sh`
  preserves the certified hybrid; `run-contract-whole.sh` (ctypes variant)
  deleted as superseded.
- llm-inference active with real completion after every window (last:
  health 200, finish=length at 18:26:16 CDT).

## Artifacts

`artifacts/step3/`: `perfstate-probelist.txt`, `t6001-pmgr.asm` (also
macstudio /tmp/t6001-pmgr.asm). `artifacts/step4/`: `ane_whole_worker.py`,
`whole-run.log`, `island-run.log`, `cutover-verify.log`,
`summary-whole.json`, `summary-island.json`, `summary-cutover.json`.
Raw on jw16: `/var/tmp/parakeet-recover/battery-20260925T181947` (whole),
`battery-20260925T182301` (island control), `battery-20260925T182605`
(cutover verify).
