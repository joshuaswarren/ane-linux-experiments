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
