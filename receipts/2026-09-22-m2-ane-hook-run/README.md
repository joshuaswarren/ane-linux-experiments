# m2 (m2-host, T6021) ANE hook run — control discriminator + v4 root cause

Date: 2026-09-22 · M2AneHookRun · build host build-host, target m2-host

## Discriminator outcome: CONTROL BOOTS OMARCHY → fault is in the HOOK IMAGE BUILD/ASSEMBLY, not the stub/bless/build-config

- Control m1n1 built from a pristine worktree of upstream 4184923 (same commit
  the v4 hook tree used), `RELEASE=1`, LLVM-19 (`/usr/lib/llvm-19`), no hook code:
  `images/boot.bin.control-nohook` sha256 `a053020647c5da1e789fcd5290c7f4541a1bca6d0a4e33c6e32324d9761b33c6`.
- Assembly: control m1n1.bin (0x10c000) zero-padded to 0x110000, then the proven
  bridge payload (`/var/tmp/m2unpark/boot.bin`, sha512 `727b418a…`) bytes from
  0x110000 onward appended verbatim.
- Installed to ESP (disk0s4 "EFI - OMARC", /boot/efi/m1n1/boot.bin from Linux),
  on-volume sha verified = a0530206 before reboot. No re-bless needed (bless
  target unchanged from the working bridge boot).
- Booted 15:04:11 → reached Omarchy Linux (ssh m2-host-linux, uname
  7.1.13-3-1-ARCH). Stub, bless path, ESP handoff: all healthy (re-confirms the
  predecessor's bisect).

## v4 chainload root cause: FIXED-OFFSET payload padding

Main's camera photo of the stranded control boot shows the failure mode
exactly: m1n1 prints **"No valid payload found"**, initializes dart-usb0/usb1,
and parks at `Running proxy...` — its gadget never enumerates on this machine,
so the box strands with no network.

Mechanism: `payload_run()` walks payloads starting at `_payload_start`, which
the linker sets to the **0x4000-aligned end of that build's own m1n1 image**
(m1n1.ld:191). The bridge image works because its asahi-built m1n1.bin ends
exactly at 0x110000, so the payload lands right at `_payload_start`. The
prior lane's assembly (and my control) zero-padded a SHORTER m1n1.bin to the
fixed offset 0x110000, leaving 0x4000 zero bytes at `_payload_start`;
`load_one_payload()` reads the empty magic → "No more payloads" → no FDT, no
u-boot, no chainload. This also explains the v4 hook "fallback to macOS"
behavior: **v4 never executed its hook at all** — it never chainloaded, it
parked in proxy mode.

Fix (applied to the v5 build): append the payload at the image's true
aligned end, no fixed offset — v5-dry's m1n1.bin is 0x114000 and the payload
starts exactly there (`images/boot.bin.ane-dry-v5`,
sha256 `f6ad10bbe82210b55eec8005f5cea745478f4a793a08392629bdc79f891cc26d`,
source /tmp/m1n1-v5 = v4 tree minus all WDT arm/marker logic, pmgr-first
ordering + log-then-read + FDT chosen log retained).
**v5-dry was NOT booted** — the scp install failed pre-reboot and Main
re-prioritized the box to T6021RtkitPort; boot it when a window reopens
(install, verify on-volume sha = f6ad10bb, reboot, read
`/proc/device-tree/chosen/ane-bringup-log` over SSH).

## ANE register readbacks: NOT CAPTURED

No hook image has produced readbacks yet (v4/v5 never reached their register
window; the control/bridge carry no hook). The FDT-log mechanism is staged and
the corrected v5 image is built; capture remains open for the next window.

## Box end state

- m2-host booted Omarchy Linux 7.1.13-3-1-ARCH since 15:43:57, SSH confirmed.
- ESP boot.bin = bridge `727b418a…` / sha256 `41a39ac7…`, verified on-volume
  from macOS after write AND from Linux after boot.
- Bless: `sudo bless --mount /Volumes/Omarchy --setBoot`; `bless --getBoot` =
  `/dev/disk3s2` = the Omarchy stub's current node (verified before reboot).
- ESP backups: boot.bin.pre-proxy.on-esp (997890bc), boot.bin.v4dry-b0feef2f.bak,
  boot.bin.park-9ad08653.bak, boot.bin.dead-hook-65d1e8ae.bak.
- Box handed to T6021RtkitPort (Main's priority order) after Linux confirm.

## Timeline

- ~14:5x control built/installed, announced, booted 15:04:11 → Linux OK.
- ~15:1x v5 install attempt: scp "Connection closed"; box went dark ~15:08 —
  control image had parked at "Running proxy..." after a second reboot
  (stalled boot loop of the stranded-proxy state), unreachable ~40 min on all
  addresses (tailscale offline, rx 0).
- ~16:1x user power-cycled into macOS; camera photo via Main gave the
  "No valid payload found" evidence → root cause.
- 16:2x bridge restored from macOS (<macOS-LAN-addr>, <key>), sha verified,
  re-blessed by mount point, getBoot verified, reboot announced, 15:43:57
  Linux confirmed. Receipt written; local commits only (no pushes).

## Operational notes for the next lane

- Never pad an m1n1 boot.bin payload to a fixed offset: pad to the build's own
  `_payload_start` (aligned image end = m1n1.bin size for these builds).
- The stranded-proxy state is network-invisible: recovery needs macOS side or
  physical power-cycle.
- `ssh m2-host-linux` (<stale-ts-addr>) goes stale across boots; macOS side is
  currently `ssh -i ~/.ssh/<key> <user>@<macOS-LAN-addr>`.

## v6 write-arm handoff + final state (closeout)

- v6 write-arm image staged for the RTKit port lane: images/boot.bin.ane-write-v6,
  sha256 fd30afea59760cc48c3caec04d4544abab7b6f08f318f0c0cd3b9440a8baf004,
  size 0x795456 = write-arm m1n1.bin (0x2b8000, ANE_BRINGUP_WRITE=1 verified in
  the binary) + bridge payload appended at TRUE image end (corrected assembly).
  Full v4 WDT arm + ANE1 reset-skip marker, pmgr-first, log-then-read,
  /chosen/ane-bringup-log. Committed at 887fc9d (local only).
- v6 boot outcome (recorded by T6021FwStart, receipts/2026-09-22-t6021-rtkit-port/
  README.md section 10): firmware rejected the Asahi stub (bless had targeted
  the macOS Recovery container) -> Boot Recovery Assistant; the hook never
  executed. Stub repair ladder is owned by that lane; no further boots
  authorized for this ticket.
- ANE register readbacks remain NOT CAPTURED; v6 image is staged and assembly-
  correct for the next authorized window.
- This lane touched nothing further; per Main, closing out without touching
  m2-host on the way out.
