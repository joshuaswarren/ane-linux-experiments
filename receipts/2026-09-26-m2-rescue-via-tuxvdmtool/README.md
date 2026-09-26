# M2 rescue reached remotely through Linux USB-PD after a U-Boot stall (2026-09-26)

Lane: M2RescueRepair (parent Main). This receipt records an operational
remote-reset capability and a read-only ESP state verification. It makes
**no** boot-recovery claim: the disk-boot stall root cause is NOT
established (see "Claim discipline").

## Preceding state

- After one reboot out of the live BusyBox rescue into the normal disk
  path, the M2 froze in U-Boot after `Hit any key to stop autoboot: 0`:
  identical webcam frames for 115 s+, no GRUB menu (timeout is 3 s), no
  kernel text; all network routes dark. Camera: M2CameraWatch frames
  frame-0118/0126/0127 on jwm1.
- This is the same stall point documented in
  `receipts/2026-09-23-m2-unstick/` ("same U-Boot across payloads",
  suspected EFI-init/ubootefi.var/NVMe class, unproven there and still
  unproven here). Laptops were offsite, so the documented cold-retry path
  (power button) was unavailable.

## Port mapping used (read receipts, no partner probing on port1)

- M2-facing PD chip on jwm1 is the controller at i2c 0x38:
  `jwm1-usb-host/RECEIPT.md` ("PD chip at i2c0 0x38 ... the M2-facing
  port"; the "port1" wording there is USB-controller numbering for
  usb@382280000, not the typec class index), `evidence/marker-boot-readout.md`
  ("chip@0x38 = M2-facing port", iBoot-stage data blip), and
  `evidence/TARGET-MET.md` (1209:316d ttyACM on that port).
- Runtime check: `/sys/class/typec/port0` resolves to `0-0038`, labeled `USB-C Left-back`.
- Do not read port1 partner identity attributes on this kernel. Reads caused
  `id_header_show` and `product_show` kernel oopses. No reset targeted that port.

## Tool and reset (root-operated; timeline from root instrumentation)

- Upstream: https://github.com/AsahiLinux/tuxvdmtool
- Source: `4f3fed6a8c7b6fc6f656efd8df7620b1dbcb30ee`; native `cargo build --release --locked` passed.
- Installed: `/usr/local/bin/tuxvdmtool`, version `0.2.0`.
- Binary SHA-256: `d58133d5dc7f2157d195d89c92edcde1f63f37de8c59614ebea9904b9c147b9b`.
- Command as root on the M1 Linux host: `tuxvdmtool --connector Left-back reboot`, exit 0.
- Timeline (CDT): 12:13:44 reset issued -> 12:14:01 ACM caught by the armed
  one-shot final3 catcher -> 12:14:09 kboot
  disconnected -> rescue SSH up, `uname` = 7.1.13-3-1-ARCH,
  `root=/dev/ram0 rw init=/init`. Independent confirmation: remote
  watcher saw rescue SSH on the M2's DHCP address at 17:14:29Z.

This is the first documented Linux-side VDM reboot of the M2 from jwm1 —
the portable replacement for the macOS `macvdmtool reboot` path while the
laptops are offsite.

## ESP state after the stall (read-only; fsck on pulled image)

Method: guarded probe on the live rescue (GPT entry-4 type GUID verified
= C12A7328-F81F-11D2-BA4B-00A0C93EC93B and size 1024000 sectors before
any mount), 500 MB partition image pulled, fsck run OFF-box:

- `fsck.fat 4.2 -n esp-p4.img`: **clean** — "44 files, 58375/127718
  clusters", zero errors (`fsck.out`). FAT dirty bit (boot sector 0x41)
  = 0x00.
- `ubootefi.var` sha256 `a6e5ec853a23e132d00ff9776dd4fa3
  919c36529fb301ae6eca731f521ddf0db` — byte-identical to the store U-Boot
  recreated and the 2026-09-23-m2-espfix run proved good.
- `EFI/BOOT/BOOTAA64.EFI` sha256 `8028d3b8...` — identical to the
  2026-09-23 record.
- `m1n1/boot.bin` sha256 `43ec6090...dea86`, 6,279,764 B, dated Sep 25
  10:55 — matches no previously recorded variant (stock a3f533b9, v1
  65d1e8ae, v4dry b0feef2f, pre-proxy 153170e0, park 9ad08653, v6
  fd30afea). Its mtime predates the last successful journaled boot
  (Sep 25 20:37). That timestamp alone does not prove identical bytes
  at that boot or identify the cause of the current stall.
- Raw evidence: `probe.out`, `fsck.out` (this directory); full image at
  `/tmp/m2-repair-current/esp-p4.img` sha256 `d1f3b76af0f23e48eae3919a
  53462bddb9366a0f0d1c933219884cb5f4d813d3` (workspace-local, not
  committed).

## Claim discipline

- FAT checks and comparisons found no filesystem damage or changed EFI variable store.
  They do not exclude a boot-logic state bug in U-Boot/EFI initialization.
  A transient stall remains a hypothesis, not a finding.
- No normal boot was attempted after the verification; the one-shot
  final3 rescue catcher stays the guarded fallback and the rescue session
  was preserved.

## Files

- `probe.out` — full probe transcript (ESP listing, hashes, vermagic,
  NVMe dmesg sanity).
- `fsck.out` — fsck.fat read-only pass on the pulled image.
