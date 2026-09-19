# Receipt: jwm1 ESP recovery initramfs + grub.cfg fix (2026-09-19)

## Root cause (as corrected by this pass)

The active recovery entry in `/grub-ane/grub.cfg` (745 B) was fatally broken in two
independent ways:

1. `search --no-floppy --fs-uuid --set=root 725346d2-…` pointed GRUB's root at the
   **btrfs** volume, but the kernel/initrd it then loads live on the **FAT ESP**.
   GRUB must resolve the ESP via `search --file /grub-ane/VMLINUZ.REC`.
2. The kernel line carried `init=/grub-ane/REPAIR.SH` — a path on the ESP, which is
   not mounted in early userspace, and the file itself is 0 bytes in the image. This
   `init=` override guarantees a panic even with a correct initramfs. Removed.

Additionally the earlier receipt's claim that the staged INITRD.REC was a
"universal fallback with ALL modules" was wrong in framing but the modules were
never the boot blocker: the ESP kernel `7.1.13-3-1-ARCH` (34,114,048 B, sha256
`570def6704c0a684cca66ee920910a933edda9ea5e7e0b1b0ae9b4718231d960`) has the entire
apple boot stack compiled **built-in**, proven from its embedded IKCONFIG
(`IKCFG_ST` at offset 16836752 of VMLINUZ.REC):

    CONFIG_NVME_APPLE=y  CONFIG_APPLE_SART=y  CONFIG_APPLE_RTKIT=y
    CONFIG_APPLE_MAILBOX=y  CONFIG_APPLE_DART=y  CONFIG_PCIE_APPLE=y
    CONFIG_SPMI=y  CONFIG_SPI_HID_APPLE_OF=y  CONFIG_SPI_HID_APPLE_CORE=y
    CONFIG_APPLE_DOCKCHANNEL=y

Module-compiled (=m) and verified present in the new initramfs by resolved filename:

    btrfs.ko            kernel/fs/btrfs/btrfs.ko
    appledrm.ko         kernel/drivers/gpu/drm/apple/appledrm.ko   (DRM_APPLE=m)
    adpdrm.ko           kernel/drivers/gpu/drm/adp/adpdrm.ko
    panel-summit.ko     kernel/drivers/gpu/drm/panel/panel-summit.ko
    hid-apple.ko        kernel/drivers/hid/hid-apple.ko
    usbhid.ko           kernel/drivers/hid/usbhid/usbhid.ko
    xhci-pci.ko         kernel/drivers/usb/host/xhci-pci.ko
    dockchannel-hid.ko  kernel/drivers/hid/dockchannel-hid/dockchannel-hid.ko (HID_DOCKCHANNEL=m)

Initramfs: rebuilt on jw14m2-linux (only box with the matching 7.1.13-3-1-ARCH
tree; jw16mbp1-linux has 7.1.6 only) with `mkinitcpio -k 7.1.13-3-1-ARCH -S
autodetect` — true full build, autodetect disabled. 268 modules in image (the
custom kernel tree has 1,862; the rest is unneeded because most of the Apple SoC
support above is built into this kernel). H14W9HelloRetry coordination done; no
device/kernel contact on jw14m2; `/tmp/jwm1-fallback.img` removed.

## Artifacts written

- Local: `/var/tmp/jwm1-esp/esp-recovery.part` (524,288,000 B — padded 8 B from
  524,287,992 to match the 1,024,000×512 B partition and 4096-B device block size;
  first dd attempt hit EINVAL on the unaligned 8-byte tail).
  FAT content of the first 524,287,992 B is unchanged; sha256 of the flashed image:
  `762321515b7c644e88a4d6c8f32deae4507bf2e42fd32f32e32f08c41c4bd8b0`.
- Device: `/dev/rdisk0s4` on jwm1 (`100.67.134.6`), raw dd via sudo, `conv=fsync`,
  DD_EXIT=0, 125×4194304 B.
- `/grub-ane/grub.cfg` → 702 B corrected config (search --file, no init=).
- `/grub-ane/INITRD.REC` → 24,929,281 B new initramfs,
  sha256 `23739973ebd799a8d95bc4319c51db82b4bdebf278b5719327db0c2cec9dbc11`.
- 0-byte `REPAIR.SH` / `LAPKG.TXZ` left in place; nothing references them.

## Verification (read-back is the proof)

Read `/dev/rdisk0s4` back from jwm1 (DD_EXIT=0), pulled local, re-parsed:
- sha256 read-back == flashed source == `762321515b7c…c4bd8b0`.
- INITRD.REC stored size 24,929,281 == source, bytes identical, same sha256.
- grub.cfg quoted from read-back matches the fixed config exactly
  (search --file, no init=, 702 B).
- jwm1 left in macOS; NOT rebooted.

## Verdict: GO

Reboot expectation: m1n1/GRUB menu with `set timeout=10`, default=0 →
"Omarchy Linux recovery (kernel+initrd from ESP)" boots the 7.1.13-3-1-ARCH
kernel with the full initramfs, mounts btrfs subvol `@` by UUID, hands off to
systemd → normal Omarchy boot. Entry 1 (btrfs-path boot) remains broken by the
known v7-inode GRUB issue and is not the default.
