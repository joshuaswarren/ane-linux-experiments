# TM -110 recovery bisect (2026-09-16): lethal writes named by netconsole, T8103 recovery proven twice and LANDED on main, T6001 recovery is unfixable driver-side (fails safe)

Date: 2026-09-16 (window work 06:30 → 07:35 CDT; main landing 07:38 CDT)

Hosts: jwm1-linux (T8103, `ane@26bc04000`), jw16mbp1-linux (T6001, `ane@285c04000`)
Agent: AneTmRecoveryBisect. Branches on `joshuaswarren/omarchy-ane`:
`bisect/tm110` (evidence trail, tip `3d65ca7`) and `fix/tm-recovery-final`
(deliverable, tip **`96d5a88`**, based on `b03f4b2` = held `fix/tm-recovery`).
**LANDED:** `origin/main` = **`44dd9bf869f1`** (merge of `6fa243a` +
`96d5a88`, tree identical to `96d5a88`) — disposition returned by Main
via LandHostLeaves within the hour: land for the T8103 half, T6001
fails safe.


## Outcome

- **T8103 (jwm1): no-reboot recovery PROVEN on the final build.** Window C
  on `96d5a88`: provoke -110 → recovered idle → provoke again -110
  (immediately post-recovery, cold) → recovered idle again →
  `verified output y exact` smoke twice. No reboot (boot `e52e0f1c`
  unchanged through windows A/B/C; jwm1 was handed over clean by
  AneMinus5RootCause and returned clean).
- **T6001 (jw16): driver-side no-reboot recovery CANNOT restore exact
  compute — proven across three windows, not assumed.** The final build
  fails safe: one recovery attempt, then preserve-until-reboot with
  submits refused loudly (no silent wrong data). jw16 restored to
  `6fa243a`, post-reboot smoke `verified output y exact`.
- **Lethal writes named** (below) with off-box netconsole lines; the
  per-write logging that names them is part of the landed candidate.
- The both-hosts landing bar ("provoke → recover → provoke again →
  recover → exact smoke, no reboot" on BOTH laptops) is unmeatable on
  T6001 for a hardware/firmware reason. Main landing is Main's
  disposition; everything is staged for a one-command decision.

## Lethal writes, netconsole-named

### T6001: `writel(0x300, 0x28e08c000+0x00)` — PS_SET0 power-down (locked pmgr domain)

Window 1, build `30eeee8` (327fd12 semantics + logging), 06:53:38 CDT,
receiver `/var/log/fleet-netconsole.log` (this workstation). The five
genpd partitions gate cleanly (ACTUAL nibbles fall `0xffffff` → `0x0`),
then:

```
192.168.10.244:6666 [23625.157207] ane 285c04000.ane: ANERD pd[4] force_suspend -> 0 (ps act 0x0)
192.168.10.244:6666 [23625.157228] ane 285c04000.ane: ANEWR PS_SET0 ps+0x00 down <- 0x300 (ps act 0x0)
```

No completion line ever arrived; the SoC hard-reset (boot `558000d3`
follows `96c73f34`). Reads at the same address succeed in the same log
(`ps act` is sampled from `0x28e08c000` immediately before the write) —
**reads safe, writes fatal**: the ANE SET0/BASE pmgr words are
firmware-locked. Corroboration: the live T6001 device tree exposes only
five ANE `apple,pmgr-pwrstate` nodes (`power-controller@{2c8,c010,c018,
c020,c028}` = sys_cpu + set1..4); set0/base carry no node at all.

This same write site, armed on T8103 (`0x23b70c000`) by the 95dbcf3-era
build, explains jwm1's 04:50 hard reset ("reset 1" in the t8103
receipt) — same code path, same mechanism, now named on hardware that
survived long enough to log it.

### T8103: exonerations (window A, build `30eeee8`)

The 327fd12 post-cycle re-init — 8× `TQ_NID1`/`TQ_STATUS` clears
(95d3062) and `TQ_EN |= 0x3000` (f3ad6e5), the two suspects from the
t8103 receipt — ran live on jwm1 during a bounded -110 recovery with
per-write logging: no abort, recovery reached `status 0x1`, smoke
`verified output y exact`. The t8103 "reset 2" (327fd12 + logging,
during the -5 fusion lane) is therefore attributable to its workload
context, not these writes: AneMinus5RootCause root-caused that lane to
fused kernels shipping NaN-laden island inputs (bias OOB, word*2 vs
pair*2 — their receipt `2026-09-16-ane-minus5-root-cause.md`). jwm1's
tm-recovery path now has zero unexplained lethality.

## Per-SoC sequences that work

### T8103 (jwm1) — full no-reboot recovery, PROVEN

`b52064c` semantics, exactly: genpd cycle of the five partitions →
`ane_tm_enable` → poll idle-or-fresh (1 s). Final build `96d5a88`
(`D3073678A263A448A60D528`), window C, 07:29 CDT:

```
[4517.839621] ane 26bc04000.ane: tm completion failed: -110, finish lines=0 (q4 nid=0x40)
[4517.839...] ANERD pd[0..4] force_suspend/resume -> 0 (per-write, off-box)
[4517.840202] ANERD TM_TQ_EN tm+0x0c -> 0x3000 (ps act 0xffffff)
[4517.840538] ANERD TM_STATUS tm+0x54 -> 0x1 (ps act 0xffffff)
[4517.840545] ane 26bc04000.ane: tm recovered: idle, accepting work again
[4519.893813] ane 26bc04000.ane: tm completion failed: -110, finish lines=0 (q4 nid=0x40)
[4519.894739] ane 26bc04000.ane: tm recovered: idle, accepting work again
```

→ both smokes `verified output y exact`, `wedged=0`, pin dropped,
`flock_reacquire=PASS`, boot unchanged. Window B (same build) adds a
third exact smoke. Every recovery-path MMIO write/read for both
recoveries is in `/var/log/jwm1-netconsole.log` (jw16) and in
`jwm1:/var/tmp/AneTmRecoveryBisect-jwm1/window-{A,B,C}.log`.

Note the console-captured SoC difference: T8103 retains `TQ_EN=0x3000`
through the cycle just like T6001 — but its `TM_STATUS` asserts idle
(`0x1`) anyway, and the next task is exact. T6001 retains `TM_STATUS=0x0`
forever. That is the real generation boundary, now register-proven.

### T6001 (jw16) — recovery must fail safe, PROVEN

The tm/tq file rides out every software-reachable cycle in retention:
20 ms gate (window 3) and 2 s gate (window 5) both leave `TQ_EN` reading
`0x3000` pre-OR; the wedged queue's `TQ_NID1[4]=0x4001` pending bit is
visible and clearable (window 2), but `TM_STATUS` stays `0x0` and
idleness never returns. Worse, tasks dispatched after a cycle COMPLETE
(events fire, `finished==3`) but compute nondeterministic garbage —
104/128 output bytes wrong, differing run-to-run, on fresh queues too
(predicate-relax and queue-rotation mitigation builds `b4628f4`,
`76bc89d` both measured wrong outputs). Only full system sleep or
reboot restores exactness on T6001.

Final build `96d5a88`, window FINAL, 07:30 CDT
(`/var/log/fleet-netconsole.log`):

```
192.168.10.244:6666 [2122.139869] ane 285c04000.ane: recovering: power-cycling engine partitions
192.168.10.244:6666 [2123.140990] ane 285c04000.ane: recovery: tm not idle after reset: 0x0
192.168.10.244:6666 [2123.142540] ane 285c04000.ane: recovery failed; preserving resources until reboot
```

`wedged=1`, refcnt pinned, every later submit refused in ~1 ms
(ECANCELED) — loud, never wrong data, no crash, no reboot during the
window. Cleared afterwards by one controlled reboot; jw16 back on
`6fa243a`, smoke `verified output y exact`.

## The landed candidate (`fix/tm-recovery-final` = `b03f4b2` + `96d5a88`)

Diff vs the held branch is logging + guards only — recovery semantics
are byte-for-byte `b52064c`:

1. Per-write console evidence: every recovery-path write logs before and
   after (`ANEWR reg <- val (ps act ..)` / `wrote`), every recovery-path
   read logs its value (`ANERD`), each line carrying the pmgr ACTUAL
   nibbles. A future lethal write is named by the last line netconsole
   carries. (`kernel.printk` is 8 on both hosts; receivers durable per
   receipts/2026-09-16-netconsole-both-hosts.md.)
2. SET block mapped read-only on both SoCs (t8103 `0x23b70c000`, t6001
   `0x28e08c000`); `ane_ps_verify_on` (manual poll, portable iopoll
   arity) refuses engine MMIO unless all six words read ACTUAL=on. No
   code path ever writes the SET block (locked-domain aborts, named
   above).
3. Strict idle-or-fresh completion of recovery: on T6001 it fails safe
   to preserve-until-reboot instead of serving wrong data. The
   3442d00/95dbcf3/327fd12 direct-gate mechanism is dropped for good.

Not landed (measured and rejected): `TQ_EN |= 0x3000` (f3ad6e5 —
hygiene only, unproven value), the 8-queue TQ clear (95d3062 — safe but
useless: idle never returns on T6001 regardless), predicate relaxation
(serves ghost/garbage completions), post-recovery queue rotation
(doesn't help; fresh queues compute garbage too), 20 ms/2 s gate drops
(retention survives any driver-reachable duration).

## Windows ledger (one provoke window per module build per host; markers verified before each)

| Window | Host | Build | Result |
|---|---|---|---|
| 1 | jw16 | `30eeee8` full gate | **CRASH** → named PS_SET0 down (T6001 lethal write) |
| 2 | jw16 | `e75d272` no-gate | Safe; file retained; idle never asserts |
| 3 | jw16 | `b4628f4` +relax | Recovery-safe; post-recovery outputs WRONG → relax rejected |
| — | jw16 | `b4628f4` smoke s3 | Still wrong minutes later; nondeterministic |
| 4 | jw16 | `76bc89d` +rotate | Still wrong on fresh queues → rotation rejected |
| 5 | jw16 | `3d65ca7` 2 s gate | File still retained → no driver-reachable wipe |
| FINAL | jw16 | `96d5a88` | Fail-safe proven: preserve, loud refusal, no reboot |
| A | jwm1 | `30eeee8` | TQ clears + 0x3000 exonerated on T8103; status 0x1; smoke exact |
| B | jwm1 | `96d5a88` | Wedge → recovered idle → smoke exact; second smoke exact |
| C | jwm1 | `96d5a88` | **Wedge → recover → wedge again → recover → 2× exact smoke, no reboot** |

Markers `ATRB-JW16 NETCONSOLE MARKER{,2..6}` and `ATRB-JWM1 NETCONSOLE
MARKER` were each verified in the off-box receiver log before the
corresponding window. Two T6001 reboots total (crash fallout 06:54;
controlled wedge-pin clear 07:31), both documented above; jwm1 zero.

## Branch / main state

- `origin/main` = **`44dd9bf869f1`** — LANDED 07:38 CDT by
  LandHostLeaves on Main's disposition (merge `6fa243a` + `96d5a88`;
  `git diff 96d5a88 origin/main` is empty). The T8103 no-reboot
  recovery and the T6001 fail-safe are on main as of this SHA.
- `origin/fix/tm-recovery-final` = `96d5a88` (deliverable, based on held
  `fix/tm-recovery` `b03f4b2`).
- `origin/bisect/tm110` = `3d65ca7` (evidence trail; includes the
  rejected mitigation builds with their commit-message measurements).

## Service / loader retargets

- **jwm1-ane.service: retargeted.** The service insmods
  `~/src/omarchy-ane-lifecycle-rebase/ane/ane.ko`; that checkout is now
  at `96d5a88` (local branch `fix/tm-recovery-final`), rebuilt clean
  (0 errors/warnings, apple SDK 7.1.6). The loaded module is
  `96d5a88` / `D3073678A263A448A60D528`, refcnt 0, wedged 0. Next boot
  loads the final build.
- **jw16: no loader exists** (no systemd unit, no modules-load entry, no
  local script references ane.ko — module management is manual by
  lanes). jw16 is restored to `6fa243a` loaded, refcnt 0, smoke
  `verified output y exact` at 07:32 CDT. Nothing to retarget; if Main
  lands the final branch, jw16's behavior is unchanged by it.

## Evidence files

- This workstation: `/var/log/fleet-netconsole.log` (jw16 console: the
  lethal-write excerpt above, window 2/3/4/FINAL recoveries, preserve
  lines).
- jw16: `/var/log/jwm1-netconsole.log` (jwm1 console: windows A/B/C
  per-write recovery trails), `/var/tmp/AneTmRecoveryBisect-jw16/`
  (window logs `window-p1..p5.log`, `window-FINAL.log`, module builds,
  saved outputs incl. the wrong-output md5 set).
- jwm1: `/var/tmp/AneTmRecoveryBisect-jwm1/` (`window-A/B/C.log`,
  scripts), `~/ane-bisect-keep/ane-{a,final}.ko` (synced pre-window
  against dirty-reset loss).
- Wrong-output md5s (T6001, window 3): s1 `8fbffb4e…`, s2 `c9c1467c…`,
  s3 `59762ee8…` vs fixture `1d88236b…`; 104/128 bytes differ from the
  first byte (wholesale, not tail).

## Disposition (resolved)

- LANDED: `origin/main` = `44dd9bf869f1` contains `96d5a88` (merge with
  `6fa243a`), per Main's disposition returned via LandHostLeaves at
  07:38 CDT — T8103 no-reboot recovery on main; T6001 fails safe, never
  wrong data. jwm1 runs main's build; jw16 remains on `6fa243a`
  (behavior-identical to main on T6001) until its next natural update.
- T6001 exact-restore paths that would need new scope: full system
  suspend trigger from Linux (heavy, untested here) or a firmware/SMC
  reset handshake (no documented endpoint found in this lane).
