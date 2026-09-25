# T6021 (M2 Max / H14) ANE RTKit client port — receipt (in progress)

Date: 2026-09-22 · T6021RtkitPort · the-m2-host

## 0. Status

| Milestone | State |
|---|---|
| 1. RTKit-client design against real mainline API | DONE (§2) |
| 2. CSNE_CMD/ANEFWRpcMsg layout recovery (static) | DONE to static limit (§3) |
| 3. Power-up + apple_rtkit_init + boot handshake + endpoint start | **Blocked at fw start** — client probes, gates pass, reads CPU_STATUS clean, refuses because no firmware is running (§5) |
| 4. First CSNE_CMD submit | Coded (opt-in `csne_ping=1`), not executed (§6) |

## 1. Architecture decision

The H14-generation ANE has no host task-manager window; the firmware owns
the task manager and Apple submits work over an RTKit mailbox RPC
(receipt 2026-09-18-t6021-engine-layout-mined, README 3c94058). The port
therefore reuses mainline RTKit verbatim:

- `drivers/soc/apple/rtkit.c` + `include/linux/soc/apple/rtkit.h`
  (`devm_apple_rtkit_init`, `apple_rtkit_boot`, `apple_rtkit_start_ep`,
  `apple_rtkit_send_message`, `apple_rtkit_poll`) — built into the
  the-m2-host kernel (`CONFIG_APPLE_RTKIT=y`), no RTKit code written by us.
- `drivers/mailbox/apple-mailbox.c` provides the mailbox channel. One
  patch (omarchy-linux `078f865d1`): the ADT gives ane0 exactly ONE
  interrupt entry (raw 0x374 = 884, 4 bytes — verified by decompressing
  `DeviceTree.j414cap.im4p` with pyliblzfse and reading the node), and
  upstream probe requires both `recv-not-empty` AND `send-empty`. The
  patch makes `send-empty` optional; when absent, `apple_mbox_send`
  polls the a2i control register (same shape as the existing atomic
  path) instead of sleeping on `tx_empty`.
- The ANE ASC mailbox at engine+0x1408000 (a2i/i2a controls
  0x285408110/0x285408114, live-read clean W10) is register-compatible
  with `apple,asc-mailbox-v4` (offsets 0x110/0x114/0x800/0x830/0x838 —
  m1n1 ASCRegs and upstream mailbox.c agree).

### Offset reconciliation (per Main's handoff question)

The handoff said "handshake via ASC block engine+0x1400000" while the
engine-layout receipt said "RVBAR +0x1050000, RTBuddy +0x1840000".
**Both are right; they are different registers in the same 32 MiB
aperture (0x284000000, ADT ane0 range0):**

| item | engine-relative | live evidence |
|---|---|---|
| CPU control (RUN) | +0x1400044 | kext h14g config-init; W10 live read |
| CPU_STATUS | +0x1400048 | W10 + this port (§5) |
| ASC mailbox (RTKit transport) | +0x1408000 block, ctrl +0x1408110/114 | W10 live read clean |
| RVBAR | +0x1050000 | W10 live read (latched 0x10000000001) |
| RTBuddy/MBI scratch regs | +0x1840000 block | kext mining |

The `+0x1608114` figure in the phase-1 tool was the h16g variant base —
the wrong address on this part (W10 correction, ane_t6021.h).

## 2. Client design (what the kernel does, in order)

`ane/t6021/ane_t6021_rtclient.c` (omarchy-ane `feat/t6021-rtkit-client`,
893324f + 786c716) binds the stock DTB's ane0 node
(`compatible = "apple,t6021-ane"`; the legacy H13-path ane_t6021.ko
shares the compatible and must NOT be loaded):

1. **Power**: `power-domains` binding (stock DTB already carries the
   full 8-domain chain incl. ane_sys_mpm) via `pm_runtime_resume_and_get`;
   then verify `ane_cpu` ACTUAL on the pmgr window (reg index 1):
   `(ACTUAL & 0xf) == 0xf` gate before any further MMIO
   (2026-09-22-t6021-power-dart-fwload G1).
2. **Non-posted mapping**: `/soc` carries `nonposted-mmio`, so the core
   marks the resource `IORESOURCE_MEM_NONPOSTED`; the driver checks the
   flag and maps with `ioremap_np` (no exclusive request — the mailbox
   child region 0x285408000 lives inside the 32 MiB window, so an
   exclusive request of the parent span self-conflicts; seen live, §5).
3. **fw-alive gate**: read `CPU_STATUS` (+0x1400048). If not RUNNING,
   the driver refuses `-EPROBE_DEFER` and never programs RVBAR or
   `CPU_CONTROL` — this box's RVBAR latch is sticky with mode bits
   55/48 missing and kernel-context ps@2e0/RVBAR writes are fatal
   (power-dart-fwload s23/s24). CPU start belongs to a quiesce context
   (m1n1/iBoot).
4. **RTKit**: `devm_apple_rtkit_init(dev, ane, NULL, 0, ops)` — picks up
   the mailbox via the `mboxes = <&ane_mbox>` DT link — then
   `apple_rtkit_boot()`: the firmware HELLOes first on MGMT EP0 (W2
   decode), rtkit.c answers, walks EPMAP, STARTEPs system endpoints,
   completes SET_IOP_PWR_STATE, then boot() sets AP power ON.
5. **Endpoint bitmap**: on `apple_rtkit_is_running()` the driver logs
   every advertised endpoint 0..63 — the hardware answer to the open
   "which endpoints carry the CSNE_CMD channels" item.
6. **RX**: mailbox recv IRQ (884) is primary; a 10 ms poll worker
   (`apple_rtkit_poll`) covers the unproven-IRQ case and continues at
   1 Hz with `poll_rx=1`.

## 3. CSNE_CMD / ANEFWRpcMsg layout (static recovery)

Sources: kext AppleH11ANEInterface 10.19.2 (mac14j 26A428), selene
t602x firmware, prior W2 decode (omarchy-ane 03b1f98), and the parallel
H14RpcProtocol receipt (`receipts/2026-09-22-h14-rpc-protocol/`).

- **Transport**: RTKit app endpoints owned by RTBuddyService; six
  channels, per-EP cfg table `__DATA_CONST.__const+0x814e520`
  (40 B/entry): EP1 INIT 64K, EP2 T2FC 256K, EP3 T2FH 256K, EP4 T2HS
  64K, EP5 T2HC 128K, EP6 T2HT 64K. Endpoint NUMBERS are confirmed at
  handshake time from the firmware's EPMAP (§2 step 5) rather than
  assumed.
- **Ring doorbell word** (SetupEndpoints): offset | size_code | unit,
  bit placement CONFLICTED between decodes — W2: offset[43:0] |
  size[51:44] | unit[53:52]; H14RpcProtocol: offset[0:28) |
  size_code[28:36) | class[36:38). Unresolved; flagged, not guessed.
- **Per-command word** (rtbuddyEndpointSendMessage 0x…95f3990):
  cursor[23:0] | len[47:24], len capped 0xffffff.
- **Header** (sendSetupCmd @0x…95e4314): u16 CSNE cmd id @+4, u8 flags
  @+6 (bits[0:5] preserved, bits[5:7]=1), u8 @+7=0, u32 args @+0x1c
  (+0x20 two-arg). Typical size 0x20/0x24. Commands are carved out of
  the shared ring, not separate allocations.
- **Opcodes**: 96 names, generation-stable H13↔H14; ids in
  `receipts/2026-09-18-t6021-engine-layout-mined/w2/fw_cmd_table.json`;
  0x400-0x404 corroborated in kext immediates (HIGH): PING=0x11,
  BUILDINFO=0x06, BOOT=0x10, PROCEDURE_CALL=0x204, INFERENCE_CALL=0x404.
  Fw→host events = CSNE cmds 0x0100-0x0108 on T2H_CMD; completion is
  fw-side poll-timer, not push.
- **ANEFWRpcMsg** is the kext-side IOService wrapper class
  (`ANEFWRpcMsg::create`, syms 5197/5268/6968-6979) around exactly this
  channel+ring+word scheme; no additional wire format exists beyond
  what is listed here.

## 4. Kernel/mailbox artifacts

| artifact | where |
|---|---|
| Client driver | omarchy-ane `feat/t6021-rtkit-client` → `ane/t6021/ane_t6021_rtclient.c` |
| Overlay v2 | same branch → `ane/t6021-j414c-ane-rtkit.dts` (adds mailbox child + `mboxes` link to stock ane0; supersedes v1) |
| Mailbox poll-TX patch | omarchy-linux `078f865d1` (drivers/soc/apple/mailbox.c) |
| Out-of-tree mailbox module | `ane/t6021/mailbox-poll/` (mainline source, driver renamed `apple-mailbox-poll` to coexist with the builtin, duplicate EXPORT_SYMBOLs stripped) |
| Box staging | the-m2-host `/var/tmp/rtkit-port/{mbp,rtclient}/` + installed dtb `/lib/modules/$(uname -r)/dtbs/t6021-j414c.dtb` (orig backed up `/tmp` is volatile — backup copy `t6021-j414c.dtb.orig` was in /tmp, regenerate from overlay) |
| ESP | `boot.bin` rebuilt by `update-m1n1`; pre-change copy `/tmp/boot.bin.pre-rtkit` (volatile; volume backups 41a39ac7 bridge et al. still on ESP) |

## 5. Hardware evidence — milestone 3 reached its gate and refused (2026-09-22)

Boot 1 with overlay v2 installed (no m1n1 hook, so no firmware running):

```
[    0.062958] apple-mailbox 285408000.mailbox: error -ENXIO: IRQ send-empty not found   ← builtin, expected
[    0.075713] platform 284000000.ane: Adding to iommu group 6
[   46.330723] Error: Driver 'apple-mailbox' is already registered, aborting...          ← first module build, name fixed after
    (after loading ane_mailbox_poll.ko: driver bound to 285408000.mailbox)
[  279.819244] ane_t6021_rtclient 284000000.ane: ane_cpu ACTUAL = 0x1f0003ff
[  279.819257] ane_t6021_rtclient 284000000.ane: CPU_STATUS = 0x2a
[  279.819261] ane_t6021_rtclient 284000000.ane: ANE firmware not alive (CPU_STATUS 0x2a)
               — start it from a quiesce context (m1n1/iBoot); this driver will not program RVBAR
```

- genpd raise through runtime PM works; `ACTUAL & 0xf == 0xf` passed.
- First-ever non-posted engine read on this boot path: `CPU_STATUS
  0x2a` (STOPPED|IDLE) — matches W10 exactly, read-clean, no abort, no
  hang. Box healthy after.
- The refusal is the designed behavior: kernel-context RVBAR is fatal
  on this box; the missing precondition is a running firmware, which
  only a quiesce-context boot can provide.

## 6. First CSNE_CMD submit (coded, fenced)

`csne_ping=1` (module param, default off): after a completed handshake
and only if the fw announced the INIT endpoint, the driver
1. sends the SetupEndpoints doorbell word for a 64 KiB coherent INIT
   ring (dart-mapped IOVA via the stock iommus binding, stream 0),
2. `apple_rtkit_start_ep(INIT)`,
3. memcpy's an 8-byte `CSNE_CMD_PING` (0x11) header at ring cursor 0
   with `dma_wmb()`,
4. sends `cursor[23:0] | len[47:24]` on the INIT endpoint.

The SetupEndpoints doorbell bit placement is [INFERENCE] (§3 conflict);
this attempt is deliberately informational.

## 7. Remaining work before real inference

1. **Firmware start from quiesce context** — one m1n1 write-arm boot
   (pmgr raise → DART map selene at vm-base 0x10000000000 → RVBAR →
   CPU_CONTROL RUN → SCRATCH wake). Awaiting go/no-go.
2. Handshake + endpoint bitmap capture (automatic once fw runs).
3. Resolve the SetupEndpoints doorbell bit-placement conflict (§3).
4. `ANESharedMemorySurfaceParams` layout + boot-args surface identity
   (BOOT command context).
5. Ring carve-out bookkeeping (fw-side alloc from `dev+0x968/0x980`
   pool) before INFERENCE_CALL/PROCEDURE_CALL can carry payloads.
6. Non-posted TX semantics through apple-mailbox (the patched poll path
   uses `readl_poll_timeout_atomic` on the non-posted control register —
   first hardware exercise pending).

## 8. Netconsole status (Main's condition 2) — BLOCKED on hardware, documented

- netconsole loads and starts on the-m2-host (`network logging started`) with
  dst the-listener-host-lan (the-listener-host, link-local /23), both gateway-resolved and
  explicitly pinned remote MAC (the-listener-host-wlan-mac, `remote ethernet
  address` line in dmesg). The listening receiver on the-listener-host is confirmed
  bound (`ss -lunp` → python3 pid) and the box→the-listener-host UDP path works for
  ordinary sockets? — NO: plain UDP box→the-listener-host on the same path was NOT
  independently retested; box→workstation UDP was verified working
  while netconsole silently dropped.
- Root cause (high confidence): netpoll TX on `wlan0` (cfg80211 needs
  process context; packets are silently dropped in netpoll context).
  Every configuration — routed, link-local, broadcast MAC, pinned
  unicast MAC — sent nothing. Netconsole on this box needs a wired
  (USB-ethernet) interface; that is a hardware change and out of scope.
- Compensating controls in force: m1n1 hook logs every MMIO access
  before execution to console + FDT buffer (`/chosen/ane-bringup-log`
  survives into Linux), WDT bites + `ANE1` reset-marker makes the next
  boot skip the hook; Linux-side probe runs over SSH with the kernel
  log streamed live to the workstation.

## 9. State at handoff

- the-m2-host: healthy, Omarchy, boot.bin contains overlay-v2 dtb
  (t6021-j414c replaced; original saved at the-listener-host-independent location:
  regenerate via `fdtoverlay -i t6021-j414c.dtb.orig -o … overlay.dtbo`;
  the pristine stock dtb also ships with the kernel package).
- Box modules staged at `/var/tmp/rtkit-port/{mbp,rtclient}/`.
- v6 write-arm image (sha256 fd30afea…) staged by M2AneHookRun, NOT yet
  installed — netconsole condition could not be met literally; decision
  handed to Main (accept FDT/UART/WDT + SSH-stream substitution, or
  provide wired networking).

## 10. v6 boot attempt (2026-09-22, this lane) — firmware REJECTED the stub; box currently at Boot Recovery Assistant

### What was executed and verified (receipts)
- Reachability: macOS side reachable only at `recovery-lan-address` (the-target.local,
  mDNS unresolvable from workstation; key `id_rsa_2025`, port 22 answers at
  login window). Linux LAN `the-m2-host-lan` and tailscale `the-m2-host-tailscale`
  unreachable throughout.
- Stub node resolved THIS boot: `diskutil info /Volumes/Omarchy` →
  `/dev/disk2s2`, Volume Name: Omarchy (ESP = disk0s4 "EFI - OMARC").
- ESP on-volume sha verified: `shasum -a 256 /Volumes/EFI*/m1n1/boot.bin`
  = `fd30afea59760cc48c3caec04d4544abab7b6f08f318f0c0cd3b9440a8baf004` (v6).
- `sudo bless --mount /Volumes/Omarchy --setBoot` → BLESS_OK;
  `bless --getBoot` → `/dev/disk2s2`; `diskutil info` on that node →
  Volume Name: Omarchy. Bless chain was CORRECT this time.
- Module refresh staged to ESP `rtkit-port/`:
  `ane_t6021_rtclient.ko` sha256 `28aa1b88f2c3af3c3dae7d55df879e187dc84ef22c
  57aaeac78f3277a479bdb9` (omarchy-ane @ 786c716 build) + source tarball
  `ane-t6021-786c716.tgz` (mailbox_poll rebuild material).
- Announced to all lanes; `sudo -n reboot` issued; boot fired.

### Outcome and corrected root cause
- The firmware did NOT reach the hook: Joshua reports the Mac explicitly
  refused the selected target ("the version of macOS on the selected disk
  needs to be reinstalled") and fell to Boot Recovery Assistant.
- Supersedes the earlier bless-targeting theory: even with bless verified
  pointing at the current Omarchy stub node, the firmware REJECTED the stub
  volume as unbootable. The Asahi stub itself now fails firmware validation.
  Suspect causes: repeated ESP writes today, or an interrupted
  update-m1n1. This is a machine-bootability issue; the ANE milestone is
  secondary.
- dmesg defects seen on the previous Linux boot are fully explained by
  stale pre-786c716 module binaries on the box: current HEAD names the
  mailbox driver `apple-mailbox-poll` (mailbox_poll.c:464) and the rtclient
  makes NO exclusive request_mem_region (ane_t6021_rtclient.c:244). Both
  lines should vanish once on-box modules match 786c716.

### Evidence to capture the moment the box is reachable
1. `bless --info --mount /Volumes/Omarchy` (from macOS) — full stub status.
2. Mount the stub's Preboot volume (`disk2s3`-equivalent, re-resolve) and
   check `/<volume-group-UUID>/System/Library/CoreServices/` contains
   `boot.efi`, `SystemVersion.plist`, and matches the Omarchy stub UUID
   shown by `diskutil info /Volumes/Omarchy` (Volume UUID / VG UUID).
3. `bless --getBoot` right after boot to macOS (node renumbers).
4. From the Linux rootfs (disk0s6) if mounted from macOS: `/var/log` around
   the last successful update-m1n1 run, plus `/boot/efi/m1n1/boot.bin` sha,
   and `/proc/device-tree/chosen/ane-bringup-log` if Linux ever boots.
5. `nvram 94b73556-2197-4702-82a8-3e1337dafbfb:ASBB` style variable is NOT
   required; do not clear NVRAM speculatively.

### Stub repair ladder (least → most invasive; goal = bootable Omarchy first)
1. **Verify only** (zero risk): macOS → `bless --info --mount
   /Volumes/Omarchy`; if it reports the volume bootable and getBoot sticks,
   the rejection may have been transient — single controlled reboot allowed.
2. **Re-bless from macOS GUI Boot Picker** (near-zero risk): hold power,
   pick "Omarchy" by hand. The picker only offers volumes iBoot considers
   bootable; if Omarchy is absent from the picker, the stub is definitively
   damaged. Booting via picker also re-arms firmware metadata.
3. **Re-run update-m1n1 from Omarchy Linux** (low risk, needs Linux booted
   via step 2): `sudo update-m1n1` (Asahi tooling) rewrites the stub
   contents and re-blesses atomically; restores known-good m1n1/u-boot +
   our boot.bin. Risk: none to macOS; ESP rewritten (re-stage our v6 +
   rtkit-port/ afterwards).
   - NOTE for later: after ANY stub rebuild, re-apply overlay v2 to the
     dtb BEFORE rebooting into the hook boot (regenerate via `fdtoverlay
     -i t6021-j414c.dtb.orig -o … overlay.dtbo`), or milestone-1 regresses.
4. **Stub repair from macOS** (moderate risk): if Linux cannot boot,
   mount disk0s6, re-copy stub payload per Asahi docs, or use
   `bless --mount … --setBoot --verbose` diagnostics. Risk: touching APFS
   system volumes; do NOT bless Macintosh HD away from macOS default.
5. **Reinstall Omarchy stub via asahi-installer/UGT** (invasive, last):
   reinstall the Asahi boot object from macOS recovery/1TR. Risk: worst
   case requires reinstalling the Linux userspace; never touches the
   macOS data volume if done per docs. Absolute last resort; needs
   Joshua's explicit go.

### State at close of this lane
- Box: last known at Boot Recovery Assistant screen; all network paths
  silent; standing order — no probes, no reboots, no re-bless without Main.
- ESP retains v6 fd30afea + `rtkit-port/` module payload (shas above).
- ANE protocol work and the RTKit handshake remain PENDING the stub repair;
  no hook execution has occurred (FDT `/chosen/ane-bringup-log` was never
  produced by any v6 attempt).

## 10. v6 boot outcome (2026-09-22 evening) — hook never executed

- v6 fd30afea installed to /boot/efi/m1n1/boot.bin with on-volume sha
  verified; reboot issued at the announced time. Result: the firmware
  rejected the Asahi stub — bless had targeted the macOS Recovery
  container — and the box went to Boot Recovery Assistant. v6 never
  ran; no ANE state was touched by the hook.
- Post-recovery dmesg showed "apple-mailbox already registered" and
  rtclient -EBUSY: both are STALE pre-786c716 module binaries (old
  driver name, old exclusive request_mem_region), not defects in HEAD.
  Current builds in /var/tmp/rtkit-port load clean (milestone-1 §5).
- Correct-evidence boot requires: bless corrected to the Asahi stub,
  v6 fd30afea verified on-volume, then the announced boot. ANE
  readbacks remain NOT CAPTURED.

### 10.1 Correction (T6021FwStart, same evening)

The 15:5x reboot had bless VERIFIED correct (getBoot = disk2s2 =
Omarchy stub, node resolved that boot) and the firmware still rejected
the stub — so the root cause is stub-level validation failure
(repeated ESP writes / interrupted update-m1n1), not bless targeting.
Repair ladder and evidence list: §10 appendix above. Box under Main
no-contact standing order; next authorized boot = Main's go + Joshua's
hands, with: stub repair, on-volume sha re-verify of v6 fd30afea, and
overlay-v2 dtb re-applied before the hook boot.
