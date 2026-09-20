# 2026-09-19 — jwm1 ESP recovery, second pass: live audit, minimal fix, bounded reboot (outcome: dark, console needed)

## Context

Prior claims equated a static image audit with a working boot. This pass
re-derived everything from live device bytes on jwm1's macOS side
(`jw-m1-macos`, 100.67.134.6, macOS 27.0), fixed the ESP with two minimal
file edits, performed ONE authorized reboot, and preserved exact evidence
when the box came up dark. jwm1 is now remotely invisible on both
identities; kernel-start status is UNKNOWN, not confirmed-dead.

## What the live ESP actually was (fresh read 16:21 CDT, sha256
`7a786f85ccfd8c4f0c4bdbcec807b4a5476c35e094615668f3327596d370f2bf`)

Partial overwrite: the earlier failed `dd` of stale `esp-final.part`
(unaligned 524,287,992 B, EINVAL short write) left most of the stale
image's content over the good image. From live bytes:

- `/grub-ane/grub.cfg` (745 B, sha `c0a37a95…`) — THE boot blocker. Entry 0:
  `search --no-floppy --fs-uuid --set=root 725346d2-…` (selects the **btrfs**
  root FS), then `linux /grub-ane/VMLINUZ.REC` — which lives on the **FAT
  ESP**, so GRUB cannot find it → "you need to load the kernel first" — plus
  `init=/grub-ane/REPAIR.SH` (a 0-byte file).
- `/grub-ane/VMLINUZ.REC` — GOOD: 34,114,048 B, sha `e10c2a5c…`, banner
  `7.1.13-3-1-ARCH`, embedded IKCFG: CONFIG_NVME_APPLE/SART/RTKIT/MAILBOX/
  DART/PCIE_APPLE all `=y`.
- `/grub-ane/INITRD.REC` — WRONG BUILD: 24,929,986 B **zstd** (sha
  `25721264…`), unknown provenance (the stale image's payload). Structurally
  valid (btrfs.ko present, vermagic matches, /init→systemd) but not the
  verified build.
- `/EFI/BOOT/BOOTAA64.EFI` — GOOD: 913,408 B, sha `0fe0f353…` (unchanged;
  search_fs_file, linux, gzio, btrfs, part_gpt built in; `loadenv` NOT built
  in).

Boot selection (read, not assumed): `bless --info --getBoot` →
`/dev/disk2s2`; `nvram boot-volume` → preboot
`7A64DCB3-EA6C-4456-97E5-9347BCD9C152`; the "Asahi Alarm Minimal (BTRFS)"
volume group (disk0s3 container, Preboot disk2s3 193 MB = m1n1 payload);
`boot-command=fsboot`, `auto-boot=true`. Persistent default = the **Linux
boot object**. btrfs fsid re-read live from `/dev/rdisk0s5` superblock:
`725346d2-f127-47bc-b464-9dd46155e8d6`, label `asahi-root`,
`num_devices=1` — matches `root=UUID=` in the config.

## Fix applied (minimal file edits through a mounted FAT; no image rewrite)

1. Backed up live files to Mac `/tmp/esp-backup-20260919-1621/` (digests
   recorded) and saved the full broken-state image locally + off-box.
2. `/grub-ane/grub.cfg` ← 335 B, sha `56f08c8a46b4cc99e15809eef3845722143a879d5893cf9a99c9a7e231722438`:
   verified `esp-recovery.part` config MINUS the `load_env` line (module not
   built into BOOTAA64.EFI; phantom console error) MINUS the entry-1
   `/@/boot` btrfs-path fossil (the v7 truncated-inode landmine; per
   btrfs-v7-grub-reboot-gate). Entry 0:
   `search --no-floppy --file --set=root /grub-ane/VMLINUZ.REC` /
   `linux /grub-ane/VMLINUZ.REC root=UUID=725346d2-… rw rootflags=subvol=@ loglevel=7` /
   `initrd /grub-ane/INITRD.REC`. NO `init=`, NO netconsole.
3. `/grub-ane/INITRD.REC` ← verified gzip build, 24,929,281 B, sha
   `23739973ebd799a8d95bc4319c51db82b4bdebf278b5719327db0c2cec9dbc11`
   (early cpio + gzip main 83,415,040 B, 888 entries, btrfs.ko vermagic
   `7.1.13-3-1-ARCH`, /init→usr/lib/systemd/systemd).
4. Post-write full-device read (16:33): sha
   `e8f3cd801c9cc0508e2cf64a1b522d315c92dbfa0af049f6ff086c5458d3740d`;
   audit 16 PASS / 0 FAIL / 1 UNKNOWN (auditor parser only models
   `--fs-uuid`; `--file` form closed manually: module built in, target file
   exists exact-case).
5. Off-box backups on jw14m2 `/var/tmp/jwm1-esp-backups/` (digests verified):
   `esp-live-1621.img` (broken state), `esp-live-1634.img` (fixed state),
   `initrd-verified.rec`, `grub-final.cfg`.

## Disqualifications recorded this pass

- `esp-netconsole.part` (`9f4f2489…`): **NOT QUALIFIED, not flashed** — its
  receipt is corrected; see `2026-09-19-jwm1-netconsole-image.md`. Wi-Fi
  cannot associate pre-userspace, no wpa_supplicant/brcmfmac firmware in the
  initramfs, no `ip=`, netconsole does not retry, and both netconsole syntax
  variants produced today are malformed (one uses the collector IP as the
  source; the same broken line also ships in the initramfs
  `/etc/modprobe.d/netconsole.conf`).
- `esp-final-verified.part` (`600cdd58…`): **disqualified as write source** —
  same mangled netconsole parameter in its grub.cfg despite the name.
- Forensic receipt corrected: "unaligned size means the write could never
  complete even in principle" was overbroad; on this raw device the observed
  behavior was a short write (EINVAL on the final partial block). Policy rule
  (exact multiple of sector size + read-back digest) unchanged.

## Reboot attempt (single, bounded, per authorization)

- `shutdown -r now` issued 21:39:27 UTC (16:39:27 CDT) via macOS SSH;
  connection dropped normally.
- 21:40:00 UTC: macOS identity JW-M1 left the tailnet (shutdown drop — the
  persistent boot object is the Linux chain, no macOS fallback expected).
- Bounded poll to 21:47:40 UTC (~8 min): `jwm1-linux` Online=False,
  lastSeen frozen 2026-09-17T22:56:22Z; JW-M1 remained dark.
- LAN evidence via jw14m2-linux (192.168.3.103, same subnet, read-only):
  ping 192.168.3.108 (recent macOS lease) and 192.168.3.66 (historical):
  100% loss; ARP holds only a STALE entry `ce:0f:2d:6e:a4:10` at 3.108 (no
  fresh confirmation); TCP/22 → "No route to host" (ARP resolution failing =
  nothing answering); mDNS dead; `tailscale ping 100.84.184.102` (DERP):
  timed out. No fresh neighbor entries anywhere on the segment.

## Outcome: NOT recovered-and-verified. Remote state: invisible, kernel-start UNKNOWN

The machine is absent from both tailnet identities AND from the LAN at layer
2. Remotely indistinguishable between: (a) dark at m1n1/U-Boot/GRUB, (b) early
kernel panic, (c) kernel reached userspace into emergency mode with no
network. Absence from the tailnet alone does NOT establish kernel failure.

## Exact evidence needed: ONE console observation

The literal screen content at the next power-on decides the next move:

- GRUB menu / GRUB error text → which entry, which error line.
- Kernel panic text (SError family?) → capture first lines.
- `emergency mode` / systemd failure banner → the failed unit is named on
  screen; that unit name is the fix target.
- Nothing at all → m1n1/U-Boot level; compare boot object payload with a
  known-good jw14m2/jw16 boot object.

## Post-reboot user observation (21:50 UTC) — HARD HOLD in effect

USER reports jwm1 **stuck at the Asahi boot screen** and says it was broken
again. No further boot changes, reboots, or writes on jwm1 until screen
evidence (photo) identifies the stage. This recovery is reported as FAILED,
not successful.

Stage key for the photo — **the logo alone cannot locate the failure stage**:
the boot splash is persistent, so a later-stage hang can still show the
logo/splash, and GRUB clears the screen only when it draws. Treat screen
content as a hint, not a stage locator; the photo's text (error lines,
menus, panic text) is what discriminates:

| Screen shows | Stage hint | Caveat |
|---|---|---|
| Apple logo, progress bar stalled | iBoot → boot-object handoff, OR later stage with persistent splash | logo alone is not diagnostic |
| Brief U-Boot text / silent hang after logo | U-Boot stage | — |
| GRUB menu visible or GRUB error line | config/loader stage | error text is decisive |
| Black screen after GRUB clears | kernel started, silent early hang/panic (7.1.13-3 on T8103 has never completed a boot on this box) | display persistence could also mask later stages |
| emergency mode banner | userspace reached; named unit on screen is the fix target | — |

No categorical claim is made that the ESP edits could not cause the
observed hang: the pre-reboot ESP state is preserved byte-for-byte
(`esp-live-1634.img`, sha `e8f3cd80…`) precisely so any stage can be
matched against exactly what the box was given, and the difference between
the attempted state and the last-known-working state is enumerated in this
receipt.

No further remote action is useful or authorized: no repeat reboots (none
possible anyway), netconsole remains unqualified, and every artifact needed
to reason further is preserved (Mac `/tmp/esp-backup-20260919-1621/`,
jw14m2 `/var/tmp/jwm1-esp-backups/`, workspace `esp-audit-20260919/`).

## Read-only reconnect (16:56 CDT) — comparison + concrete mechanism

User returned jwm1 to macOS (one-time picker choice — `bless --getBoot` is
now `/dev/disk3s2`, the same Linux boot object renumbered; the persistent
default is UNCHANGED, so a plain reboot retries Linux). ESP digest re-read
UNCHANGED: `e8f3cd80…` (user's flip did not touch it). Boot object payload
vintage: Aug 24 14:04–14:30 ALARM install (Restore/ + boot/active,
Preboot 7A64DCB3…); proven with 7.1.6 daily through Sep 17 22:56 — i.e.
AFTER the Sep 3 macOS 27 update, so current firmware is proven with the
7.1.6 kernel on this exact boot object.

**Concrete mechanism found (not speculation):** `CONFIG_BRCMFMAC=m` in BOTH
kernels' embedded configs (extracted from the images this session), and the
entire Wi-Fi stack modular (brcmfmac/brcmutil/cfg80211/mac80211 all `=m`;
USB ethernet `=m`). jwm1's root has ONLY 7.1.6-1-1-ARCH modules. Therefore
the attempted 7.1.13 boot could never produce a reachable system: even a
fully successful boot reaches userspace with no brcmfmac.ko for 7.1.13 → no
Wi-Fi → no LAN → no tailscale → invisible. "Booted but unreachable" is an
evidence-backed outcome, not proof of an early hang.

### Comparison: attempted fleet pair vs last-known-consistent pair

| | Attempted (fleet) | Last-known-consistent (esp.new, a0e10002…) |
|---|---|---|
| kernel | 7.1.13-3-1-ARCH `e10c2a5c…` 34,114,048 B | 7.1.6-1-1-ARCH `ee36d989…` 33,917,440 B |
| initramfs | `23739973…` gzip 24,929,281 B, btrfs.ko vermagic 7.1.13 | `de4ae604…` gzip 19,414,040 B, btrfs.ko vermagic 7.1.6 |
| root /lib/modules | only 7.1.6 → **mismatch** | 7.1.6 → **match** |
| root pacman db | linux-asahi 7.1.6 → mismatch | match |
| Wi-Fi (BRCMFMAC=m) | no 7.1.13 brcmfmac.ko in root → **never reachable** | 7.1.6 brcmfmac.ko present in root → works |
| proven on T8103 + this boot object + current firmware | never reached kernel start | yes, daily through Sep 17 22:56 |

### PROPOSED minimal repair (sent for review — NO writes made)

1. ESP `/grub-ane/`: replace VMLINUZ.REC ← 7.1.6 kernel and INITRD.REC ←
   7.1.6 initramfs (both digest-verified extractions from `esp.new`
   `a0e10002…`, itself verified by full read-back at 02:03 per the bootloop
   receipt). Two `cp`s through the mounted FAT, identical mechanism to the
   16:32 fix.
2. grub.cfg UNCHANGED (`56f08c8a…` — correct `search --file` form, no
   `init=`, no netconsole; the first correct config this ESP has had).
   BOOTAA64.EFI unchanged (`0fe0f353…`, audited).
3. Authorized reboot (plain — persistent default already the Linux chain).
4. Verify: `uname -r` = 7.1.6-1-1-ARCH; `/` = btrfs subvol @; brcmfmac
   loaded + wlan0 leased; tailscaled active; `systemctl --failed` empty;
   ANE stack status (7.1.6 modules match root).
5. Phase 2 (separate review, only after reachable Linux): make root
   self-consistent with 7.1.13 (pacman -U linux-asahi 7.1.13, mkinitcpio,
   then re-stage the ESP pair) — until then 7.1.6 is the only kernel whose
   userland, modules, and pacman db all match root.
6. Rollback: attempted pair digests recorded (`e10c2a5c…` / `23739973…`);
   full images of both states preserved locally and on jw14m2.

## 17:00 CDT — AUTHORIZED STAGING COMPLETE (two-file replacement, no reboot)

Main authorized exactly the two ESP file replacements. Executed and verified:

- Written: `/grub-ane/VMLINUZ.REC` ← 7.1.6 kernel, 33,917,440 B, sha256
  `ee36d989d62f2dd498b818e15c2044350c79d814a2017ffca61fdc2ad1aa95b6`;
  `/grub-ane/INITRD.REC` ← 7.1.6 initramfs, 19,414,040 B, sha256
  `de4ae60473443e2b2184dce8b73be270ded13f21b704f7d568145bbb000d650c`.
- Unchanged (readback verified): grub.cfg `56f08c8a…`, BOOTAA64.EFI
  `0fe0f353…`. Previous pair backed up on Mac
  `/tmp/esp-backup-20260919-7113-pair/` (digests match the 16:33 state).
- Fresh full-device readback 17:01: 524,288,000 B, sha256
  `cbf538412648367930fa6dda85d8c789255025d1e7f504be420a6a0866501a30`;
  audit with `--expect-version 7.1.6-1-1-ARCH`: 16 PASS / 0 FAIL / 1
  UNKNOWN (same auditor parser gap on `--file` search; module search built
  into BOOTAA64.EFI, target file exists exact-case). Off-box copy verified
  on jw14m2 (`esp-live-1701.img`, digest match).
- Initramfs metadata, parsed from the fresh image: `/init` mode 100755,
  3,325 B, `#!/usr/bin/ash` mkinitcpio script (an earlier NUL-prefix read
  was this lane's own parse artifact — name-padding not applied; corrected
  parse shows a clean shebang). `btrfs.ko` 2,973,032 B, vermagic
  `7.1.6-1-1-ARCH SMP preempt mod_unload aarch64`, `depends=raid6_pq,xor`;
  both dependency modules physically present
  (`kernel/lib/raid6/raid6_pq.ko`, `kernel/lib/raid/xor/xor.ko`); index
  files present (`modules.dep.bin`, `modules.alias.bin`,
  `modules.builtin.bin`, `modules.softdep`, `modules.devname`; plain-text
  `modules.dep`/`modules.builtin` absent — normal for mkinitcpio, kmod uses
  the binary indexes). Initramfs module tree: 205 `.ko`, all under
  `7.1.6-1-1-ARCH`.
- Storage config: 7.1.6 embedded config (extracted from the staged kernel)
  reads CONFIG_NVME_APPLE=y, CONFIG_APPLE_SART=y, CONFIG_APPLE_RTKIT=y,
  CONFIG_APPLE_MAILBOX=y, CONFIG_APPLE_DART=y, CONFIG_PCIE_APPLE=y — the
  whole Apple storage path is builtin, so the initramfs needs no storage
  `.ko` and has none missing; btrfs is `=m` and its module is in the
  initramfs with matching vermagic.
- Root: `/dev/rdisk0s5`, label `asahi-root`, fsid
  `725346d2-f127-47bc-b464-9dd46155e8d6` (re-read live at staging time),
  `num_devices=1`, subvol `@` — matches `root=UUID=… rootflags=subvol=@`.
- Current boot entry (menuentry 0, default): `search --no-floppy --file
  --set=root /grub-ane/VMLINUZ.REC` → `linux /grub-ane/VMLINUZ.REC
  root=UUID=725346d2-f127-47bc-b464-9dd46155e8d6 rw rootflags=subvol=@
  loglevel=7` → `initrd /grub-ane/INITRD.REC`. timeout=10, default=0, no
  `init=`, no netconsole.

Honest caveat per Main: the module/pacman mismatch is a PROVEN defect that
made the 7.1.13 attempt unreachable-by-construction; this staging removes
that defect and uses the only pair ever proven end-to-end on this hardware,
boot object, and firmware — it is NOT a guarantee that the next boot is
reachable (the unexplained 21:39 hang stage remains unidentified, and the
screen photo is still the discriminating evidence).

## 17:13 CDT — AUTHORIZED ROLLBACK BOOT: FAILED (user reports stuck at logo)

Main authorized one bounded rollback boot with diagnostic args. Exact facts:

1. Diagnostic grub.cfg staged 22:06–22:07 UTC: 389 B, sha256
   `2033bf407a0765e357ef6cc130e3ff4b7f6c5b629ee578705dcb45dd7a2c13eb` —
   identical to the verified config except the linux line gained
   `plymouth.enable=0 rd.plymouth=0 systemd.show_status=1` (loglevel=7,
   UUID, subvol=@ preserved; no quiet/splash; no init=). Mount readback
   digest match; pre-change grub.cfg backed up on Mac
   `/tmp/esp-backup-20260919-grubcfg-pre-diag/`.
2. Fresh full-device readback (`esp-live-1706.img`): 524,288,000 B, sha256
   `70287ab78a220deab0962cf1bf84009deef20a7e949005ac2ce9409334067498`; all
   four files re-verified from device bytes: grub.cfg 389 B MATCH, kernel
   `ee36d989…` 33,917,440 B MATCH, initramfs `de4ae604…` 19,414,040 B
   MATCH, BOOTAA64 `0fe0f353…` MATCH.
3. Single reboot issued 22:13:04 UTC (17:13 CDT); ssh dropped normally.
4. Bounded poll: jwm1-linux never online (lastSeen frozen 2026-09-17T22:56Z
   through poll cutoff); JW-M1 macOS dark after 22:10 UTC shutdown drop.
   Polls cancelled at Main's hold.
5. USER reports the box stuck AGAIN at the Asahi logo; user pressed Esc once
   to try to expose Plymouth text; photo awaited.

Main has ordered: NO more boot-file changes or reboots unless the user
explicitly approves another attempt; hold even if macOS reconnects; no
reboot-on-reconnect; wait for console evidence. This supersedes the
autonomous-host rule for this recovery.

Observation for the record (no categorical claim): the 21:39 attempt
(7.1.13 pair) and the 22:13 rollback (7.1.6 pair) used different kernels,
different initramfs builds, and verified-identical boot object and GRUB
binary — both produced the same user-visible stuck-at-logo outcome. That
pattern is consistent with a stage at or before the bootloader handoff or
with splash/display persistence masking later stages; only the console
photo (Esc text output, GRUB menu, error lines, panic text, emergency
banner, or a truly static logo) can discriminate. Static analysis is
exhausted; every ESP state handed to the box is preserved byte-for-byte
(esp-live-1621 broken, esp-live-1634 7.1.13+clean-cfg, esp-live-1701
7.1.6 pair, esp-live-1706 7.1.6+diag-args) with fresh-device digests.

## 17:2x CDT — BOOT-CHAIN FORENSICS (read-only) + CHRONOLOGY CORRECTION

Correction (Main-directed, and correct): an earlier claim of mine — "GRUB
provably executed at 14:01" — was WRONG. The visible "you need to load the
kernel first" console errors were reported BEFORE 13:41 (they motivated the
13:30 fix), i.e. on a pre-13:30 ESP state whose loader was most plausibly
the Aug-24-original binary `9d6e7510…` (staged into esp.new at 02:00). The
14:01 boot (state `7a786f85`, loader `0fe0f353`) has NO console observation
at all. Score table, source-backed: loader `0fe0f353` = 2 boots, 2
logo-hangs, zero observed output; loader `9d6e7510` = observed GRUB console
output (the errors) and historical boots through Sep 17.

### /ubootefi.var decoded (U-Boot persistent EFI var store, 728 B)

- Boot0000 "hnvme 0" → NVMe namespace node **nsid=1** (hosts the ESP,
  partition 4 EFI-ASAHI); Boot0001 "hnvme 1" → **nsid=2**; Boot0002
  "hnvme 2" → **nsid=3**. None contain an explicit file-path node.
- **BootOrder = [Boot0001, Boot0002]** — namespaces WITHOUT the ESP.
  Configured selection therefore cannot directly load; execution proceeds
  only via U-Boot's fallback EFI scan appending `\EFI\BOOT\BOOTAA64.EFI`
  (UEFI removable/fallback behavior; exact U-Boot code path citation
  pending if required). GRUBANE.EFI / GRUBANE2.EFI / BOOTAA64.EFI.stock on
  the ESP are referenced by NO Boot entry — configured-vs-executed
  distinction recorded; fallback reachability is inferred, not proven.
- ESP inventory surprise: /EFI/BOOT holds FOUR binaries (BOOTAA64.EFI
  `0fe0f353`, GRUBANE.EFI `4571f270` 909,312 B, GRUBANE2.EFI `6dfe7475`
  913,408 B — DIFFERENT digest from BOOTAA64 despite equal size — and
  `BOOTAA64.EFI.stock` **405,504 B**), plus /M1N1/BOOT.BIN `07009e0b…`
  with a `boot.bin.stock-20260906` backup `3945ed51…`, /VENDORFW, /ASAHI.
- Capability scan: `9d6e7510` and `0fe0f353` carry the same module-name
  string set (fat, search_fs_file/fs_uuid/label, linux, gzio, btrfs,
  part_gpt, configfile, normal, gfxterm, devicetree, …) — capability
  parity; builds still differ.
- Stage1 binding: Preboot boot/71AB6A44… (the `active` payload) is the
  Aug-24 stub boot chain (iBoot.img4 + base-system + FUD trustcaches);
  Restore/Firmware holds Apple device firmware, no m1n1 named file; ESP
  /M1N1/BOOT.BIN is staging material with no Boot#### reference — live
  m1n1 binding UNVERIFIED (Preboot chain untouched since Aug 24 and
  historically functional).

### Evidenced-cause change staged (single variable)

The only pre-kernel construct that reads btrfs directories is
`search --file` (14:01-era config used `--fs-uuid`, superblock-only, and
GRUB output was visible). GRUB's documented failure class on this box is
the v7 btrfs layout. New grub.cfg staged 17:12 UTC: identical to the
diagnostic config except `search --no-floppy --fs-uuid --set=root
6C79-DC47` (the ESP's own FAT UUID, read from live BPB) replaces the
`--file` search — no btrfs directory walk pre-kernel. 380 B, sha256
`0899770c9ac6f03beb26c93deca7aef626dd0bda0335a7b5587aa61d065bba54`;
fresh full-device readback `esp-live-1712.img` 524,288,000 B sha256
`4a44a6e9a82b3f7ed71a6a644f8556b59f766b8d3455870e46e5d14c55b09cff`; all
four files re-verified from device bytes. Prior cfg backed up on Mac.
If the next authorized boot still hangs pre-menu, the next single-variable
change is BOOTAA64.EFI ← `9d6e7510` (the only loader with observed output
on this box), cfg already compatible with its module set.

## 17:3x CDT — STAGE1→BOOT.BIN BINDING CLOSED; SOURCE-ANCHORED FALLBACK

- Live m1n1 stage2 identified: Preboot
  `boot/71AB6A44…/System/Library/Caches/com.apple.kernelcaches/kernelcache.custom.336646078F…`
  (1,051,585 B, Aug 24 14:33; strings: `m1n1_stage2.log`, "failed to
  allocate m1n1 log buffer", `asahi,kblang-code`) — m1n1 stage2. Its
  payload: **ESP `/M1N1/BOOT.BIN`** (6,092,721 B, mtime **Sep 6 19:45**,
  sha `07009e0b…`; strings include `m1n1 custom logo payload`,
  `m1n1 initramfs payload`, no U-Boot banner — asahi builds hide it).
- Provenance: `BOOT.BIN` vs `boot.bin.stock-20260906` (6,090,601 B) differ
  from byte 0 with ~1.25 M differing bytes in the common range and
  different tails = **full rebuild of m1n1+U-Boot+dtbs, staged Sep 6
  19:45**, NOT a patch. It is the live payload and is PROVEN: Linux booted
  Sep 17 22:56, after the Sep 6 update, on kernel 7.1.6.
- The static "Asahi logo" is drawn by this stage: m1n1 carries a **custom
  logo payload** and draws it across stage2/U-Boot; Esc produced no change
  (dead input or hang — stage NOT assignable from this).
- Fallback anchored in source: AsahiLinux/u-boot (asahi branch)
  `configs/apple_m1_defconfig`: `CONFIG_BOOTCOMMAND="bootflow scan -b"` —
  U-Boot runs bootflow scan over all bootdevs; the EFI bootmgr bootmeth
  fails on our unloadable BootOrder entries (nsid 2/3, no ESP, no file
  node), the scan continues and boots the first usable flow =
  `\EFI\BOOT\BOOTAA64.EFI` on the ESP → `0fe0f353`. Configured (BootOrder)
  ≠ executed (fallback scan); both recorded.

## 17:4x CDT — STAGE1 VARIABLE EXTRACTED; MARKED CONFIG STAGED

- m1n1 stage2 appended config extracted from
  `kernelcache.custom.336646078F…` (1,051,585 B, pulled read-only from the
  live Preboot): it carries
  `chainload=2dccadb2-c083-4c21-abae-5a29b442ea48;m1n1/boot.bin` and
  `chosen.asahi,efi-system-partition=2dccadb2-c083-4c21-abae-5a29b442ea48`.
- GPT mapping (live disk0 table): GUID `2dccadb2-c083-4c21-abae-5a29b442ea48`
  is the **EFI System Partition** (type C12A7328-F81F-11D2-BA4B-00A0C93EC93B,
  disk0s4, "EFI - ASAHI"). Binding therefore proven to partition GUID +
  path: stage2 chainloads `m1n1/boot.bin` = `/M1N1/BOOT.BIN` (case
  insensitive FAT) = the Sep 6 rebuild `07009e0b…`, proven by Sep 17 boots.
- Executed GRUB `0fe0f353` command strings: `terminal_output`, `echo`,
  `terminal`, `menuentry` all present — visible markers will print if the
  cfg executes. No `bootflow` string (irrelevant).
- Marked diagnostic cfg staged 17:43 UTC: 552 B, sha256
  `68930cc4862fa740ce6dad35622224417ea78882a85f2e897cbd1a2c15e08133` —
  adds `terminal_output console`, pre-search echo, post-search
  `echo root=$root`, pre-initrd echo. Prior cfg backed up on Mac
  `/tmp/esp-backup-20260919-grubcfg-pre-marked/`.
- Fresh full-device readback `esp-live-1743.img`: 524,288,000 B, sha256
  `0e4bab63ca55af60caa145faa040dd481102d28d41c63675dafebb50ad2803aa`; all
  four files re-verified from device bytes (cfg 552 MATCH, kernel
  `ee36d989…` MATCH, initramfs `de4ae604…` MATCH, BOOTAA64 `0fe0f353…`
  MATCH). No reboot performed — awaiting authorization.

Stage discrimination the next authorized boot provides:
- "GRUB cfg loaded: probing ESP 6C79-DC47" visible → cfg executes; later
  markers pinpoint the failing step (search / kernel / initrd).
- Nothing visible → hang before/at cfg execution inside the loader → next
  single-variable change: BOOTAA64.EFI ← `9d6e7510`.

## 22:42:46 UTC — AUTHORIZED DIAGNOSTIC BOOT: FAILED (no markers visible)

- Sync + unmount confirmed before reboot. Single diagnostic reboot issued
  **2026-09-19T22:42:46Z** (17:42:46 CDT) of the marked fs-uuid cfg + 7.1.6
  pair (state `0e4bab63…`, all four files device-verified pre-boot).
- USER OBSERVATION: static Asahi logo again; the cfg's visible markers did
  NOT appear. Retained uncertainty: markers absent = [loader-level hang
  before cfg execution] OR [cfg executed but console output not displayed];
  neither individually proven. Connectivity after: both identities offline
  (jwm1-linux lastSeen frozen 2026-09-17T22:56:22Z; JW-M1 dark since
  22:40:00Z shutdown drop). No further reboot.
- Loader score updated: `0fe0f353` = **3/3 boots, zero observed output**.
- PREPARED (staged on Mac /tmp + local + jw14m2, NOT written to ESP):
  restoration package `grub-9d6e7510.efi` (full sha
  `9d6e751045e794733a672db7f6acf73a2b137e6488653c5eba93d013c45a1065`,
  source `esp.new`), compatibility pre-checked against the staged marked
  cfg: contains terminal_output/echo/terminal/search/fs_uuid/menuentry/
  linux/initrd/gzio/btrfs/part_gpt strings; embedded prefix identical
  `(hd0,gpt4)/grub-ane` → routes to `/grub-ane/grub.cfg` (marked cfg,
  `68930cc4…`).
- Wording correction (Main): "Sep 6 mtime + Sep 17 boot" proves staging
  time only — NOT that hash `07009e0b…` was the live payload at the Sep 17
  boot, and mtime is not proof of no-modification. Digest `07009e0b…` was
  read from the live ESP today; identity with the Sep 17-era payload is
  not hash-proven.
- Attempt ledger corrected (Main-directed): loader `0fe0f353` boots, all
  with ZERO observed GRUB/console output — #0 ~14:0x UTC (state `7a786f85`,
  745 B broken cfg + 7.1.13-era pair) outcome UNOBSERVED (no console
  report; box dark; user power-cycled to macOS 15:07); #1 21:39:27 UTC
  (`e8f3cd80`, clean cfg + 7.1.13 pair) — user-observed static logo; #2
  22:13:04 UTC (7.1.6 pair + `56f08c8a` cfg) — user-observed static logo;
  #3 22:42:46 UTC (`0e4bab63`, marked fsuuid cfg + 7.1.6 pair) —
  user-observed static logo, no markers. Total 4 boots, 0 with observed
  GRUB output. Loader `9d6e7510`: observed GRUB console output on at least
  one pre-13:41 boot, plus at least one unobserved-dark boot (02:08 era).
  "Only remaining untested element" is RETRACTED — not proven; only
  "only loader with any observed output on this box".
- PLAN AWAITING COORDINATION: on macOS return — read-only verify first;
  swap BOOTAA64.EFI ← 9d6e7510 via mounted FAT (backup 0fe0f353 first);
  fresh full-device readback + digest verify; ONE reboot only on explicit
  approval. Every prior state remains preserved byte-for-byte.

## 17:51 CDT — AUTHORIZED ORIGINAL-LOADER RESTORATION STAGED (no reboot)

- macOS returned 22:50:30 UTC (17:50 CDT, load spike 144 from Spotlight,
  transient). Pre-restore fresh verify: ESP digest `0e4bab63…` (expected
  staged state intact); current loader `0fe0f353…` confirmed.
- First restore attempt aborted safely (`set -e`) — source file missing on
  the Mac (transfer oversight); NO ESP write occurred. Transferred,
  digest-verified, re-ran.
- Backup: current `0fe0f353` loader on Mac
  `/tmp/esp-backup-20260919-0fe0f353/`.
- Restored: `/EFI/BOOT/BOOTAA64.EFI` ← original `9d6e7510…` (913,408 B,
  Aug-24-era binary, the only loader with observed console output on this
  box). Unchanged: marked cfg `68930cc4…` (552 B), kernel `ee36d989…`
  (33,917,440 B), initramfs `de4ae604…` (19,414,040 B).
- Fresh full-device readback `esp-live-1753.img`: 524,288,000 B, sha256
  `f6f9ec5ae180ac0299de886d3277561b5350ee36d7ed3d46822322664f682b66`; all
  four files digest-matched from device bytes. Off-box archive updated on
  jw14m2 (digest match).
- Staged state summary: loader `9d6e7510` + marked fs-uuid cfg `68930cc4`
  + 7.1.6 pair. NO reboot — awaiting authorization.

## 22:53:13 UTC — AUTHORIZED BOOT OF RESTORED STATE: FAILED (same logo)

- Sync + unmount confirmed; boot issued 2026-09-19T22:53:13Z of verified
  state `f6f9ec5a…` (loader `9d6e7510` + marked cfg `68930cc4` + 7.1.6
  pair). USER OBSERVED: static Asahi logo again. Retry cycle stopped.
- Connectivity after: both identities offline (JW-M1 dark since
  22:50:00Z; jwm1-linux frozen at Sep 17).
- Elimination matrix after five boots:
  | Variable | States tested | Result |
  |---|---|---|
  | GRUB binary | `0fe0f353` ×3 boots; `9d6e7510` ×1 boot | both hang identically at logo |
  | kernel pair | 7.1.13 (`e10c2a5c`+`23739973`); 7.1.6 (`ee36d989`+`de4ae604`) | both hang |
  | cfg form | broken `--fs-uuid`+`init=`; clean `--file`; clean `--fs-uuid`; marked variants | all hang |
  | `/M1N1/BOOT.BIN` | byte-identical, contiguous, start cluster 34420 in current AND mtools-era | unchanged across all boots |
  | `/ubootefi.var` | byte-identical `a6e5ec85…` across 02:00-era, 13:30-era, current | unchanged |
- Consequence: the hang sits in a stage none of these touch — m1n1
  stage2/U-Boot runtime (bootflow scan, USB/ASMEDIA probe, display init)
  or an ESP-wide filesystem-state factor: every hanging boot's ESP carried
  macOS-msdos-written FAT metadata (16:32 CDT onward), while the last
  boot with observed GRUB console output ran an ESP written only by
  mtools-era tooling. That correlation is the top remaining lead.
- Recorded ambiguity: the pre-13:41 visible-error boot's loader is
  UNDETERMINED (candidate states carry `9d6e7510` or `0fe0f353`);
  consequently today's binary-swap test was under-determined and
  inconclusive rather than a clean discriminator.
- Proposed next change (requires coordination, not executed): construct a
  fully-mtools-native ESP state OFF-DEVICE from preserved images
  (mtools-written FAT metadata + proven BOOT.BIN placement, carrying the
  verified 7.1.6 pair + marked cfg) — the only remaining ESP-wide
  variable — then one coordinated boot.
- Preserved states on this workstation + jw14m2:/var/tmp/jwm1-esp-backups/:
  esp-live-1621 (broken), 1634 (7.1.13+clean cfg), 1701 (7.1.6 pair),
  1706 (7.1.6+diag args), 1712 (fsuuid cfg), 1743 (marked cfg,
  `0fe0f353`), 1753 (marked cfg, `9d6e7510`) — plus Mac /tmp backups and
  the restoration package.

## 23:53-55 UTC — BOUNDED WINDOW CLOSED; FSCK: NO FAT DEFECT EXISTS

- Full 10-minute poll (22:53→23:55:05... corrected: boot 23:44:32 UTC,
  window closed 23:55:05 UTC = 10m33s): **jwm1-linux never checked in.**
  Both identities offline throughout (JW-M1 dark since 23:40 shutdown
  drop). Boot outcome still PENDING console observation — the d1ee639c
  payload is the one that reached GRUB with visible output pre-13:30, so
  stage progress is plausible but unconfirmed.
- fsck-grade FAT consistency check (read-only, full-chain walk):
  - current ESP (esp-live-1848, d1ee restored): FAT1==FAT2 ✓; reachable
    clusters 46,473 + free-in-FAT 81,524 = 127,997 vs 128,000−2 reserved —
    EXACTLY consistent; all file/dir chains valid (the only flagged items
    are 0-length `.Spotlight-V100` files where cluster 0 is legal).
  - esp.new (02:00, mtools-era metadata): same result — 47,494 reachable +
    80,503 free = 127,997 — also fully consistent.
- CONSEQUENCE: **no FAT defect exists in the current ESP** — macOS-written
  metadata is as structurally sound as the mtools-era metadata, so the
  "FAT writer state" hypothesis is ELIMINATED as a defect (it remains only
  an unobservable era difference). The remaining stage-unknown for any
  frozen-logo boot now sits in m1n1 stage2→U-Boot→GRUB→kernel execution or
  display — i.e., requires console/USB-proxy observation, not more ESP
  analysis. All ESP analysis avenues are exhausted at the byte level.

## 23:4x UTC — USER OVERNIGHT HOLD (explicit)

USER DECISION: leave jwm1 untouched tonight — no repair writes, no
reboot, no boot config changes. Keep macOS accessible; offline
provenance/regression work only. The d1ee639c restoration candidate is
ready for later; do not ask again tonight.

Regression check archived and verified off-box: jw14m2
`/var/tmp/jwm1-esp-backups/regression-bootbin-shift.py` +
`verify-espnew-BOOT.BIN` / `verify-1753-BOOT.BIN` extracts — corruption
relationship reproduces off-box (missing reset-vector bytes
`090680d23e020014` confirmed).

## 18:0x CDT — ACTUAL DEFECT FOUND: HIDDEN IN-PLACE OVERWRITE OF /M1N1/BOOT.BIN

Preserved-image comparison (m1n1 stage2's own chainload target):

- FAT directory entry for `/M1N1/BOOT.BIN` is **byte-identical across
  eras**: write time 2026-09-06 19:45:34, access 2026-09-16, cluster
  34420, size 6,092,721 — no disclosed change, ever.
- The DATA at that cluster chain is NOT identical across eras:
  - `esp.new` (02:00 today): sha256 `d1ee639c160cdabdde206d8ef5b91ab7a58f132033b6fe91d92623bf028d3aa2`
  - `esp-recovery.part` (13:30 today) and current live (17:51): sha256
    `07009e0baf5482a7cf4a8904e5cb57c89f1ce74bd384117d1d9c2453877087d4`
- => **an in-place overwrite of BOOT.BIN's clusters happened between 02:03
  and 13:30 today, WITHOUT updating the directory entry** — a hidden
  payload swap (d1ee639c → 07009e0b). Cluster chain unchanged (same 1,488
  clusters, contiguous, start 34420).
- Correlation with observed boots (no causal claim beyond the bytes):
  - d1ee639c live: boots through Sep 17 22:56 (working Linux), and the
    pre-13:30 boots whose console showed GRUB errors.
  - 07009e0b live: every boot from 14:01 onward (14:0x unobserved; 21:39,
    22:13, 22:42, 22:53 user-observed frozen Asahi logo — the logo m1n1
    itself draws via its custom logo payload). Zero observed output in 4-5
    boots across two GRUB binaries, three cfg forms, two kernel pairs.
- Reading: the frozen logo is consistent with 07009e0b (m1n1+U-Boot main
  payload) failing in stage2→U-Boot launch or early U-Boot, before any
  console draw — independent of every ESP file swapped so far. This is an
  ACTUAL DEFECT (undisclosed overwrite), not a bounded hypothesis.
- Fix candidate (proposed, NOT executed): restore `/M1N1/BOOT.BIN` ←
  d1ee639c (extracted and preserved locally +
  jw14m2:/var/tmp/jwm1-esp-backups/bootbin-d1ee639c.bin). In-place,
  same cluster, same size — surgical. 07009e0b remains preserved in
  esp-live-1701/1706/1712/1743/1753 images and `boot.bin.stock-20260906`
  (3945ed51) remains on the ESP untouched.
- Attribution of who wrote 07009e0b (which lane/process) is NOT
  established; the overwrite window is 02:03–13:30 today.

## 18:1x CDT — ATTRIBUTION SEARCH + DT COMPARISON RESULTS

- Provenance search: NO record of `07009e0b` or `d1ee639c` in repo
  receipts/, .local/, or git history — the in-place overwrite's writer and
  build source are UNKNOWN. Known fleet mechanism that produces such a
  file: `update-m1n1`-style rebuild ("m1n1 + newest-kernel dtbs glob +
  u-boot.gz", documented in 2026-09-18-t6021-overlay-abort.md; same
  receipt documents the restore precedent
  `cp boot.bin.orig /boot/efi/m1n1/boot.bin`).
- DT comparison: BOTH builds embed the full multi-platform DTB set (~110
  FDT blobs, all Apple platforms incl. t8103/t6021/t602x/t8112 families).
  The boot-critical **j293 (T8103 MacBookPro17,1) blob is byte-IDENTICAL
  between d1ee639c and 07009e0b** (sha 1a72bc81c03cf0b548e9f959…, 69,046
  B, at 0x488e9f/0x488e97). No wrong-platform or missing-DT mismatch at
  the compatible level; the difference is in CODE/alignment (different
  builds), not the j293 DT.
- Scope correction recorded (Main): the 7.1.13 module mismatch made
  Wi-Fi/tailnet unavailable — the kernel itself may well have reached
  userspace; "unreachable" applies to remote reachability, not to kernel
  execution. macOS up and kept accessible (18:02 CDT, read-only posture,
  ESP unmounted).

## 18:1x CDT — U-BOOT PAYLOAD VERIFICATION; BUILD DIFFERENCE NARROWED

- Jwm1BootFix history checked: NO BOOT.BIN rebuild/write — it only
  captured the device state (d1ee was already live) and staged
  kernel/initramfs/cfg. Provenance of the in-place 07009e0b write remains
  UNKNOWN (no candidate lane found in any checked history).
- Both BOOT.BINs embed a gzipped U-Boot payload: decompresses cleanly
  (CRC-valid) to an IDENTICAL 639,624 B payload in both — **U-Boot
  2026.04 (May 26 2026 - 15:04:36 +0000)**, same boundaries, no banner
  (asahi hides it). Embedded U-Boot is NOT the differing variable.
- DTB sets are IDENTICAL: 110 unique FDT blobs in each, zero only-in-
  either (content-hashed); the boot-critical j293 (T8103 MBP17,1) blob is
  byte-identical (69,046 B, sha 1a72bc81…). No wrong-platform or
  missing-DT mismatch.
- Both carry the same m1n1 version marker `v1.5.2`; no U-Boot banner in
  either (asahi hides it); not Mach-O (raw ARM images).
- The entire difference reduces to: **m1n1 stage1+stage2 CODE rebuilt**
  (head entry instructions differ at byte 0; code regions to ~0xd4000
  differ; everything after shifts by 8 bytes) — a legitimate-looking
  rebuild of the same v1.5.2 m1n1 with the same U-Boot and DTB set.
- Candidate status (per Main): the difference is NOT demonstrated to be
  corruption or an incompatibility. CRC, decompression, and structural
  termination all pass. The "rebuild" remains candidate-status only; the
  d1ee→0700 swap being coincidental to the hangs is not excluded
  (independent failures remain possible).

## 18:4x CDT — CORRUPTION-MECHANISM HYPOTHESES (direction-accurate)

Candidate vehicles for the LEFT shift (bad = good[8:] + 8 zero bytes) —
hypotheses only; transport vs staging NOT proven (no exact feed recovered
for the corrupting write):

- (a) SOURCE-SKIP-8: the staging writer READ its m1n1 payload skipping
  the first 8 bytes (header-skip bug in a re-staging script), then wrote
  source[8:] at the chain start, with trailing zeros filling the 8-byte
  shortfall. Writing the full source at target+8 would shift RIGHT and
  does NOT produce this signature.
- (b) WRITE AT TARGET−8: the writer positioned its write 8 bytes before
  the chain start with the full source.

Candidate transport: the wr.py-style raw chunk writer (12-byte records:
u64 offset + u32 length + payload; recovered as wr-bootfix-0204.py,
sha dcb8ea29…) replayed with records derived from a diff against a
staged image whose /M1N1/BOOT.BIN region held the shifted payload —
this matches the in-place, dir-entry-untouched signature. The feed for
the corrupting replay has NOT been recovered; the 02:03
changed-sectors.txt feed provably wrote d1ee content (Jwm1BootFix
history). Staging-side vs transport/framing remains undetermined.

## 18:4x CDT — MAIN INDEPENDENT ROOT PROOF; ALL REBUILD/COMPILER SPECULATION RETRACTED

Main's independent mcopy extraction proved the exact relationship:

    a = d1ee639c BOOT.BIN (esp.new, mcopy extract)
    b = 07009e0b BOOT.BIN (esp-live-1753, mcopy extract)
    a[8:] == b[:-8]   EXACTLY TRUE for all 6,092,713 bytes
    b[-8:] == 8 zero bytes

**07009e0b is NOT a rebuild of any kind.** It is d1ee639c with the FIRST
8 BYTES REMOVED and 8 ZERO BYTES APPENDED. The missing first 8 bytes are
the reset vector head `09 06 80 d2 3e 02 00 14` (`mov x9,#'0';
b 0x8fc`). Mechanism of the frozen-logo hang: chainload entry at offset 0
now lands in the NOP slide (former vector-0 padding), falls through to
the displaced vector-1 code (`mov x9,#'1'; b exc_unk`) into the
unknown-exception path with the vector table displaced — m1n1 never
launches U-Boot. All "rebuild / different m1n1 code / alignment shift /
compiler-marker" speculation from earlier sections is RETRACTED; the
DTB-set and U-Boot "identical" findings stand (they are the shifted-
identical payloads).

Reproducible regression preserved:
`esp-audit-20260919/regression-bootbin-shift.py` (verified: reports
corruption True for 1753-vs-espnew; prints the missing reset-vector
bytes `090680d23e020014`).

Provenance: the 8-byte-short write happened between 02:03 and ~12:33
today (7623 inherited it from `esp-final.part`, which inherited from the
live device); the specific command/lane that dropped the 8-byte header
remains UNIDENTIFIED (checked histories clean: Jwm1InitramfsFix,
AccurateCicada, Jwm1BootFinalize, Jwm1BootFix — none wrote BOOT.BIN).
User hold on writes/reboots remains in force.

## 18:2x CDT — ENTRY-POINT DELTA (capstone disassembly); USB PROXY RESEARCH

- Head disassembly: d1ee639c entry at offset 0: `mov x9, #0x30; b 0x8fc`.
  07009e0b: 30 NOPs (0x0–0x74), then `mov x9, #0x31; b 0x898` at 0x78 —
  entry sequence MOVED; different x9 immediate (image-format/revision
  marker). NOP-slide keeps offset-0 entry theoretically functional; body
  layouts differ. Compiler/build markers absent (stripped raw ARM).
- m1n1 version marker v1.5.2 in both. U-Boot payloads byte-identical
  (CRC-valid). j293 DT byte-identical.
- USB proxy diagnostic research (Fedora/m1n1 official path): m1n1 exposes
  its USB proxy gadget over the USB-C port when stage2 pauses/backs off;
  requirements = one USB-C DATA cable host↔target + a host running python
  with AsahiLinux/m1n1 proxyclient (pyusb). Read-only capture viability:
  proxy enumerates only if the hang is inside m1n1 stage2's
  wait/proxy-capable path; if the hang is after USB teardown or in U-Boot,
  nothing enumerates. Cable availability on-site unverified — user flag
  for tomorrow if this path is chosen. No action taken tonight.

## 18:3x CDT — DEFECT DEMONSTRATED: 07009e0b EXCEPTION VECTOR TABLE MALFORMED

Source anchor: AsahiLinux/m1n1 v1.5.2 `src/start.S` — `_vectors_start`
(.align 11 = 2048-aligned) is a 16-slot ARM64 vector table, 128 B per
slot: slot 0 = `mov x9,'0'; b cpu_reset` (reset), slot 1 = `mov x9,'1';
b exc_unk`, … x9 carries the ASCII exception-type digit into the panic
handler (Main's ASCII-marker hypothesis CONFIRMED with source; not an
image-format revision).

Measured from the file bytes (capstone, branch targets absolute, base 0):
- d1ee639c: offset 0 = `mov x9,#0x30 ('0'); b 0x8fc` — correct vector 0;
  `_start` body follows the 2048-byte vector region.
- 07009e0b: offsets 0x0–0x74 = NOPs; the `'1'`/exc_unk handler starts at
  **0x78** — straddling the 128-byte slot boundary, with NOPs where
  vector 0 (the reset vector) must be.

=> **07009e0b's exception vector table is malformed/misaligned.** The
m1n1+U-Boot payload draws its logo, but the broken vector table breaks
exception dispatch and/or the stage2→payload handoff — hang at the m1n1
logo with zero console output, exactly as observed on all five boots
since the swap. This demonstrates the incompatibility/corruption Main
required before treating the rebuild as the defect: the in-place
overwrite installed a payload whose vector table is not valid at the
required alignment, unlike d1ee639c's correctly formed table.

Consequence for the fix: restoring `/M1N1/BOOT.BIN` ← d1ee639c repairs a
PROVEN structural defect, not merely a version preference. (Still NOT a
guarantee the full Linux boot then succeeds — the root userland and any
independent failures remain separate questions.)

## 01:1x UTC (Sep 20) — ROOT CAUSE ESTABLISHED BY MAIN (supersedes unknown-writer wording)

Main found the exact historical bug and asserts it with independent
verification (Bf16RecertRepair re-verifying original results):

- 15:57:18.127Z: the ESP staging writer's `add_file_83` built 28-byte
  directory entries but assigned 32-byte image slices (twice) → the
  staged image (`esp-repair`) SHRANK BY 8 BYTES — every allocation after
  the affected file shifted left 8. This is the source of the
  d1ee→0700 shift (BOOT.BIN payload landed 8 bytes into its region; the
  reset vector was consumed by the shift).
- 15:58Z: the corrected writer built a CLEAN `esp-final` — but
  `esp-repair` was left STALE on disk.
- 18:04Z: Main read the STALE `esp-repair` and overwrote `esp-final`
  with it — REINTRODUCING the shifted image into the lineage.
- 18:27Z: Jwm1InitramfsFix inherited it (7623 built from esp-final;
  flashed to the device 18:31Z = 13:31 CDT).
- Ownership (Main, honest): the historical repair code caused the
  corruption — NOT an m1n1 rebuild, NOT a macOS FAT writer.

This supersedes my earlier "02:03–13:30 window, writer unknown" wording.
My timeline reconciles: the 18:04Z reintroduction matches my observed
18:27–18:31Z (13:27–13:31 CDT) 7623 inheritance and flash. The current
repaired state (esp-live-1848, cd65c46d: d1ee BOOT.BIN restored, 7.1.6
pair, marked cfg, 9d6e7510 GRUB) was audited AFTER the restoration and
remains valid — the file audit found no shifted entry in the restored
payloads, and no new live writes have occurred from attribution work
alone.

## 18:1x CDT — INDEPENDENT SECOND-TOOL VERIFICATION (mtools); RETRACTION

RETRACTED: my earlier phrasing "BOOT.BIN byte-identical across
02:00/current" was wrong as written. What is identical: the file's
PLACEMENT (dir entry bytes, cluster chain = 1,488 contiguous clusters
starting 34420) and its directory timestamps. The CONTENT DIFFERS:
d1ee639c (02:00 era) vs 07009e0b (13:30 era + current).

Independent re-extraction with mtools (second tool, not my parser):
- `mdir -i /var/tmp/jwm1-esp/esp.new ::M1N1` and
  `mdir -i …/esp-live-1753.img ::M1N1` — listings agree with my parser
  (BOOT.BIN 6,092,721 B, 2026-09-06 19:45; stock backup 6,090,601 B;
  volume serial 6C79-DC47).
- `mcopy -n -i esp.new ::M1N1/BOOT.BIN /tmp/verify-espnew-BOOT.BIN`
- `mcopy -n -i …/esp-live-1753.img ::M1N1/BOOT.BIN /tmp/verify-1753-BOOT.BIN`
- Hashes: `d1ee639c160cdabdde206d8ef5b91ab7a58f132033b6fe91d92623bf028d3aa2`
  and `07009e0baf5482a7cf4a8904e5cb57c89f1ce74bd384117d1d9c2453877087d4`
  — mtools agrees with my parser exactly.

esp.new provenance: full-image sha256 TODAY =
`a0e10002eda5bd5a94998b4b63e2c13d766749dc8c8e73d6238797c1826e04cc` =
exactly the read-back digest recorded in
2026-09-19-jwm1-omarchy-bootloop-fix.md — the artifact is unmodified
since 02:03.

Diff structure (both 6,092,721 B; 3,754,145 differing bytes): 8 regions;
largest `0xf3ff0–0x5cf7af` (5,093,312 B — the embedded U-Boot+dtb area);
all FDT magics and m1n1 strings sit 8 bytes earlier in 07009e0b than in
d1ee639c — i.e., two different builds with different section alignment,
both structurally valid m1n1+U-Boot+dtb combos, neither truncated.

## 18:2x CDT — THEORY / RESEARCH (user-requested), sources cited

Sources:
- Fedora Asahi Remix troubleshooting,
  https://docs.fedoraproject.org/en-US/fedora-asahi-remix/troubleshooting/#stage2-troubleshoot
  — official procedure for "m1n1 stage 1 had trouble loading m1n1 stage 2"
  after an update: boot macOS, mount the EFI partition, swap
  `boot.bin` ↔ `boot.bin.old` in the `m1n1/` subdirectory. jwm1's ESP has
  the same layout (`/M1N1/BOOT.BIN` + a stock backup), and the extracted
  stage1 variable (`chainload=<esp-uuid>;m1n1/boot.bin`) proves jwm1's
  stage2 loads exactly this file.
- AsahiLinux/u-boot (asahi branch) `configs/apple_m1_defconfig`:
  `CONFIG_BOOTCOMMAND="bootflow scan -b"` — fallback scan executes
  `\EFI\BOOT\BOOTAA64.EFI` on the chosen ESP.
- AsahiLinux installer issue #100 — historical boot.bin repair precedent
  (per Main's research).
- Observed doc guidance relevant to symptom: U-Boot "can have trouble with
  certain kinds of USB devices"; recommended mitigation = disconnect all
  USB devices.

Causal theory (bounded; proven bytes vs inference separated):

PROVEN (bytes): (1) broken grub.cfg lineage through 16:32 (btrfs-rooted
search forms + init=; now fs-uuid-on-ESP + no init= + visible markers);
(2) 7.1.13 kernel vs 7.1.6-only root modules/pacman mismatch — the 7.1.13
boot was unreachable by construction (BRCMFMAC=m, no 7.1.13 brcmfmac.ko in
root); (3) hidden in-place /M1N1/BOOT.BIN content swap d1ee639c →
07009e0b in the 02:03–13:30 window with unchanged directory entry;
(4) 0-byte LAPKG.TXZ/REPAIR.SH fossils (now unreferenced).

BOUNDED HYPOTHESES (in priority order):
- H1: 07009e0b (the swapped-in m1n1+U-Boot main payload) fails in
  stage2→U-Boot launch or early U-Boot, before any console draw — the
  frozen Asahi logo is m1n1's own drawn logo. Supported: all 5 boots since
  the swap hung identically across 2 GRUB binaries, 3 cfg forms, 2 kernel
  pairs; d1ee639c-era boots reached GRUB (visible errors) and Sep 17
  working Linux.
- H2: U-Boot runtime device hang (USB device / ASMEDIA probe) — possible
  independent contributor; mitigation = disconnect USB before test boot.
- H3: display/console output path failure masking later stages — cannot be
  excluded remotely; markers address it if output works at all.
- H4: boot-selection divergence — weakened by official docs: the chosen
  ESP controls the default EFI path; ubootefi.var unchanged across eras.

PROPOSED (not executed): Step 1 — /M1N1/BOOT.BIN ← d1ee639c (Fedora
boot.bin.old procedure, with the last-known-working payload), USB
disconnected; keep 7.1.6 pair + marked cfg. Step 2 — Linux verification
battery (uname 7.1.6-1-1-ARCH, btrfs @, brcmfmac, wlan0, tailscale/SSH,
failed units). Step 3 (post-recovery, separate) — root consistency work
toward 7.1.13 + `update-m1n1` equivalent, then re-stage ESP. Fallback
ladder if Step 1 fails: /M1N1/BOOT.BIN ← boot.bin.stock-20260906
(3945ed51, pre-Sep-6 original — the literal boot.bin.old analogue); then
GRUB ← BOOTAA64.EFI.stock (405,504 B d5765e2c, authentic Asahi GRUB,
capability scan pending). Each step = one coordinated boot with
observation.

## 00:12 UTC (Sep 20) — MONITORING + PROVENANCE SEARCH SCOPE (corrected)

- Connectivity: BOTH identities offline (JW-M1 dark since 23:40Z; box
  state/stage UNKNOWN — the persistent default is the Linux chain, but
  whether the box is at m1n1, U-Boot, GRUB, a kernel, or powered into
  something else is not observable remotely). NO new user console
  observation exists for the 23:44 boot (the last explicit user
  observation — static Asahi logo — was for the 22:53 boot).
- Provenance search scope corrected: the writer's SOURCE need not be
  larger than 6,092,721 bytes (bad = good[8:] + 8 zero bytes; consistent
  with a writer that skipped the first 8 bytes of its source, or an
  8-byte write-offset error). Searching only larger artifacts does not
  exhaust provenance. Local hunt found no relevant artifact; Mac-side
  hunt blocked (box dark). Checked lane histories (Jwm1InitramfsFix,
  AccurateCicada, Jwm1BootFinalize, Jwm1BootFix) show no BOOT.BIN writer;
  deeper provenance requires sources not available in this lane.
- Regression check verified off-box on jw14m2 (corruption relationship
  reproduces; missing reset-vector bytes 090680d2 3e020014).
- Holding: no writes/reboots; monitoring read-only.

## 00:5x UTC (Sep 20) — GLOBAL AUDIT: CURRENT ESP CERTIFIED (FS + per-file), no remaining shifted entry

- FS structures on the CURRENT ESP (esp-live-1848, d1ee restored): boot
  sector 55AA ✓, backup boot sector byte-identical at sector 6 ✓,
  FSInfo RRaA (free 81,244, next-free 46,476) ✓, FAT1==FAT2 ✓, fsck-grade
  chain walk clean (reachable 46,473 + free 81,524 = exactly consistent)
  ✓. Sampled FS-structure blocks vs the 02:00-era image differ ONLY where
  today's file replacements legitimately changed FAT entries/FSInfo — no
  wholesale shift signature (a shifted FS would mismatch from offset 0).
- Per-file payload audit (each digest vs independently validated source):
  /M1N1/BOOT.BIN = d1ee639c (provenance-verified esp.new extract; reset
  vector 090680d2 restored; remainder exact) ✓; /grub-ane/grub.cfg =
  68930cc4 (composed, semantics verified) ✓; /grub-ane/VMLINUZ.REC =
  ee36d989 (7.1.6; cross-verified against jw16's rescue copy + banner +
  IKCFG six-symbol check) ✓; /grub-ane/INITRD.REC = de4ae604 (7.1.6;
  gzip CRC-valid, 888-entry cpio, btrfs.ko vermagic match, /init→systemd)
  ✓; /EFI/BOOT/BOOTAA64.EFI = 9d6e7510 (executed with visible console
  output this morning; capability strings verified) ✓.
- m1n1 rebuild provenance vs fleet: neither jwm1 build (d1ee639c,
  07009e0b) matches jw14m2's /boot/efi/m1n1/boot.bin (e77a5e1a, rebuilt
  TODAY 10:10 CDT) or its boot.bin.old (bf848a1f, 09:37 CDT) — separate
  lineage; both jwm1 builds carry m1n1 v1.5.2 + the full multi-platform
  DTB set incl. byte-identical j293 blob.
- CONSEQUENCE: no remaining shifted entry detected by any available
  check; the corruption is fully attributed (8-byte-left-shift of
  BOOT.BIN, repaired) and the CURRENT staged ESP certifies clean at both
  the filesystem and per-file level. Stage evidence for the pending boot
  still requires console/USB-proxy observation (prepared).

### CORRECTIONS (Main-directed, 00:5x-01:0x UTC)

1. CONNECTIVITY: the earlier "macOS accessible read-only" line was STALE —
   it referred to the 23:50 UTC window. EXACT SSH RESULT at 01:02 UTC:
   `ssh jw-m1-macos` → **connection timed out** (unreachable). Tailscale:
   JW-M1 Offline, lastSeen 2026-09-19T23:40:00.1Z. macOS is NOT currently
   verified reachable.
2. FSCK ARITHMETIC — exact accounting, replacing "exactly consistent":
   - Scan range: cluster indices 2..127,999 = 127,998 data clusters.
   - FAT-scan free (zero DWORDs): 81,524.
   - Walker-reachable (file/dir chains): 46,473 — this count EXCLUDES
     cluster 2 (the root directory itself; the walker counted child chains
     only), which accounts for the remaining +1: 81,524 + 46,473 + 1
     (root dir cluster 2) = 127,998 = the full scan range. No orphan, no
     unaccounted cluster.
   - FSInfo free hint = 81,244 — STALE by 280 vs the FAT scan. FSInfo is
     a hint (rw mounts leave it stale); not a defect, and not "exact".
   - Wording: FAT1==FAT2, all chains valid, partition sum exact
     (with root-cluster accounting); FSInfo hint stale-by-design.
3. BOOTAA64: its console output is HISTORICAL (pre-13:30 era) — NOT proof
   of current-boot behavior. The 22:53 boot with 9d6e7510 produced no
   output; its current-boot behavior is unproven like 0fe0f353's.
4. BOOT STAGE: remains UNKNOWN pending console/USB-proxy observation.

## 2026-09-20 — BOOT.BIN 0700 provenance CLOSED (Main extraction + Bf16RecertRepair independent verification)

Exact writer found in the MAIN parent session (`2026-09-08T11-10-14-932Z…jsonl`):
- **15:57:18Z** `add_file_83` built the FAT directory entry as `sn.encode(11) + attr(1) + zeros(8) + packH(2) + packH(2) + packI(4)` = **28 bytes** and assigned `img[entry_off:entry_off+32] = entry` — Python shrinks the bytearray by 4 per add. Two adds (LAPKG.TXZ, REPAIR.SH) = **−8 bytes total**; output written to **esp-repair.part** (the 0700 lineage origin). Synthetic regression: 1024→1020→1016 (−8), reproduced.
- **15:58:13Z** corrected to 32-byte entries but wrote **esp-final.part** from the CLEAN esp-fallback — it did not repair esp-repair.
- **18:04:34Z** read the stale esp-repair (28-entry shrink inherited) and wrote **esp-final** — reintroducing the bug; InitramfsFix copied esp-final→esp-recovery (truncate re-padded to 524,288,000, leaving content shifted −8) and flashed 13:31.

Mechanism: each 28-into-32 dirent write shifts all subsequent image bytes −4/−8; BOOT.BIN (data start 0x11a000 + (34420−2)×4096 = 0x878c000) then reads displaced — file-level signature `good[8:] + 8 zero bytes`, lost reset vector `09 06 80 d2 3e 02 00 14` (m1n1 stage1 head). No transport culprit: wr.py/flash/dd pipelines moved bytes as given.

Ownership: historical writer = the MAIN-session 15:57:18Z `add_file_83` (28-byte dirent bug), per Main's artifact extraction (89606/89609) and independent Bf16RecertRepair verification (synthetic −8 regression; per-artifact digest ladder d1ee vs 0700 lineage). Repaired bytes (d1ee639c) were restored to the live ESP 18:43 CDT Sep 19; preserved digests unchanged.

EXECUTION CORROBORATED (2026-09-20, Main + Bf16RecertRepair): the actual toolResult for the 15:57:18Z write (call_id `call_d558bbd5a6a34bbaacd8579c`, timestamp 2026-09-19T15:57:19.589Z, artifact 89657) reads: "Added LAPKG 27911868 bytes, Added REPAIR 901 bytes, cfg 720->745, VERIFIED LAPKG 0 bytes REPAIR 0 bytes, Final ESP: 524287992 bytes" — the literal 524,287,992-byte (8-short) output, live at write time. Evidence now complete: source (89606/89609) + mechanism (synthetic -8 regression, commit 1902d5e) + result (this toolResult) + artifact chain (digest ladder). Record fully verified; no further search required.
