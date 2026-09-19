# 2026-09-19 — jwm1 Omarchy boot loop: root cause + ESP recovery (boot outcome pending)

## Root cause (named)

**GRUB 2.14 (`grub-2:2.14-1.1`, pre-v7-btrfs) cannot read jwm1's v7.x btrfs inode
layout.** The root filesystem on `/dev/disk0s5` (label `asahi-root`,
`725346d2-f127-47bc-b464-9dd46155e8d6`, subvol `@`) carries v7 "remap/tombstone"
items at the classic inode key `(ino, type 0x01, 0)`. GRUB reads that item as the
inode and trusts its first u64 as the file size:

- `/@/boot/vmlinuz-linux-asahi`  → GRUB sees **10 bytes** (real: 33,917,440 B)
- `/@/boot/initramfs-linux-asahi.img` → GRUB sees **257 bytes** (real: 19,414,040 B)

GRUB therefore loads ~10 bytes as the kernel → instant kernel panic → boot loop
since Sep 18. The filesystem data was never lost: every file's real extents are
intact (verified: `usr/bin/bash` has a 1,196,032-byte extent; the kernel banner
reads `Linux version 7.1.6-1-1-ARCH (linux-asahi@archlinux)`).

Trigger context: jwm1 received the fleet 7.1.13 boot-file push on Sep 18
(jw14m2's `/boot` files are dated Sep 18 12:28); jwm1's `/@/boot` files now
surface the remap-stub sizes, its `pacman` db still says
`linux-asahi-7.1.6.asahi1-1`, and `/@/usr/lib/modules` has only
`7.1.6-1-1-ARCH`. Modules dir is intact and matches the intact kernel.

Diagnostics that pinned this down (all via raw reads — msdosfs mount is broken
on this macOS 27.0 install):

- ESP image + custom FAT32 parser: `tools/fat32-raw.py` (`grubenv` clean — no
  wedged `ane_trying`/`next_entry`).
- Raw btrfs reader `tools/btrfs-raw.py` over `ssh + sudo python rd.py`:
  superblock → boot chunk map → chunk tree → root/FS trees → dir/inode/extent
  items. v7.x specifics handled: key layout `(obj,type,off)` unchanged but type
  IDs renumbered (ROOT_ITEM=0x84, CHUNK_ITEM=0xe4); chunk header = 48 B with
  **u16** stripe counts; inode item = classic 160 B layout shifted +16
  (size@16, mode@52, atime@112); leaf item offsets are relative to header end
  (+101). Bootstrap system chunk: logical `0x1500000` 8 MiB SYSTEM|DUP,
  stripes `0x1500000`/`0x1d00000` (cross-checked vs `btrfs-progs 6.2
  dump-super` on a fake device).
- `btrfs-inspect-internal dump-super` output archived at
  `/var/tmp/jwm1-esp/fakedev.img` flow; superblock copy `superblock.bin`.

## Fix applied (ESP-only writes; disk0s5 never written)

1. Read the intact kernel + initramfs extents via `tools/btrfs-raw.py`:
   - vmlinuz: ino 642, 33,917,440 B, one extent, sha256
     `ee36d989d62f2dd498b818e15c2044350c79d814a2017ffca61fdc2ad1aa95b6`,
     banner `Linux version 7.1.6-1-1-ARCH (linux-asahi@archlinux)`,
     `ARM\x64` header OK — matches installed modules `7.1.6-1-1-ARCH`.
   - initramfs: ino 311689, 19,414,040 B, one extent, sha256
     `de4ae60473443e2b2184dce8b73be270ded13f21b704f7d568145bbb000d650c`,
     early plain-cpio + gzip main archive (RD_GZIP=y), contains `btrfs.ko`
     and vermagic `7.1.6-1-1-ARCH`.
2. Staged onto an ESP image copy (`/var/tmp/jwm1-esp/esp.new`) with a FAT32
   writer (`/tmp/esp-stage.py`): `/grub-ane/VMLINUZ.REC`,
   `/grub-ane/INITRD.REC` (8.3 names, contiguous cluster runs, both FATs kept
   consistent) and `/grub-ane/grub.cfg` rewritten **in place** (720 ≤ 973 B) so
   entry 0 = "Omarchy Linux recovery (kernel+initrd from ESP)"
   (`root=UUID=… rw rootflags=subvol=@ loglevel=7`), entry 1 = original
   `/@/boot` path (marked broken). Round-trip parse of `esp.new` verified
   byte-exact incl. `grubenv` (clean).
3. Wrote 12,416 changed 4K blocks (50,855,936 B) to `/dev/rdisk0s4`
   (write via seek+write; `pwrite` and `/dev/disk0s4` are silent no-ops on
   this macOS). **Full-device read-back sha256 matches `esp.new`**
   `a0e10002eda5bd5a94998b4b63e2c13d766749dc8c8e73d6238797c1826e04cc`.
4. `bless --mount '/Volumes/Asahi Alarm Minimal (BTRFS)' --setBoot --nextonly`
   → `ONE-SHOT BLESS OK` → reboot (~02:08).

## Boot outcome at yield time (02:29): UNCONFIRMED — box dark on tailnet

`tailscale ping` to 100.84.184.102 (jwm1-linux) and 100.67.134.6 (jw-m1-macos):
no reply for ~20 min after the reboot; `tailscale status` lists jwm1-linux
`active; relay "dfw"; offline, last seen 1d ago`. Not yet observable which of
these holds: (a) Linux up but wifi/tailscale not reaching tailnet, (b) panic
loop with a persistent stub default, (c) slow boot. Nothing further could be
observed remotely (no console). A manual power-cycle is safe: the ESP now
contains a validated recovery boot path, and worst case it repeats the recovery
entry rather than the truncated one.

### Post-reboot evidence (02:32–02:45 CDT)

`tailscale status --json`:
- `jwm1-linux`: `Online: False`, `lastSeen 2026-09-17T22:56:22Z` — unchanged,
  confirming Linux has not returned to the tailnet since Sep 17 22:56 UTC.
- `JW-M1` (macOS node): `Online: False`, `lastSeen 2026-09-19T07:10:00Z`
  (= 02:10 CDT, ~2 min after the reboot) — the Mac reached the tailnet **once**
  on macOS at 02:10, then went dark; lastSeen frozen through 02:45 CDT. So the
  one-shot did NOT produce a running Linux session, and after a brief macOS
  appearance the box dropped off again (second reboot → dark boot, or boot
  into a state without working networking). No reboot loop is visible in
  lastSeen (it is frozen, not advancing).

Read: the recovery kernel itself was never observed booting or failing — the
box left the network at the macOS-fallback stage. A manual power-on is safe
(ESP recovery entry is validated; truncated-kernel entry is no longer default).

## Contained artifacts

- `tools/fat32-raw.py` — FAT32 parser (list/cat/extract) for raw partition images.
- `tools/btrfs-raw.py` — raw read-only v7.x btrfs walker (ssh-rd or image).
- Staging artifacts on this workstation: `/var/tmp/jwm1-esp/{esp.part,esp.new,
  vmlinuz.tree,initramfs.tree,changed-sectors.txt,superblock.bin}` and
  `/tmp/{esp-stage.py,carve-*.py,rd.py,wr.py}` (also deployed to
  jw-m1-macos:/tmp).

## Follow-ups for whoever picks this up

1. Watch `tailscale ping 100.84.184.102` / `100.67.134.6`. If Linux is up:
   `uname -r` (expect `7.1.6-1-1-ARCH`), `systemctl is-active llm-inference`,
   `lsmod | grep -i ane`, then copy `/grub-ane/{VMLINUZ,INITRD}.REC` from the
   ESP back to `/@/boot/` under proper names and regenerate the initramfs
   (`mkinitcpio -P`) so GRUB's v7-inode bug stops mattering for /boot files
   (or upgrade grub to a v7-capable build), then re-point grub.cfg.
2. If macOS fallback appears instead, re-check `bless --info`, then re-arm the
   one-shot (attempt 2) per the 2-attempt policy.
3. If the box is panic-looping with the persistent stub default, reset the
   boot default to macOS from a later macOS session
   (`bless --mount /Volumes/Macintosh\ HD --setBoot`).
4. The `pacman.log` (11 B) and other logs are truncated/remap-shadowed — the
   Sep 17–18 event cannot be reconstructed from logs; jw14m2's Sep 18 12:28
   boot-file timestamps + jwm1's db state are the evidence.
