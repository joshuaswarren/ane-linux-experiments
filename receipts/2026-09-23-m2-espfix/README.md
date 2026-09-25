# M2 (m2-host) ESP repair from macOS, then Linux boots (2026-09-23)

Lane: M2EspFix (parent Main). Model: anthropic/claude-opus-5-5. This executes step 3 of
`receipts/2026-09-23-m2-unstick/README.md` (d219c20). Result: Linux booted by normal
autoboot about 50 s after the macOS reboot, reached `running` with no failed units.

## What was done (macOS 27.0, ssh to its mDNS LAN address, `caffeinate -dimsu`)

1. `diskutil list`: the only EFI-type partition on disk0 is `disk0s4` "EFI - OMARC"
   (524.3 MB, FAT32, partition UUID A420CF0F…). The Omarchy stub is `disk2s2`. The ESP
   was not mounted.
2. `sudo fsck_msdos -n /dev/rdisk0s4` (unmounted): no structural errors, 253 files, but
   `MARK FILE SYSTEM CLEAN? no` / `FILE SYSTEM IS LEFT MARKED AS DIRTY`. The dirty bit is
   the fault the plan predicted, so `sudo fsck_msdos -y /dev/rdisk0s4` ran:
   `MARKING FILE SYSTEM CLEAN`, rc 0. A second `-n` pass was clean.
3. Read-only mount, full listing and hashes in `esp-before-ls-laR.txt` (with an `xxd` of
   `ubootefi.var`):
   - `m1n1/boot.bin` a3f533b9879cd0129d78d3d73715b3c9214e297459c7661c4195a9c2bc2683b2 (expected)
   - `ubootefi.var` a6e5ec853a23e132d00ff9776dd4fa3919c36529fb301ae6eca731f521ddf0db (728 B;
     Boot0000-0002 for nvme 0/1/2, BootOrder, PlatformLang en-US)
   - `EFI/BOOT/BOOTAA64.EFI` 8028d3b82f1797cdddfcaaa0ceb12b9ce5a251514266c7532f3715f69401e5a0

   Then read-write mount: created `.metadata_never_index`, renamed `ubootefi.var` to
   `ubootefi.var.bad-20260923`, deleted `.Spotlight-V100`, `.Trashes`, `.fseventsd` and
   23 `._*` AppleDouble files. `boot.bin` sha re-checked unchanged.
4. `sync`, `sudo diskutil unmount disk0s4` (rc 0), `Mounted: No`, no `EFI - OMARC` line
   in `mount`. `fsck_msdos -n` afterwards: 36 files, no dirty warning. A read-only
   remount showed no recreated `.fseventsd` or `._*`, then it was unmounted again.
5. `bless --getBoot` was already `/dev/disk2s2`. `sudo bless --mount /Volumes/Omarchy
   --setBoot` printed a password prompt, got empty stdin and returned rc 0;
   `--getBoot` stayed `/dev/disk2s2`. NVRAM `boot-volume` names partition 13FFC613…
   (disk0s3 13C6FF13… in mixed-endian GUID order) and volume group 5AE8D78F… (Omarchy).
6. `sudo shutdown -r now` at 13:19:22Z with the ESP unmounted.

## Result (Linux, ssh `m2-host` over tailscale)

ssh answered at 13:20:19Z; the journal's first line is 08:20:08 CDT (13:20:08Z). The
webcam was not needed. From `linux-health.txt`:

- `Linux m2-host 7.1.13-3-1-ARCH #1 SMP PREEMPT_DYNAMIC Sun, 13 Sep 2026 17:52:27 +0000 aarch64`
- cmdline `BOOT_IMAGE=/vmlinuz-linux-asahi root=UUID=4f4d5801-… rw rootflags=subvol=@ …`
- `systemctl is-system-running`: `running`; `systemctl --failed`: 0 units
- `journalctl -b -p err`: only driver noise (apple-dcp dp-xbar/dp-phy -517 probe
  deferral, avd firmware -2, brcmf -52, Bluetooth codec -22, bpf-restrict-fs LSM
  unsupported, apple-mailbox send-empty IRQ). No emergency mode, no mount errors.

`linux-esp.txt`: U-Boot recreated `ubootefi.var` on this boot, and it is byte-identical
(a6e5ec85…) to the renamed file. So the old variable store was not corrupt. The stall
cleared after the dirty FAT and the macOS metadata were removed together; this run does
not separate those two causes [INFERENCE].

`/boot/efi` is mounted rw by Linux (`vfat rw,…,errors=remount-ro`). Before the next macOS
session that touches the ESP: unmount it explicitly before rebooting, and keep
`.metadata_never_index` in place.
