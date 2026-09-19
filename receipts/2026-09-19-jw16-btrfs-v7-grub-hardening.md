# 2026-09-19 — jw16 btrfs-v7/GRUB boot-mine: risk verdict + ESP hardening (no reboot)

Host: `16m1mbp` (jw16 / `jw16mbp1-linux`, kernel `7.1.6-1-1-ARCH`, up since
2026-09-17 04:46:44 — box was NOT rebooted at any point in this work).

## Verdict (tested at three layers, not guessed)

**The jwm1-class mine is ABSENT from jw16's boot path, and jw16's btrfs
metadata is classic-layout, read byte-exact by the booted GRUB.**

1. **Item layer** (raw tree walk, `tools/btrfs-raw.py` over ssh+rd.py against
   `/dev/nvme0n1p6`): every sampled inode item at the classic key
   `(ino,0x01,0)` is a classic 160 B inode with `size@16` equal to the
   kernel-mounted size; zero shadow/tombstone items in `/@`, `/@log`, `/@pkg`
   sampled paths (incl. write-active `pacman.log`, journal, pkg rewrites).
   `/@/boot` itself is EMPTY (ino 263, no dir entries) — jw16 keeps kernel +
   initramfs on the ext4 `/boot` partition, so GRUB has nothing to truncate.

   | path | inode `size@16` | kernel `stat` | GRUB `cmp` |
   |---|---|---|---|
   | `/@/usr/share/grub/unicode.pf2` | 2,412,513 | 2,412,513 | rc=0 |
   | `/@/usr/bin/bash` | 1,194,408 | 1,194,408 | rc=0 |
   | `/@/etc/os-release` | 371 | 371 | — |
   | `/@/etc/passwd` | 1,745 | 1,745 | — |
   | `/@/boot/{vmlinuz,initramfs}` | ENOENT | ENOENT (ext4-resident) | ls: empty |

   Method note: `size@0` of a classic inode item is `generation/transid`, NOT
   the size (classic layout: generation@0, transid@8, **size@16**). An interim
   census that compared `size@0` vs `size@16` and labeled mismatches
   "TRUNCATED" was wrong; kernel `stat` + GRUB `cmp` overturned it. On jwm1's
   variant the size DID live at @0 (hence the jwm1 receipt's "+16 shift"
   wording) — the two fs variants are distinguishable exactly there.
2. **GRUB-binary layer** (`grub-fstest` from the installed `grub 2:2.14-1.1`
   — the same package jw16 boots): `cmp` byte-exact for the 2.4 MB btrfs font
   and the 1.2 MB btrfs `bash`; `ls /@/boot/` returns empty (rc=0); negative
   control (wrong local file) fails rc=1 as designed; ext4 vmlinuz rc=0;
   ESP FAT vmlinuz + 16.8 MB initramfs rc=0.
3. **System layer** (boot-chain audit): `EFI/BOOT/BOOTAA64.EFI` = stock m1n1
   stage-1 (217,088 B, ESP gpt4) → `/m1n1/boot.bin` (m1n1+U-Boot) → GRUB
   (`LoaderInfo` efivar = "GRUB 2.14"; `core.efi` + `arm64-efi` modules +
   `grub.cfg` all on ext4 gpt5 `/boot/grub`) → `vmlinuz-linux-asahi` +
   `initramfs-linux-asahi.img` from ext4 → kernel mounts btrfs `subvol=@`.
   The btrfs is never read pre-kernel in practice: the 00_header font
   fallback (`/@/usr/share/grub/unicode.pf2`) is inert
   (`feature_default_font_path` set; `/boot/grub/fonts/unicode.pf2` present
   on ext4), and harmless even if read (loadfont failure = console font only).

Superblock: `incompat_flags 0x371` (MIXED_BACKREF | COMPRESS_ZSTD |
BIG_METADATA | EXTENDED_IREF | SKINNY_METADATA | NO_HOLES) — all
classic-era, all supported by this GRUB; nothing v7-flagged.

## Residual risk (real, not on today's boot path)

- **GRUBANE family**: jwm1's `GRUBANE.EFI`/`GRUBANE2.EFI` (md5
  `111574c42cd2998a5deb88de60b3b183` / `2274e9d3a83b93968fbd61307c884353`)
  both stamp version `2:2.14-1.1` yet failed on jwm1's v7-variant fs — the
  version string proves nothing. Never install that family on a box whose
  boot files live on btrfs (fleet rule `.omp/rules/btrfs-v7-grub-reboot-gate.md`).
- **Layout drift**: jw16's /@ must not gain boot files. If the ext4 /boot is
  ever merged into btrfs, the mine re-arms on any pre-v7 GRUB build.
- Repo grub: `pacman -Si grub` = `2:2.14-1.1` aarch64 = the installed,
  fstest-verified build; there is no newer "v7-capable" package to install,
  and none is needed for this layout.
- jwm1's fs variant is not re-derivable offline (its 1 GB `fakedev.img`
  lacks the FS-tree chunks; FS tree root sits at logical `0x247d80c000`).

## Changes applied (native, live box)

1. **ESP-resident rescue pair** (ESP `/dev/nvme0n1p4` → `/boot/efi/grub-ane/`,
   368 M free before write):
   - `vmlinuz-linux-asahi` sha256 `ee36d989d62f2dd498b818e15c2044350c79d814a2017ffca61fdc2ad1aa95b6`
     (identical to jwm1's recovered kernel — same fleet image),
   - `initramfs-linux-asahi.img` sha256 `2336c312b4719da2b02b527813aa31c4897929707cb80a4442aeb0d734b3c789`,
   both byte-identical to `/boot` copies (sha256 matched both sides).
2. **`/etc/grub.d/40_custom`** (native, survives `grub-mkconfig`): dated
   comment + menuentry id `rescue-esp` "Omarchy Linux rescue (kernel+initrd
   from ESP FAT)" — `insmod fat`, `search --fs-uuid 4F4D-5801` (the ESP),
   `linux /grub-ane/vmlinuz-linux-asahi root=UUID=4f4d5801-524f-4f54-8000-000000000001 rw rootflags=subvol=@ …` (live cmdline, loglevel=7),
   `initrd /grub-ane/initramfs-linux-asahi.img`. Entry 0 remains the stock
   ext4-path "Omarchy Linux" (it is GRUB-safe today; flipping the default to
   the rescue copy would boot a stale kernel silently after future updates).
   The jwm1-style ANE-test entry (`devicetree /@/boot/ane.dtb`) was
   deliberately not created — jw16 had none; if ANE work needs one, its
   devicetree/kernel paths must point at ext4 or ESP, never `/@/boot`.
3. **`grub-mkconfig -o /boot/grub/grub.cfg`** rc=0; `grub-script-check`
   SYNTAX_OK; 9 template blocks, single rescue entry. Backups:
   `/etc/grub.d/40_custom.pre-ane-20260919`,
   `/boot/grub/grub.cfg.pre-ane-20260919` (backups chmod 644 — the first
   regeneration executed the executable backup as a template and emitted a
   duplicate block; second regeneration is clean).
4. **Fleet rule** landed: `.omp/rules/btrfs-v7-grub-reboot-gate.md`
   (gate: boot files off-btrfs OR fstest-verified booted GRUB; ESP rescue
   pair refresh after every kernel update; GRUBANE ban on btrfs-boot boxes).
   Untracked by design — `.omp/` is gitignored; no rule file is tracked in
   this repo (convention).

## Tooling note

`tools/btrfs-raw.py` `inode()` reads size@`0` — correct on jwm1's v7
variant, wrong (returns generation/transid) on classic-layout fs like jw16's.
Fix lane when picked up: derive size from the extent list max-end, or probe
size@0 vs size@16 against a kernel `stat`. Not patched in this pass so
jwm1-side (Jwm1BootFix) reads stay stable.

## Receipts

- `uptime -s` = 2026-09-17 04:46:44 before and after (no reboot).
- fstest matrix + census numbers above are command outputs from this session.
- Rule: `.omp/rules/btrfs-v7-grub-reboot-gate.md` (landed untracked;
  `.omp/` is gitignored per repo convention).
