# M2 (T6021) firmware start — recoveryOS fall root cause, kernel path blocked (2026-09-23)

Lane: M2FwStart-2. Hardware: m2-host (T6021, J414c). Linux restored to stock and
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
- Reboot 09:49 CDT (`sudo shutdown -r now`, ESP unmounted). `m2-host` up
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

- m2-host on stock Linux, `boot.bin` = `a3f533b9`, default boot = Omarchy
  (`/dev/disk2s2`). Healthy after two watchdog recoveries.
- ane_cpu ps word left at `0x0f0003ff` (bit 28 cleared by the test) until the
  second hang; the watchdog reboot restored hardware defaults. No module
  loaded, no boot-chain write.
- Read-only snapshot (islands up, ACTUAL 0xf all eight): `CPU_STATUS 0x2a`,
  `CPU_CONTROL 0`, `RVBAR 0x10000000001`, `VERS 0xe3044`, `RTB_STATUS 1`,
  scratch all zero.

## 6. Fixed images built, not booted

Built off-device in the macstudio ALARM chroot (`dg-alarm-py314:sep23`,
`/alarmroot`, rustc 1.93.1, gcc 16.1.1, `make ARCH= RELEASE=1 BUILDSTD=1`).
Hook source: `ane_bringup.c` in this directory. WDT is armed before any
island write. Nine islands (the eight plus parent `ane_sys`) are raised
with `pmgr_set_mode(TARGET=0xf)` and each ACTUAL is checked before any
engine read. No RESET bit. No engine read while an island is off.

- dry m1n1 `ce11e652…` 1,130,496 B, contains `mode=dry` / `islands up`,
  no `mode=write`. Assembled `boot.bin.dry-islands` sha `a2e3b68c…`.
- write m1n1 `da6f039a…` 2,834,432 B, contains `mode=write` /
  `cycle ane_cpu off`, no `mode=dry`. Assembled `boot.bin.write-islands`
  sha `df31b635…`.
- Both payload tails equal the stock tail (sha `b73cd565`, 110 dtbs, gzip
  u-boot). ESP still `a3f533b9`, matches the Linux backup. Not installed.
- Pre-boot read-only recheck on Linux: all nine ps words ACTUAL=0xf at the
  addresses the hook uses. `RVBAR` still `0x10000000001`.

## 7. Linux-side start, after the boot was held

No `/dev/mem`. Modules built in the ALARM chroot against the M2's
7.1.13 headers and loaded with `insmod`.

- RVBAR write of `0x0000010000004001` read back `0x0000010000000001`.
  The address bit does not stick while the island is up. Restored.
- TARGET=0 on ane_cpu, pmgr word only: ACTUAL went to 0 (`ps=0f000300`)
  and back to 0xf. Box stayed up. RVBAR after was still
  `0x0000010000000001`, bit0 set. A power cycle does not clear the lock.
- RESET bit, no engine read until ACTUAL was back and RESET was clear:
  ACTUAL never left 0xf, RVBAR unchanged, box stayed up.
- Live DT `ane-alias-iova` is IOVA `0x10000000000` size 16MB, not a
  physical region. Physical `0x10000000000` is a hole (iomem jumps from
  `0x1303057fff` to reserved `0x10000230000`). T6001 ADT segment-ranges
  use IOVAs 0 and `0xf4000`, not `1<<40`.
- Existing rtclient (vermagic match) with `fw_load=1 fw_start=1
  fw_load_stamp_base=0x10000000000`: alias `0x10000000000` <- 320 pages,
  roundtrip OK, stamp sha `00220713`, RUN issued, no SCRATCH7 READY,
  no dart fault, CPU_STATUS `0x28`, driver HELD. All three dart-ane
  instances share TTBR `0x10005f69` and translate that IOVA to
  `0x100a1a08000`, whose first word is the reset branch `0x14000081`.

Hard blocker: the latched entry is fully mapped on every ANE DART and
holds the real reset vector, RUN does not start the firmware, and no
safe pmgr operation clears the RVBAR lock so the mode bits can be
written. The built boot image would hit the same lock. Not booted.
ESP still stock. Driver left HELD; a stock reboot reclaims it.

## 8. macOS capture and the Linux read-back

macOS 27.0, build 26A428, AppleH11ANEInterface 10.19.2 loaded.
H11ANEIn registered, active, FirmwareLoaded=Yes. No /dev/mem, so
RVBAR, CPU_STATUS, EDDEVARCH, and TCR were not readable there.
Dumps: ane0-dt.txt, dart-ane0-dt.txt, h11ane.txt.

ane0 segment-ranges (32-byte records):
- TEXT phys 0x1000092c000, iova 0, remap 0x10000000000, size 0xe8000
- DATA phys 0x1000150c000, iova 0xe8000, remap 0x100000e8000, size 0x284000
pre-loaded=1. No asc-dram-mask, no region-base.
dart-ane0 vm-base=0x10000000000, sid=`00 00 00 00 0f 00 00 00`,
bypass-15 present.

Back on stock Linux (boot.bin a3f533b9, default Omarchy):
- All nine islands ACTUAL=0xf.
- SID 15 TCR=0 TTBR=0 on all three dart-ane instances. Disabled, not
  BYPASS. Stream 0 is translate. Streams 32-35 are past the 16-SID
  PARAMS4 limit and read 0.
- EDDEVARCH=0, EDPRCR=0. Core clock gated.
- 0x100009fc000 is `asc-firmware@100009fc000`, no-map, size 0x934000,
  phandle 0x209, referenced by nobody. It overlaps the tail of the
  macOS TEXT range.
- ioremap_np of 0x1000092c000 reads `d10005ea 924005ed f1000d5f
  54000d22`, not the firmware reset branch `0x14000081`. Those bytes
  are not in the selene file. 0x1000150c000 is all zeros.

RUN was not issued. The firmware is not at the macOS phys, and SID 15
is not in the macOS bypass state. Writing TEXT would also spill
0x18000 bytes into the asc-firmware reserved region.

## 9. Host-TM and mailbox, after the stock reboot

Stock Linux, boot.bin a3f533b9. Hardware experiments stopped here.

Power. All eight domains the ane node references, plus unreferenced
ane_sys@260, read ACTUAL=0xf via ioremap_np. ane_sys and ane_cpu
0x1f0003ff. ane_sys_mpm, ane_td, ane_base, ane_set1-4 0x000003ff.
The Linux DT has no clocks property. The ADT clock-ids 318-321 are
venc_pipe4/5 and venc_me0/1 at 0x290288008/010/018/020. Those four
and their parents were ACTUAL=0. pm_runtime_get on the provider
devices returned -EACCES. A parent-first TARGET=0xf write raised
venc_sys (0x0f000300 -> 0x0f0003ff) and venc_dma (0x300 -> 0x3ff);
the four then read ACTUAL=0xf with no new write.

Engine layout. The ADT and the Linux DT list the same three ranges:
engine 0x284000000/0x2000000, pmgr 0x28e080000/0x4034, set
0x28e08c000/0x4000. No TM sub-block. H13's TM is +0x20000 inside a
0x24000 slice. That offset from the 32MB base is 0x284020004. One
ioremap_np read there hung the machine; the watchdog brought stock
Linux back. No value was logged. The H13 slice translated into the
32MB region is 0x285c04000, the named kill window. Not read.

SID 15. Firmware staged in DRAM, first word 0x14000081. SID 15 TCR
0x9 and a valid TTBR on all three dart-ane instances (0x10039129,
then a fresh table 0x100201b9). Walk of IOVA 1<<40 hit that page.

RUN. CPU_STATUS 0x2a -> 0x28, SCRATCH7 stayed 0, no READY. Same
result with the VENC domains up. DART ERROR bit 31 stayed clear.
t8110 ERROR is flag bit 31, stream bits 27:20, code bits 14:0.
dart1 0x00f00000 is stream 15, code 0, flag 0, addr 0x3fe39dcbbdb.
dart2 0x00700000 is stream 7, code 0, flag 0, addr 0x3bacedea7f6.
dart0 addr 0x100000dca10 (1<<40+0xdca10), stream 0, code 0, flag 0.
Not a live SID 15 translation fault. The words did not change after
the second RUN.

Mailbox 0x285408000. A2I and I2A both 0x00020001 (ENABLE, EMPTY).
No HELLO. MGMT set-IOP-power ON (type 6, state 0x20) on A2I left
A2I at 0x00100101, EMPTY clear, message unconsumed. I2A stayed
empty. No reply in 2 s. CPU_STATUS still 0x28.

## 10. Engage-row candidates, read only

The macOS ADT ane0 IODeviceMemory has the same three ranges as the
Linux DT. It carries no PS, PWGATE, PTD, or ANEHAL whitebox range.
Only ANE (0x284000000) and PS (0x28E080000) bases are proven.

Reads via ioremap_np, no writes:
- PS 0x170 amcc2 0x1f0003ff, PS 0x2c8 pmp 0x1f0000ff, PS 0x2e0
  ane_cpu 0x1f0003ff. All ACTUAL=0xf. No missing domain here.
- pmgr+0x4000 through 0x4030 0x000003ff (the inferred PWGATE
  0x4008-0x4030 rows, already ACTUAL=0xf).
- pmgr+0xc000 (SET+0) 0x00000000; pmgr+0xc008 through 0xc038
  0x80000000. No known power-state shape.
- engine+0x570/0x5b8/0x5c0/0x1a9c not read: sub-block base unproven.

## 11. ISP/PRORES raise, restore, and mailbox decode

Reads first. ISP words and prores all ACTUAL=0: isp_cpu/isp_fe/
isp_vis/isp_be/isp_raw/isp_clr 0x00000300, dprx 0x00000200, prores
0x00000300, prores children 0. VENC 0x8008-0x8018 were already
ACTUAL=0xf from the earlier raise.

Approved raise, labeled words only. No DT parent existed for the ISP
nodes except prores under afnc3_lw0. TARGET=0xf writes: the six ISP
words latched target (0x30f, dprx 0x2ff) with ACTUAL 0. prores went
0x300 -> 0x3ff (ACTUAL 0xf). RUN with a new SID 15 TTBR 0x10097771:
SCRATCH7 0, CPU_STATUS 0x00, no READY. A2I 0x00100101, I2A
0x00020001. DART ERRORs unchanged.

Restore in reverse order. prores 0x3ff -> 0x900 (ACTUAL 0; was-clkgated
sticky, not a reopen). All six ISP words back to 0x300/0x200.
ISP and dprx marked target-latched with ACTUAL 0: gated by another
controller, not a provable ANE prerequisite.

Mailbox. Mainline ASC layout: FULL bit 16, EMPTY bit 17. A2I
0x00100101 = FIFOCNT 1, FULL 1, EMPTY 0. The IOP-power-ON message is
still sitting unconsumed in our send FIFO. I2A 0x00020001: FIFO
empty, the core has emitted nothing. The core is not consuming.

CPU_STATUS 0x00: no RUNNING, no STOPPED, no IDLE. 0x28 parked with
STOPPED clear but WFI; 0x00 after the ISP-touching RUN is a state
with no processor bit set at all.
