# M2 (T6021) firmware start — recoveryOS fall root cause, kernel path blocked (2026-09-23)

Lane: M2FwStart-2. Hardware: jw14m2 (T6021, J414c). Linux restored to stock and
verified. No custom image booted this lane.

## 1. Linux back on stock

- ESP `m1n1/boot.bin` restored from `e93323fb` (dry) to stock `a3f533b9` via
  `/tmp/restore-stock.sh` (before/after shasum, ESP unmounted). Re-verified on
  the booted Linux: `sha256sum /boot/efi/m1n1/boot.bin` =
  `a3f533b9…bc2683b2`.
- Default boot had flipped to macOS (`bless --getBoot` = `/dev/disk4s1`,
  `boot-volume` = disk0s2 group `2A5A7F8E`). Re-blessed `/Volumes/Omarchy`
  (`sudo bless --mount /Volumes/Omarchy --setBoot`, rc 0, no password);
  `boot-volume` now disk0s3 `13FFC613` : group `5AE8D78F`, `--getBoot` =
  `/dev/disk2s2`.
- Reboot 09:49 CDT (`sudo shutdown -r now`, ESP unmounted). `jw14m2-linux` up
  at 09:49:58, kernel 7.1.13-3-1-ARCH, stock sha confirmed.

## 2. Root cause of the recoveryOS fall

The dry image is not structurally broken, and the boot policy was not touched.
The fall is the dry stage-2 hook hanging on an unpowered ANE window.

**Image diff (byte-verified).** `boot.bin.dry-new` (e93323fb, 0x5f1254) vs
`boot.bin.stock-linux` (a3f533b9, 0x5ed254), both saved on the box at
`/var/tmp/m2stub-backup/`:

- delta = 0x4000. First byte divergence at 0x80c.
- stock m1n1 part = `stock[:0x110000]` sha `9ad08653`; dry m1n1 part =
  `dry[:0x114000]` sha `c143e49b`.
- payload tails are byte-identical: `stock[0x110000:]` == `dry[0x114000:]`,
  both 0x4dd254 bytes, sha `b73cd565`. Header identical through 0x80c.

So iBoot verifies stage 1 (the stub fuOS image, unchanged — `bputil -e` shows
the Omarchy stub policy intact: Permissive, `coih` and `nsih` present) and
stage 1 loads stage 2 fine. The stub (disk0s3) and the local policy were not
modified. The fall is not a stage-1 or boot-policy failure.

**Not a macOS restart path.** The dry boot (reboot #2, 09:05:30) was a
Linux-initiated `systemctl reboot`. Stock Linux reboots reach Linux every
time: reboot #1 (09:02, from macOS), reboot #3 (09:49, from macOS), and the
10:02 watchdog recovery. Only the dry image falls to recovery.

**The hook hangs.** The dry stage 2 runs `ane_bringup_run()`
(`/tmp/m1n1-b9/src/ane_bringup.c`). In dry mode it calls
`pmgr_adt_power_enable("/arm-io/ane")` then `ane_dump_scratch("pre")`.
`pmgr_adt_power_enable` walks the ADT `clock-gates` property
(`pmgr.c:210`), which for ane is the virtual gate 473 (ANE-SYS-V, flag
0x10, no ps word — research receipt §7.4). It raises no power island. Then
`ane_dump_scratch` reads the engine window (`ASC_SCRATCH`, `CPU_CONTROL`,
`CPU_STATUS`, `RVBAR`). iBoot skips ANE init on Asahi boots (fw-debug receipt
§4a), so that window is unpowered at m1n1 stage-2 time, and a read of an
unpowered ANE window hangs the fabric (the hook's own comment, line 484, and
the power-dart-fwload hard rule). The hook arms the 30 s WDT *before* the
read (line 494), so the hang trips the WDT and resets the box. iBoot then
routes the watchdog-reset boot to recoveryOS — the same mechanism the jw16
spin-test receipt established.

**Video.** `/tmp/m2proxy/m2dry-CAM.mp4` (299 s, jwm1 webcam): screen drops at
t+4 s (reboot), the Omarchy splash holds, and the Boot Recovery Assistant
dialog appears at t+92 s and stays to the end. 92 s = boot-to-hook plus the
30 s WDT plus iBoot's recovery boot. The stock boot video
(`/tmp/m2stock-CAM.mkv`) reaches the bright desktop instead.

## 3. Kernel-driver start: blocked

The firmware never runs because the RVBAR latch reads `0x10000000001` —
missing the kext mode bits 55/48 (research receipt §7.13). The latch is
sticky; clearing it needs the ane_cpu island powered off. Both power-off
mechanisms hang a running Linux:

- ps-off write (TARGET 0xf→0): fatal, s24 (2026-09-21), watchdog +62 s.
- reset pulse (bit 31): hung today. It worked once (s14, 2026-09-21, ACTUAL
  dropped to 0) when `AUTO_ENABLE` (bit 28) was clear, so I cleared bit 28
  first (survived, read back `0x0f0003ff`, ACTUAL stayed 0xf) and pulsed
  again. It hung anyway. The s14 result does not reproduce; the pulse is
  unsafe from Linux regardless of bit 28. Not retried (same crash twice).

Both hangs recovered by themselves: the watchdog rebooted to stock Linux
(10:02, sha `a3f533b9` re-confirmed). No data loss, no boot-chain change.

The chainload alternative is also closed: stock stage 1 has no `chainload=`
variable, and setting one rewrites the default boot object (jw16 receipt §3).

## 4. Next blocker

No firmware-start path exists that avoids a new boot image. The remaining
path is a fixed m1n1 image whose hook raises the eight ANE power islands
(direct pmgr ps writes, not the virtual-gate walk) *before* any engine-window
read, with the WDT armed before the first engine access. Boot the dry image
first to prove it reaches Linux, then the write image for the real start
(quiesce power-cycle, stage, DART, RVBAR with mode bits, RUN). Each attempt
keeps the byte-verified restore: stock `a3f533b9` at
`~/m2stub-backup-20260923-0901/` (macOS) and `/var/tmp/m2stub-backup/`
(Linux), `restore-stock.sh` tested this lane. This boot can drop to recovery
and needs Joshua at the console, so it waits for Main's go-ahead.

## 5. Device state (closeout)

- jw14m2 on stock Linux, `boot.bin` = `a3f533b9`, default boot = Omarchy
  (`/dev/disk2s2`). Healthy after two watchdog recoveries.
- ane_cpu ps word left at `0x0f0003ff` (bit 28 cleared by the test) until the
  second hang; the watchdog reboot restored hardware defaults. No module
  loaded, no boot-chain write.
- Read-only snapshot (islands up, ACTUAL 0xf all eight): `CPU_STATUS 0x2a`,
  `CPU_CONTROL 0`, `RVBAR 0x10000000001`, `VERS 0xe3044`, `RTB_STATUS 1`,
  scratch all zero.
