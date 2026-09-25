# M2 (m2-host, T6021 J414c) stuck after U-Boot — diagnosis and recovery plan (2026-09-23)

Lane: M2Unstick (parent Main). Model: anthropic/claude-opus-5-5. No write of any kind
was made to the M2. Evidence came from the jwm1 webcam (`/dev/video1`, which faces the
M2 screen), ssh probes, the receipts on lane/m2-recover, lane/t6021-fw-debug and
lane/t6021-b9, the M2Boot9 and LaptopRecover session transcripts, and the Asahi
U-Boot source.

## 1. Verdict

The M2 is stuck, not slow. It stops inside U-Boot after the autoboot countdown
reaches 0 and before U-Boot prints its first bootflow line, so GRUB and the kernel
never run. The boot.bin now on the ESP is byte-identical to the last image that
booted Linux, and every boot.bin variant we have carries the same U-Boot build.
Restoring a different boot.bin or dtb will therefore not fix it. The stall is in
U-Boot's EFI initialisation, which reads the NVMe disk and the ESP (`/ubootefi.var`)
and can write to the ESP. The only on-disk change that code reads since the last good
boot is the ESP, which macOS mounted read-write and then left mounted across a bare
`sudo reboot`.

## 2. Observation

- LaptopRecover restored `boot.bin` ← `boot.bin.stock-a3f533b9.bak` from macOS
  (on-volume sha a3f533b9…), blessed `/Volumes/Omarchy` (getBoot `/dev/disk2s2`) and
  ran `sudo reboot` at about 12:18Z.
- Webcam frames at 12:35:10Z, five frames 30 s apart from 12:35:38Z to 12:37:39Z, a 3 s
  burst at 12:41:43Z and a frame at 12:50:15Z all show the same screen. The mean
  absolute pixel difference of the text area against the first frame is 0.8 (sensor
  noise), and the area where the next U-Boot line would print stays black (max level
  ≤ 5/255). So the screen has not changed for at least 32 minutes.
- Screen text (`stuck-text-enhanced-1241Z.jpg`): `U-Boot 2026.07 (Sep 09 2026 -
  09:50:39 +0000)`, `Model: Apple MacBook Pro (14-inch, M2 Max, 2023)`, three
  `1 USB Device(s) found`, `scanning usb for storage devices... 0 Storage Device(s)
  found`, `Hit any key to stop autoboot: 0`, the m1n1 logo in the centre. Nothing after
  that line.
- ssh to `m2-host` (tailscale) timed out on every try from 12:35Z to 12:50Z;
  port 22 on the old mDNS LAN address is closed from macstudio. This is expected:
  the Asahi U-Boot is built with `CONFIG_NO_NET=y`.

## 3. Where a good boot goes next

`jwm1:/var/tmp/m2cam/m2-boot-20260923T002018Z.mp4` (sha256 cb078ca3…, the
M2Recover boot of stock 153170e0) shows the same U-Boot banner. Frame by frame
(`goodboot-countdown-to-grub.jpg`), within 0.1 s of `autoboot: 0` U-Boot prints:

```
** Booting bootflow '<NULL>' with efi_mgr
Booting: Label: nvme 0 Device path: /VenHw(...)/NVMe(0x1,...)/...
Using DT from U-Boot
error: fs/fshelp.c:find_file:260:file '/grub/arm64-efi/efi_env.mod' not found
```

and the GRUB menu is drawn at +0.1 s. The stuck boot never prints the first of these
lines.

Asahi U-Boot `asahi-v2026.07-2` (the version the uboot-asahi 2026.07.asahi2 package
builds) runs `CONFIG_BOOTCOMMAND="bootflow scan -b"`. Before the efi_mgr line can
print, `efi_mgr_read_bootflow()` calls `efi_init_obj_list()`, which does, in order:
`efi_disks_register()` (probe every NVMe block device and probe a filesystem on every
partition), `efi_init_variables()` (read `/ubootefi.var` from the ESP),
`efi_bootmgr_update_media_device_boot_option()` (can rewrite `/ubootefi.var` with
U-Boot's FAT write code), then the other EFI tables and capsule handling. The stall is
inside this sequence or in the NVMe hunt just before it.

Not involved: the btrfs root. The package runs `apple_m1_defconfig` plus
`olddefconfig` only, and `FS_BTRFS` has no default, so this U-Boot has no btrfs
driver. GRUB loads the kernel from the ext4 `/boot` partition
(`BOOT_IMAGE=/vmlinuz-linux-asahi`, GRUB paths under `/grub/` on nvme0n1p5), and
GRUB never started in this boot. The jwm1 GRUB/btrfs failure class does not apply,
and the btrfs reboot rule stays satisfied (boot files are on ext4).

## 4. Last known-good combination (M2FwStart closeout state)

| part | value | evidence |
|---|---|---|
| ESP `m1n1/boot.bin` | a3f533b9879cd0129d78d3d73715b3c9214e297459c7661c4195a9c2bc2683b2, 6,214,228 B, mtime 2026-09-22 20:49 CDT | M2Boot9 `ls`/`sha256sum` at 03:11Z |
| m1n1 part (first 1,114,112 B) | 9ad08653… = `/usr/lib/asahi-boot/m1n1.bin` (m1n1 1.6.1-1) | M2Boot9 `dd`+`sha256sum` at 03:12Z |
| t6021-j414c dtb in the image | stock 451cfceb… (`dtbs/t6021-j414c.dtb` = `.orig`); `.composed-bak` 9b83234a is not matched by `*.dtb` | M2Boot9 at 02:50Z; b9 README: the stock recipe reproduces a3f533b9 byte-for-byte |
| U-Boot | 2026.07, built Sep 09 2026 09:50:39 (`u-boot-nodtb.bin` 660,216 B) | banner in good-boot video and in the stuck frame |
| kernel | 7.1.13-3-1-ARCH (#1 SMP PREEMPT_DYNAMIC Sun, 13 Sep 2026) via GRUB from ext4 nvme0n1p5; root btrfs nvme0n1p6 `subvol=@` | fw-debug B1/B6/B8 dmesg |
| last good boot | about 21:28 CDT 2026-09-22 (uptime 11 min at 21:39:58); the B6-B8 runs after 20:49 used this image | M2Boot9 first-contact output; fw-debug README §3/§5 |

The concern that the "stock" backup carries a modified dtb is resolved: a3f533b9 is
the stock-dtb rebuild, and it booted after the dtb was restored.

## 5. What changed since the last good boot

1. 2026-09-23 03:14:32Z (Linux, M2Boot9): `cp boot.bin boot.bin.stock-a3f533b9.bak`,
   `cp boot.bin.b9-dry boot.bin` (D1, 0130305f…), `sync`, clean `systemctl reboot`.
2. D1 failed in stage 1 (loader bar at 0 %), iBoot fell back, and the box sat at the
   recoveryOS "Recovery Assistant" dialog until Joshua booted macOS this morning.
3. About 12:17Z (macOS, LaptopRecover): `sudo diskutil mount disk0s4`,
   `sudo cp boot.bin.stock-a3f533b9.bak boot.bin`, sha verified, bless, then
   `sudo reboot` with the ESP still mounted. The pre-restore boot.bin sha was not
   recorded. (M2Recover on 2026-09-22 unmounted the ESP before its macOS → Linux reboot,
   which booted.)
4. No OS has mounted the ext4 `/boot` or the btrfs root since the clean 03:14Z shutdown
   [INFERENCE: macOS and recoveryOS cannot mount them; nothing in the transcripts did].

## 6. Recovery plan (no flashing; each step only if the one before fails)

Files to restore: none. `m1n1/boot.bin` must stay a3f533b9…2683b2. The alternatives
on the ESP (153170e0 pre-proxy, the composed-dtb and bisect rebuilds) carry the same
U-Boot and cannot change a stall that happens inside U-Boot's EFI setup.

Step 1 — cold retry (Joshua, no macOS). Hold the power button about 10 s until the
screen is black, release, press it once, touch nothing. A hard power-off is the only
exit from this state and every other path needs it. Watch on the camera: pass =
`** Booting bootflow '<NULL>' with efi_mgr` right after `autoboot: 0`, then GRUB,
then Linux (about 60 s in the good boot). A pass means the stall was transient
hardware state. Then verify Linux health.

Step 2 — U-Boot prompt (Joshua at the keyboard, no macOS). Power-cycle and press
Space when `Hit any key to stop autoboot` shows (the window is 1-2 s). At `=>`, type
one line at a time and wait for output; we read it on the camera:

```
nvme scan
part list nvme 0
fatls nvme 0:4 /
ext4ls nvme 0:5 /
```

A hang on the first line points at the NVMe/partition probe (go to Step 3). If all
four return, the stall is in the `/ubootefi.var` path. Then boot Linux without the
EFI layer. This reads the disk only; use the names that `ext4ls` printed, and load the
initramfs last so `${filesize}` is its size:

```
load nvme 0:5 ${kernel_addr_r} /vmlinuz-linux-asahi
load nvme 0:5 ${ramdisk_addr_r} /initramfs-linux-asahi.img
setenv bootargs root=UUID=4f4d5801-524f-4f54-8000-000000000001 rw rootflags=subvol=@ rootfstype=btrfs zswap.enabled=0
booti ${kernel_addr_r} ${ramdisk_addr_r}:${filesize} ${fdtcontroladdr}
```

`kernel_addr_r`/`ramdisk_addr_r` are set by the Apple board code, `booti`, `ext4ls`,
`fatls` and `load` come from `BOOT_DEFAULTS`, and linux-asahi installs the raw arm64
`Image` as vmlinuz, which `booti` accepts. This path has not been run on this box yet.
From Linux, run read-only `fsck.vfat -n /dev/nvme0n1p4`, list and hash the ESP, then
repair only what the evidence shows (with Main's go), and do one normal reboot to prove
autoboot.

Step 3 — macOS (only if Step 2 is impractical or `nvme scan` hangs). Joshua holds
power and picks Macintosh HD; ssh with `-i ~/.ssh/id_rsa_2025`. Read-only first:
`sudo fsck_msdos -n /dev/rdisk0s4` with the ESP unmounted, `sudo diskutil mount
readOnly disk0s4`, `ls -laR` and `shasum -a 256` of `m1n1/boot.bin` (expect
a3f533b9…), `ubootefi.var` and `EFI/BOOT/BOOTAA64.EFI`, then `diskutil unmount
disk0s4`. Repair by evidence with a go: `fsck_msdos -y` for FAT errors; if the FAT is
clean, rename `ubootefi.var` to `ubootefi.var.bad-20260923` (U-Boot recreates its
boot options, and without BootOrder bootflow falls through to the removable-media
path). Always unmount explicitly, confirm no OMARC mount, confirm `bless --getBoot` is
the Omarchy stub, then `sudo shutdown -r now`.

## 7. Files

- `stuck-1235Z.jpg`, `stuck-1250Z.jpg`: raw webcam frames, 15 minutes apart.
- `stuck-text-enhanced-1241Z.jpg`: 89-frame average of the 3 s burst, text region
  contrast-stretched.
- `goodboot-countdown-to-grub.jpg`: frames 52.2-54.4 s of
  `m2-boot-20260923T002018Z.mp4` (sha256 cb078ca3…): countdown, efi_mgr lines, GRUB.
