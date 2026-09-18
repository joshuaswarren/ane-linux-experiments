# T6021 overlay authored + installed; forced bind external-aborts the box — CAPTURED-STOP (2026-09-18)

Verdict: **CAPTURED-STOP per runbook discipline.** Gates pass to and including
the refusal gate on both boots; the `allow_unqualified=1` forced-bind leg
caused a **full machine reset** (external abort class) on its first and only
attempt. No retry. No SET-block write by the runbook driver beyond the bind
itself; no promotion; tier stays RECOGNIZED in driver `3b0d115`. The
community bring-up path this run established: **merged DTB via
`update-m1n1`** (GRUB has no `devicetree` line; m1n1 boot.bin embeds the DT).

## 1. What was mined (the missing data, found without m1n1)

| Datum | Value | Source |
| --- | --- | --- |
| Engine reg | `0x285c04000 + 0x24000` | m1n1 `fw/ane.py` constant (ane0 range0 `+0x1c04000`), proven delta on t8103 dtsi (`ane@26a000000`→`0x26bc04000`) and t6001 live (jw16 overlay); t6021 ane0 range0 raw `0x84000000/0x2000000` (macOS 26.6.2+27.0 captures) + translation `+0x200000000` proven by pmgr low-32 match (`0x8e080000` ↔ stock DTB `0x28e080000`) |
| DARTs | `0x285800000/810000/820000`, 16 KiB each, **sid 0** | macOS dart-ane0 quartet (identical to t6001 ADT); 4th window `0x285804000` unused on t6001 overlay precedent |
| IRQs | ane AIC `0x374` (884), dart `0x375` (885), AIC2 4-cell level-high | macOS IOInterruptSpecifiers + jw16 flags=4 pattern |
| pwrstate chain | **pmgr+0x4000**: `ane_cpu@2e0`, `ane_td@4008`(0xb5), `ane_base@4010`(0xb6), `ane_set1..4@4018-4030`(0xb7-b9+new) | **STOCK t6021-j414c.dtb already carries the full ANE genpd chain** — resolves the "unverified pwrstate layout" risk named in the driver receipt (t6001 carries its SET block at +0xc000; t602x exposes the ane chain at +0x4000 in the ADT-derived DTB) |
| SET window | `0x28e08c000` (driver-side, unchanged) | m1n1 `fw/ane.py` `ps_map["ane0"]` = `0x028e08c000`, hardcoded by-name across all chips — direct confirmation of descriptor 3b0d115 |
| macOS captures | engine sub-window **absent** from ane0 children (reg = MMIO block + pmgr `0x4034` + `0xc000/0x4000` windows only) | mined `decoded-nodes.json` — this gap is why Linux-side/ADT derivation was required |

Field list posted to Contrib422 for the capture-script schema bump (ride-along).

## 2. Overlay + install (the documented bring-up path)

- `omarchy-ane` `feat/t6021-soc-entry` **3d34cfb** + fix **b877b87** (pushed).
- Overlay source: `ane/t6021-j414c-ane.dts` (fragment shape per jw16
  `t6001-j316c-set-domains.dts`, with phandles 0x1f0/0x1f1 added to
  `ane_cpu@2e0` / `ane_set4@4030`).
- **Kernel trap found:** `apple_dart_of_match` has **no `apple,t6020-dart`
  row** — stock t602x darts bind via their second compatible
  `apple,t8110-dart`. Single-compatible overlay darts never probe, silently.
  Fix b877b87: dual compatible. (First boot: darts unbound, ane deferred —
  refusal gate still passed.)
- Install: overlay merged **at DTS source level** (stock DTB has no
  `__symbols__`; fdtoverlay renumbers overlay phandles without remapping raw
  refs — fdtoverlay path is a trap), compiled with dtc, merged DTB sha256
  `5f822986…` (first) → installed to `/usr/lib/modules/7.1.13-{1,3}-1-ARCH/dtbs/t6021-j414c.dtb`,
  then `sudo update-m1n1` rebuilds `/boot/efi/m1n1/boot.bin`
  (m1n1 + newest-kernel dtbs glob + u-boot.gz).
- Post-reboot verification (both boots): live tree has
  `soc/ane@284000000` (`apple,t6021-ane`) + three ANE DARTs; second boot
  `apple-dart 2858{0,1,2}00000.iommu: DART [pagesize 4000, 16 streams …]
  initialized`, ane in iommu group 6, fdt sha `d6a7b3a8…`.

## 3. Runbook execution

Boot `-3` kernel (`7.1.13-3-1-ARCH`), .ko rebuilt on-box vs prebuilt `-3`
artifact (sha `8441546f…` stage-checked earlier):

- Gate (a) **PASS** (both boots): plain insmod →
  `apple,t6021-ane: recognized but unqualified` refusal, no `/dev/accel`,
  clean rmmod. `GATE-OK: refusal path holds`.
- Forced-bind leg (`insmod ane/ane.ko allow_unqualified=1`): **machine
  reset ~90 s into the runbook**, between the refusal gate OK and any
  further output. `/dev/accel` never appeared. Probe lines visible before
  the reset on boot 2 (no bind attempted); on boot 3 the bind leg itself
  reset the box. **STOP — no retry** (runbook + lane instruction).
- Crash site candidates (cannot be distinguished without persistent
  console): (1) genpd attach driving pmgr+0x4000 ane pwrstate writes,
  (2) driver SET-window probe at `0x28e08c000` (m1n1 ps_map value — but
  t602x exposes its ane chain at +0x4000, so the c000 window's live
  identity on t6021 is now the open question), (3) first engine MMIO
  access at `0x285c04000`.

## 4. Exact missing datum (blocker for the next attempt)

**A persistent console for jw14m2-linux (netconsole or ramoops).**
The box has no `ramoops` reserved-memory node and no netconsole target, so
the abort named neither ESR/FAR nor the faulting module. T6001's abort was
only diagnosable because netconsole named it (2026-09-16). Next attempt
REQUIRES: netconsole pointed at a fleet log sink (module params
`netconsole=…` pre-loaded before insmod) or an added `ramoops` reserve +
`pstore.console_size` reboot, THEN one `allow_unqualified=1` bind. Until the
abort is named, the safe-order candidate list is §3's (1)-(3); do not
"fix" by guessing another offset.

## 5. State / revert

- Overlay LEFT INSTALLED (boots 2 and 3 healthy; the DT is inert without
  the module). Revert: `sudo cp /var/tmp/t6021-j414c.dtb.orig-{1,3}` back
  into the two dtbs dirs, `sudo cp /var/tmp/boot.bin.orig /boot/efi/m1n1/boot.bin`,
  reboot.
- Runbook staging survives at `/var/tmp/t6021-qual` (checkout 3b0d115 +
  smoke stack, byte-identical ports); `-3` .ko at `/var/tmp/omarchy-ane-k3/ane/ane.ko`.
- jwm1, jw16 untouched; no SET-block write by any agent; the only writes in
  flight at reset were the driver's own first probe (unobserved).
- No screenshot evidence per open-source exemption (kernel bring-up; dmesg
  + this receipt are the artifacts).

## 6. Refs

- Overlay commits: omarchy-ane `feat/t6021-soc-entry` 3d34cfb, b877b87.
- Inputs: 2026-09-18-t6021-qualification.md, 2026-09-18-t6021-driver-entry-prepared.md
  (runbook §3 executed verbatim), 2026-09-13-t6001-tm-offset.md,
  2026-09-13-t6000-live-mapping.md, 2026-09-18-jw14m2-macos26-capture.md (+27).
- Post-abort boot state captured in repo: `receipts/2026-09-18-t6021-overlay-abort/jw14m2-postabort-state.txt`.

---

# Session 2 — console armed, kill named at register level, sys_mpm fix falsified — STOP (2026-09-18, later)

Verdict: **CAPTURED-STOP, per the same discipline.** The persistent console was
armed and verified, the bind was repeated under instrumentation, and the
killing access is now named exactly: **the first engine MMIO read,
`TM_TQ_EN` at `0x285c04000 + 0x20000 + 0xc = 0x285c2400c`, external-aborts
the machine** — after a genpd raise that completes without error and after a
SET-window probe that reads safely. The one capture-derivable refinement
(consume `ane_sys_mpm@4000`) was applied and **falsified**: the kill is
unchanged. No promotion; tier stays RECOGNIZED. The next datum has no capture
source (§2.3) — any new constant would be a guess, so the lane stops here.

## 1. Instruments armed (survive on the box; revert notes at §4)

- **netconsole**: `/etc/modprobe.d/netconsole.conf`
  `options netconsole netconsole=6668@192.168.3.103/wlan0,6666@192.168.10.235/04:f4:1c:92:4c:c8`
  (remote MAC = the 192.168.2.1 gateway — the target is one routed hop
  off-link, and an explicit gateway MAC makes netpoll deliver; round-trip
  proven both directions, including the refusal-path insmod line).
  `/etc/systemd/system/jw14m2-netconsole.service` (After=network-online,
  oneshot modprobe) + `/etc/sysctl.d/90-netconsole-loglevel.conf`
  `kernel.printk = 8 4 1 7`. Receiver = the standing fleet receiver on the
  dev box (`fleet-netconsole-receiver.service`, port 6666, log
  `/var/log/fleet-netconsole.log`, sender tag `192.168.3.103:6668`).
- **ramoops**: the asahi kernel has `CONFIG_PSTORE_RAM=m` but **no
  `CONFIG_PSTORE_CONSOLE`**, so the DT node arms dmesg records only
  (`record-size` must be a single u32 cell — an 8-byte cell pair fails to
  parse and the probe dies with -22). Reservation `0x10010000000 + 0x400000`
  (DRAM base `0x10000000000` + 256 MiB; clear of the low asc-firmware
  carves, which end at base+0x26b4000, and of the top m1n1/u-boot region).
  Live proof: `ramoops: using 0x400000@0x10010000000, ecc: 0` + 16
  dmesg-records. pstore stayed EMPTY after both kills — the reset strikes
  below the kernel (no die()/panic() ever runs), so netconsole is the only
  instrument that captured anything.
- **driver instrumentation** (omarchy-ane `feat/t6021-soc-entry` **22c5314**):
  first resume now names every stage before it runs — genpd raise complete →
  per-word named SET-window probe (`ane_ps_act_probe`) → first engine access
  (with the engine resource printed) → TM_STATUS — and runs `ane_tm_enable`
  in `rec=true` mode on first enable. Built on-box at
  `/var/tmp/t6021-bisect` vs the running 7.1.13-3 kernel.

## 2. What the three bind attempts under console proved

### 2.1 Bind A (pre-instrumentation, console-verified gate leg first)

Last off-box line = the `UNQUALIFIED bind forced` banner, then silence, then
a fresh boot. No ESR/FAR, no panic text: reset below the kernel. This
cleared the ground for the instrumented retry.

### 2.2 Bind B (instrumented, five-domain overlay)

```
ANE-resume: genpd raise complete; SET window probe next
ps probe: SET window at 0x000000028e08c000, 6 words
ps probe: word 0 -> 0x0          words 1..5 -> 0x80000000 each
ANE-resume: SET window probed; first engine access next
  (TM_TQ_EN tm+0x0c @ engine [mem 0x285c04000-0x285c27fff] + 0x2000c)
<silence — machine reset>
```

Three candidates, two dead on the spot:

1. **genpd pmgr writes — dead.** The raise callback chain completed (the
   resume entry line printed; apple-pmgr-pwrstate polls ACTUAL and would
   have errored otherwise).
2. **SET-window read at 0x28e08c000 — dead as a kill.** All six words read
   safely. The window decodes (the ADT gives ane0 exactly this range,
   11/11-validated on 26.6.2 + 27.0), but the values (word0 0x0, words 1-5
   0x80000000, ACTUAL nibbles all zero) do not look like live SET words —
   the live SET-block location on t6021 is therefore ALSO unverified.
3. **First engine MMIO — THE KILL.** `readl(0x285c2400c)` hard-reset the
   machine.

### 2.3 Bind C (sys_mpm fix, omarchy-ane d2e1d14) — falsified

Rationale: `ane_sys_mpm@4000` is a *sibling* of `ane_td` under
`ane_sys@260`, so the stock parent cascade (set4→…→set1→ane_base@4010→
ane_td@4008→ane_sys) can never raise it; ane0's ADT pmgr window
(`0x8e080000..+0x4034`) frames exactly the six-island chain
4000/4008/4010/4018-4030, so the bound device should consume it. Applied
(phandle 0x1f5 assigned in the merged DT; live tree verified: six
power-domains on the ane node). Result: **identical kill line** —
genpd raise complete (now six domains), same SET-window values, same engine
read, same silence. The missing-consumer hypothesis is dead.

## 3. Exact missing datum (blocker for the next attempt)

**The t6021 ANE engine-internal layout inside ADT range0
(`0x84000000/0x2000000` → translated `0x284000000/0x2000000`): which
sub-offset is the TM/TQ block the driver must talk to (t8103/t600x say
`+0x1c04000` with TM at `+0x20000`), and where the live SET block really
sits (t600x: pmgr+0xc000; t6021's +0xc000 reads non-pwrstate values).**
Neither is derivable from any capture in hand: macOS shows no engine
sub-window for ane0 (the documented mined gap), m1n1's `fw/ane.py` constants
never executed on t6021, and the ADT bounds only range0. Sources that would
name it: a m1n1 boot on jw14m2 walking ANE.ps_map/engine probes
(fallback listed in the driver receipt §2), or a macOS-side ANE runtime
capture that surfaces the engine window. Do NOT re-derive by guessing
another offset — two kill sites are now named and the base rule is
three-chip-proven; only a real t6021 source moves this lane.

## 4. State / revert (delta over session 1)

- Overlay DTB now = session-1 merge + ramoops node + sys_mpm phandle 0x1f5
  + six-domain ane power-domains (dtb sha `d0021300…`, boots healthy across
  4 reboots). New backups on the box:
  `/var/tmp/t6021-j414c.dtb.pre-ramoops-20260918` (session-1 DTB),
  `/var/tmp/boot.bin.orig` (stock boot.bin, unchanged).
- Instrumented driver: repo commits 22c5314 (naming) + d2e1d14 (overlay
  sys_mpm); on-box source + .ko at `/var/tmp/t6021-bisect`. Module NOT
  loaded; plain-insmod refusal gate green with this .ko on the final boot.
- netconsole/ramoops arms automatically every boot; receiver on the dev box
  is standing infrastructure (`fleet-netconsole-receiver.service`).
- jwm1, jw16 untouched; no SET-block write by any agent at any point; no
  promotion; tier RECOGNIZED.
- Open-source exemption: no screenshots; dmesg/netconsole log + this
  receipt are the artifacts. Full console stream: receiver log lines
  14019-14022 (bind A), 14788-15207 (bind B, kill named), 15589+ (bind C).
