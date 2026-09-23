# jwm1 reboot gate (btrfs v7 GRUB) — 2026-09-23

Root: /dev/nvme0n1p5[/@] btrfs compress=zstd:1, space_cache=v2; /boot on same btrfs.
ESP nvme0n1p4 vfat; boot chain: iBoot -> m1n1/boot.bin -> EFI/BOOT/BOOTAA64.EFI
(GRUB 2.14, grub pkg 2:2.14-1.1, image built Sep 20 08:10 from the installed
module set) -> btrfs -> /@/boot/vmlinuz-linux-asahi. bootctl of the outgoing
session: Product GRUB 2.14 (GRUB booted the Sep 22 15:07 session reading this fs).

gate-reboot fstest (grub-fstest /dev/loop0, losetup of p5, -d /usr/lib/grub/arm64-efi
= same package build as the ESP image):
  ls /@/boot                      -> vmlinuz-linux-asahi grub/ initramfs-linux-asahi.img efi/
  cmp /@/boot/vmlinuz-linux-asahi    -> RC=0 byte-identical (35,834,368 B)
  cmp /@/boot/initramfs-linux-asahi  -> RC=0 byte-identical (19,871,870 B)

sha256:
  BOOTAA64.EFI            fc9ea5c61430562168a62aaca592f8e6721dfe59c404246dc98fc2d35019cb3d
  m1n1/boot.bin           41a39ac756fb181cf1abb052199cb45893e2ed5d1368c7db495a71f23f027bd5
  grub.cfg                f98179847d4da91bb8c96b9f820ef654e05b1c2f5a3acaeb11eb98a636f9dd3f
  vmlinuz-linux-asahi     c9764582601a847d64943d1a19008c589e87b9e79c5ad416773dee6a8a05a17c

Return path: asahi-bless -n -y --set-boot 1 (Macintosh HD, next-boot-only);
default stays Omarchy -> automatic return to Linux. Volumes at gate time:
  1) Macintosh HD
* 2) Omarchy  (current default)
