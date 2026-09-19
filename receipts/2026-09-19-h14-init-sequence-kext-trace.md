# H14/T6021 init sequence traced — the block-access kill is a POWER-STATE gate, not an address; bring-up script re-grounded on the phase1-proven eight-word raise (2026-09-19)

Verdict: **MISSING INIT STEP NAMED.** The hard reset is not caused by a wrong
offset. Static analysis of the W3 driver's actual build, the phase1 device
logs, the K14 kext disasm, and the m1n1 t8103 oracle shows the ANE block is
readable on t6021 **only after all eight ANE pmgr ps words are raised with
phase1 RMW semantics** — and every block access that ran with a reduced power
state reset or hung the machine. The W3 skeleton's six-domain genpd chain and
the kernel's AUTO_ENABLE-flagged `ane_cpu` word are the deltas that matter;
`h14_bringup.py` is now hard-gated on the proven sequence. No device was
touched in this lane (static + tooling only).

## 1. Erratum first: RVBAR is 0x285050000, not 0x285105000

`0x284000000 + 0x1050000 = 0x285050000` (verified numerically). The absolute
`0x285105000` printed in the W3 receipt and the task assignment is an
arithmetic slip (it would be offset +0x1105000, which no code path computes).
The register touched was still RVBAR — proven below — and the analysis stands.

## 2. New pinned datum: the W3 fatal first-access WAS RVBAR (disasm-proven)

The W3 resume bundles seven `readl`s into one `dev_info` (C arg order is
unspecified), so "RVBAR was first" was unproven. Rebuilt
`ane/t6021/ane_t6021_drv.o` here (same source, same
aarch64-linux-gnu-gcc 12.2.0): gcc emitted the reads **left-to-right** —
island loop → `set+0` → **`eng + 0x1050000` (RVBAR)** → VERS → RTB status →
GPIO0 → CPU_CONTROL → mailbox ctrls (`objdump` of `ane_t6021_first_resume`,
first block access at `.text+0x610`). The freeze address is
**0x285050000**, with `insmod` never returning and the last flushed
netconsole line being the stage banner — a stalled load, watchdog reset
~60-69 s later.

## 3. The evidence matrix (three device sessions, one variable)

| session | power state before block access | block access | outcome |
| --- | --- | --- | --- |
| phase1 S2 (09-18, /dev/mem) | **all 8 ps words raised**, RMW `target=0xf` flags-cleared, polled ACTUAL=0xf, `ane_cpu` ends `0x3ff` (AUTO_ENABLE **cleared**) | RVBAR=`0x1`, VERS=`0xe3044`, RTB+88=`0x1`, +7c=`0x30`, GPIO0-7=`0`, EDPRCR=`0` | **clean** |
| phase1 zero-write probe (09-18) | `ane_cpu` on from iBoot only, other 7 **gated** (`0x300`) | `+0x1600044`-family read | **hang → reset** (attributed then to the box crash loop) |
| W3 v2 (09-19, kernel genpd) | six domains raised (`2e0,4000,4018-4030`); `ane_td@4008`/`ane_base@4010` **not consumers** (read `0x3ff` anyway — unexplained); `ane_cpu` = `0x1f0003ff`, AUTO_ENABLE **set** | RVBAR read | **freeze + watchdog reset** |

Rule that survives all three rows: **no block access without the full
eight-word raise; the two reduced-state accesses are the only kills.**

Two concrete deltas in W3 vs phase1, both fixed by the same change:

1. **Chain incompleteness.** The ADT/pmgr1 device table has NINE ANE devices:
   `ANE_SYS(id2 60, map6)`, `ANE_CPU(76, map6)`, `ANE_SYS_MPM(112)`,
   `ANE_TD(113)`, `ANE_BASE(114)`, `ANE_SET1-4(115-118)` (all map8,
   alias-chained SYS←CPU/SYS_MPM←TD←BASE←SET1-4). The live ps words:
   seven at `pmgr+0x4000..0x4030` + `ane_cpu@+0x2e0`. The W3 overlay
   consumed only six (`ane_cpu, sys_mpm, set1-4`) — **`ane_td` and
   `ane_base` are missing from the DT chain** even though phase1 raises
   them. (Why their words read `0x3ff` at the W3 resume is itself an open
   datum — nobody raised them in that boot.)
2. **`ane_cpu` AUTO_ENABLE.** phase1's RMW clears bit 28
   (`PS_CLEAR` includes `1<<28`); the kernel's apple-pmgr-pwrstate keeps it
   set (`0x1f0003ff`). AUTO_ENABLE permits hardware auto-gating of the fw-CPU
   island — exactly the slice RVBAR/VERS/RTB live in. phase1's proven-safe
   end state has it cleared.

## 4. What the kext actually does before its first ASC access (K14 disasm)

`AppleH11ANEInterface` 10.19.2 (symbols + capstone via the mined lane's
`disx.py`):

- **No raw pmgr writes anywhere.** `ANEHWDevice::ChangePowerState` /
  `SetRTBuddyPowerState` / `SetRTBuddyPowerPolicy` are IOService-PM
  bookkeeping (power-state list head at `this+0x148`, 32-byte records,
  `kalloc` at tail) — power flows through the platform's ADT-driven PMGR
  machinery, which enables the device's declared gates.
- **The ADT declares what Linux never enabled**: `ane0` carries
  `clock-gates: [473]`, `power-gates: [473]`, `clock-ids: [318 319 320 321]`.
  Gate 473 = pmgr device **`ANE-SYS-V`** (flag 16, no ps-map — a gate-class
  entry, not a ps word); `dart-ane0` carries gate **507 = `ANE-SYS-DART`**.
  Neither has a Linux consumer; no clock provider exists in the overlay.
  m1n1's t8103 `ANE.power_up()` calls `pmgr_adt_power_enable('/arm-io/ane')`
  — the same ADT-gate class — before any engine access.
- **Runtime attach** = `InitializeRTBuddyClient` (endpoint config tables,
  0x40c-stride records) + RTBuddy power policy, then poll RTB status
  `+0x1840088` (loop while `< 2`), endpoint doorbells via GPIO acks
  `+0x1840048..0x64`. **No `+0x1600000` read exists on the runtime path** —
  the CPU_CONTROL `0→0x10` write and SCRATCH0-7 boot args belong to the
  cold-boot (Chinook) path, taken only when RVBAR bit0 is clear. With iBoot
  having released selene (bit0=1, device-proven in phase1), the kext never
  touches that block.
- **m1n1 t8103 oracle**: `power_up()` also writes the SET-window ps words
  `ps_base+0x00..0x30 = 0xf` before any engine access. On t6021 that window
  is ADT ane0 range2 (`0x28e08c000`) — and **no Linux attempt has ever
  raised it** (W3 read `set+0 = 0x00000000`). Caution: kernel-side ps-word
  writes to this window class are what hard-reset t6001 (2026-09-16
  bisect), so this stays an explicit opt-in, never a default write.

## 5. T6021 vs T6001 ane0 (assignment comparison)

Same block-relative map (`base 0x284000000`, RVBAR `+0x1050000`,
VERS `+0x1840000`, GPIO acks `+0x48`; t6001 receipts quote identical
absolutes). Differences that matter:

- t6021's pmgr carries the **full nine-device ANE chain** (SYS_MPM, TD,
  BASE, SET1-4 beyond SYS/CPU) plus gate **ANE-SYS-V (473)** + four
  clock-ids on ane0 — t6001's Linux overlay declared only two domains
  (`ps@268`/`ps@2c8`) and no clocks, and still died at first engine MMIO.
  The failure class is therefore not t6021-specific: it is "block access
  before the platform-level power/clock/gate set is enabled", reproducibly
  fatal on T6001 (2026-09-13..16), T8103 (jwm1) and now T6021 (W2/W3) —
  while m1n1 (boot-chain, iBoot state intact) always survived.
- t6001's ADT ane0 additionally carries `pre-loaded=1`, `__TEXT;__DATA`,
  `asc-dram-mask` (fw preload metadata); selene is position-independent and
  learns its base from boot args — only relevant if fw boot from Linux is
  ever attempted, which it is not on this machine.

## 6. Tooling landed: `rtkit/h14_bringup.py` rewritten

omarchy-ane `feat/t6021-rtkit-w2` @ **93b42b4** (pushed). In order:

1. **Stage 0** — pmgr snapshot (read-only, now logs `auto_enable`).
2. **Stage 1** — the eight-word raise, phase1 RMW byte-for-byte
   (`(v & ~PS_CLEAR) | 0xF`, poll ACTUAL=0xf && BUSY(0x800)==0, parent-first,
   `ane_cpu` last), then **refuses to proceed unless the `ane_cpu` word has
   AUTO_ENABLE cleared** — the W3 death discriminator, asserted not assumed.
3. **Stage 2** — reads restricted by a 13-address whitelist to the
   phase1-proven set (RVBAR `+0x1050000`, EDPRCR `+0x1010310`, VERS
   `+0x1840000`, RTB `+0x184007c/88`, GPIO0-7 `+0x1840048..64`), each
   address **logged and fsynced BEFORE the access** so a freeze pins the
   exact address in netconsole; verdict line decodes RVBAR bit0/entry.
4. **Read-excluded zones enforced in `rd32`**: the old TM window
   `+0x1c04000..+0x1c28000` (two netconsole-named kills) and the
   `+0x1600000` cpu-control/mailbox family (kext never reads it at runtime;
   one hang association). The mailbox-sweep stage is deleted.
5. **`--set-raise`** (refused by default, requires stage 1, documented
   t6001 hazard): m1n1-analog SET-window raise `0x28e08c000+0x00..0x30 → 0xf`.

Self-checks run here (no device): `py_compile` clean; whitelist shape
(13 addrs, none in a kill zone); kill-zone predicate fires on
`0x285c2400c`/`0x285600044`/`0x285608114` and passes `0x285050000`;
RMW reproduces phase1 exactly (`0x300→0x30f`, `0x1f0003ff→0x3ff`,
`0x3ff→0x3ff`); guards refuse whitelisted-set outsiders. One real bug was
caught and fixed by this self-check before commit (an over-wide
`+0x1600000` exclusion hi-bound that would have swallowed VERS/GPIO).

## 7. Next live pass (owner's call, per lane rules)

1. `sudo python3 h14_bringup.py --stage 2` under netconsole: raises all
   eight, asserts the cpu word shape, reads the proven status set. Expected
   if the diagnosis holds: RVBAR=1, VERS=0xe3044, RTB+88 < 2, no reset.
2. Driver fix to carry (W3/W4 branch owners): overlay + driver consume
   **eight** power-domains (add `ane_td@4008`, `ane_base@4010`), and probe
   gates all block access on all-eight ACTUAL=0xf with the `ane_cpu`
   AUTO_ENABLE state checked — kernel-side, that is a DT + probe-order
   change, not a register-address change.
3. If the block still kills after the eight-word raise with AUTO_ENABLE
   cleared, the next static target is the ADT gate-473/clock-ids enable
   (the one platform step Linux never models) — not another MMIO offset.

## 8. Refs

- omarchy-ane `feat/t6021-rtkit-w2` @ 93b42b4 (script, pushed).
- `receipts/2026-09-18-t6021-engine-layout-mined/` (kext/fw/ADT artifacts,
  disx.py, dtree-j414c), `receipts/2026-09-18-h14-rtkit-port-phase1.md`
  (S0/S1/S2 evidence, probe hang), `receipts/2026-09-19-h14-w3-live-probe.md`
  (W3 death), `receipts/2026-09-19-h14-w3-probe-netconsole.log` (word-level
  readback), `receipts/2026-09-16-tm-recovery-bisect.md` (t6001 SET-write
  hazard), m1n1 `proxyclient/experiments` `m1n1_ane_experiment.py` +
  `fw/ane.py` `power_up()` (t8103 oracle).
- Open-source exemption: no screenshots; receipts + pushed branch are the
  artifacts. No device contact of any kind in this lane.
