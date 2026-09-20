# jwm1 ESP forensic audit — the storage-driver theory was wrong

Date: 2026-09-19
Where: audit performed off-box (omp host) against the staged ESP images in
`/var/tmp/jwm1-esp/`, plus module-tree facts read from jw14m2 (same kernel).
Method: `mtools` (mdir/mtype/mcopy) on the raw partition images, `cpio` +
`gzip` on the extracted initramfs, `strings` on the GRUB EFI binary. No
mounting (container lacks CAP_SYS_ADMIN), so every claim below comes from
reading bytes out of the image rather than from a live mount.

## Why this audit happened

jwm1 failed to boot Linux across several remote ESP-patching attempts, with
three distinct symptoms reported from the console: first an `asynchronous
SError interrupt` panic, later emergency mode (`Cannot open access to console,
the root account is locked`), and most recently GRUB refusing with *"you need
to load the kernel first"*. Each attempt was driven by a hypothesis that was
never checked against the actual bytes on the ESP.

## Finding 1 — the "missing Apple storage drivers" theory is dead

The prevailing explanation for emergency mode was that the initramfs had been
`autodetect`-pruned on jw14m2 (T6021) and therefore lacked the Apple NVMe /
SART / DART drivers that jwm1 (T8103) needs, so jwm1 could not see its own
SSD. That is false.

On kernel `7.1.13-3-1-ARCH`, `/lib/modules/7.1.13-3-1-ARCH/modules.builtin`
contains:

```
kernel/drivers/nvme/host/nvme-core.ko
kernel/drivers/nvme/host/nvme.ko
kernel/drivers/nvme/host/nvme-apple.ko
kernel/drivers/soc/apple/apple-rtkit.ko
kernel/drivers/soc/apple/apple-rtkit-helper.ko
kernel/drivers/soc/apple/apple-sart.ko
kernel/drivers/iommu/apple-dart.ko
```

and no `.ko` file exists for any of them anywhere under
`/lib/modules/7.1.13-3-1-ARCH/kernel`. The whole Apple storage stack is
compiled into the kernel image. An initramfs cannot be missing them, so
initramfs module pruning was never capable of causing the root-mount failure.
Effort spent building a "universal fallback initramfs" was chasing a non-cause.

`btrfs` is the opposite case: 0 hits in `modules.builtin`, so `btrfs.ko` *must*
be present in the initramfs. It is (see finding 2).

## Finding 2 — `esp-recovery.part` is correct

sha256 `762321515b7c644e88a4d6c8f32deae4507bf2e42fd32f32e32f08c41c4bd8b0`,
size 524,288,000 (exact multiple of 512).

`/grub-ane/grub.cfg`, menuentry 0:

```
search --no-floppy --file --set=root /grub-ane/VMLINUZ.REC
linux /grub-ane/VMLINUZ.REC root=UUID=725346d2-... rw rootflags=subvol=@ loglevel=7
initrd /grub-ane/INITRD.REC
```

Correct: it roots on the FAT ESP via a file search, and carries no `init=`
override.

- `VMLINUZ.REC` — 34,114,048 bytes, embedded version string
  `7.1.13-3-1-ARCH`. This is the kernel that boots fine on jw14m2 under
  macOS 27 firmware, so it is not exposed to the SError mismatch that
  killed 7.1.6.
- `INITRD.REC` — 24,929,281 bytes. Layout is uncompressed early-cpio
  (`TRAILER!!!` at 3106) followed by a gzip main archive at offset 10240,
  83,415,040 bytes uncompressed, 888 entries. Contents verified:
  - `/init -> usr/lib/systemd/systemd`, and `usr/lib/systemd/systemd` is
    really there (200,880 bytes).
  - `usr/lib/modules/7.1.13-3-1-ARCH/` — version **matches** the kernel.
  - `btrfs.ko` present (2,975,216 bytes) — required, per finding 1.
  - `fsck.btrfs` present.
  - `modules.dep.bin`, `modules.alias.bin`, `modules.symbols.bin`,
    `modules.builtin.bin`, `modules.builtin.alias.bin`, `modules.devname`,
    `modules.softdep` all present and sanely sized. mkinitcpio ships only the
    binary indexes, so the absence of plain-text `modules.dep` is expected and
    not a defect.

Builtin storage + `btrfs.ko` + systemd init + matching module version means
this initramfs is capable of mounting root.

## Finding 3 — `esp-final.part` is the actual cause of the last failure

sha256 `dc6f2f082b2d079fe13593f368e0a44b0efff0014f5fd311fcb630d5777aa9cd`,
size 524,287,992 — **not** a multiple of 512, which is precisely why `dd`ing it
fails `EINVAL` on the tail write and leaves a partial image behind.

Its menuentry 0 is the broken original:

```
search --no-floppy --fs-uuid --set=root 725346d2-f127-47bc-b464-9dd46155e8d6
linux /grub-ane/VMLINUZ.REC ... init=/grub-ane/REPAIR.SH
```

`search --fs-uuid` selects the **btrfs** root partition, and then GRUB is asked
to load `/grub-ane/VMLINUZ.REC`, which lives on the **FAT ESP**. GRUB cannot
find it, `linux` never completes, and the subsequent `initrd` reports *"you
need to load the kernel first"* — exactly the console error reported. This one
config explains the symptom completely.

It also pins `init=/grub-ane/REPAIR.SH`, which is a 0-byte file.

## Finding 4 — the self-repair mechanism never existed

In **both** images, `/grub-ane/LAPKG.TXZ` and `/grub-ane/REPAIR.SH` are
**0 bytes** (with garbage FAT timestamps, `2095-05-28` and `1981-12-05`). The
plan to have the initramfs self-install a kernel module package and run
`depmod` was never actually staged. Given finding 1 it is also unnecessary:
nothing needs installing. With the corrected `grub.cfg` there is no `init=`
override, so neither file is referenced and both are harmless dead weight.

## Finding 5 — GRUB capability audit

`/EFI/BOOT/BOOTAA64.EFI`, 913,408 bytes, byte-size-identical to
`GRUBANE2.EFI`. GRUB `2.14-1.1`, embedded prefix `(hd0,gpt4)/grub-ane`.

This matters because `/grub-ane/arm64-efi/` **is completely empty** — GRUB has
zero loadable modules on this ESP, so every command must be compiled into the
EFI binary or it does not exist.

Confirmed built in: `search_fs_file` (so `search --file` genuinely works),
`search_fs_uuid`, `search_label`, `part_gpt`, `btrfs`, `gzio`, `normal`,
`linux`, `configfile`, `echo`, `test`. FAT support confirmed by symbol
presence: `grub_fat_mount`, `grub_fat_open`, `grub_fat_dir`, `grub_fat_read`,
`grub_fat_uuid`, `grub_fat_label` — it has to be, or GRUB could not read its
own config off the ESP.

One blemish: `loadenv` is **not** built in, yet line 1 of
`esp-recovery.part`'s `grub.cfg` is `load_env`. GRUB prints
``error: can't find command `load_env'`` and continues parsing, so the
menuentries still register. Non-fatal, but it should be dropped so nobody
burns time debugging a phantom error on the console.

## Operational lesson

Three separate remote fix attempts were driven by unverified hypotheses, and
two of them wrote an image whose size was not a multiple of the block
size. On this raw device the observed behavior was a short write: dd exited 1
with EINVAL on the final partial block after writing most of the image,
leaving the ESP a partial overwrite of the good image by the stale one
(verified live 2026-09-19 16:21: on-device digest `7a786f85ccfd8c4f…` equals
the failed write's read-back). That is the observed behavior of one
device/dd/final-block combination, not a universal law — alignment handling
of a trailing partial block is device- and driver-dependent. The policy rule
is unchanged and general: never write an ESP image whose size is not an
exact multiple of the sector size, and always verify by read-back digest.

Rules this supports:
- Never write an ESP image whose size is not an exact multiple of 512.
- Always read the region back and compare sha256 to the source image.
- Always verify image **content** — grub.cfg text, kernel version string,
  initramfs module-tree version, presence of the non-builtin filesystem
  driver — before a reboot, not just the transfer.
- Check `modules.builtin` before concluding a driver is "missing from the
  initramfs".
- Audit the GRUB EFI binary's built-in module list whenever `arm64-efi/` is
  empty, because `insmod` is a no-op there and any command you rely on must
  already be inside the binary.
