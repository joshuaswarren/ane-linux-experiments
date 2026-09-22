# m2-host m1n1 ANE bring-up hook — built (Stage A, dry + write images)

Date: 2026-09-22 · Owner: M2M1n1Hook (subagent) · All times local.

## What exists now

Two m1n1 stage-2 images with a boot-time ANE (t6021, j414c M2 Max) bring-up
hook compiled in. The hook runs in `run_actions()` before the payload
chainload, so after it finishes (or hits its 10 s global deadline) the NORMAL
Omarchy chainload proceeds untouched. The full text log is injected into the
FDT at `/chosen/ane-bringup-log` (kboot.c, `dt_set_chosen` path), readable
from Linux at `/proc/device-tree/chosen/ane-bringup-log`.

- `images/boot.bin.ane-dry` (6,231,126 B, sha512 5031a95c…) — dry mode:
  ADT presence check + readbacks only (RVBAR, SCRATCH0/1/6/7, CPU_CONTROL,
  CPU_STATUS), then chainload. For the first boot: proves the mechanism and
  the FDT log path.
- `images/boot.bin.ane-write` (7,951,446 B, sha512 53f6dbdf…) — write arm:
  (b) pmgr ane power cycle via ADT gates (`pmgr_adt_power_disable/enable`,
  which poll ACTUAL to target), dart-ane0 enable; RVBAR write64
  `0x0081010000000001` + readback (abort-to-chainload on mismatch);
  (c) `dart_init_adt("/arm-io/dart-ane0", 0, 0, keep_pts)` +
  `dart_share_ttbr0` to reg instances 1/2 (proxyclient ane hack) +
  `dapf_init(".../dart-ane0", 1)` + selene mapped at DVA 0x10000000000
  (flat image: TEXT at +0, DATA at +0xe8000 by vmaddr, embedded from
  tools/ane-hunter/fixtures selene rc4x macho, 0x1a0000 B);
  (d) CPU_CONTROL 0 → 0x10; (e) poll SCRATCH7 == 0x08042006, ≤1000×1 ms,
  deadline-bounded; (f) on READY: publish SCRATCH0/1 = fw DVA, wake
  SCRATCH7 = 0xF7FBDFF9, poll B ≤1000×1 ms. No access to engine+0x1874008.

Hook source: `m1n1-ane-hook.patch` against upstream m1n1 main 4184923
(2026-09-18, /tmp/m1n1-src checkout). Build proven: dry and write both link
clean (write embeds the 1.7 MB fw; dry GCs it — 1,130,496 B vs 2,850,816 B
m1n1.bin).

Payload provenance: both images carry the payload carved verbatim from
m1-host's known-good Omarchy `/boot/efi/m1n1/boot.bin` (bytes 0x110000..,
sha512 727b418a…): its kernel dtb set includes t6021-j414c (verified at
payload offset 0x157276) plus u-boot.gz. Layout = m1n1.bin + dtbs +
gzip(u-boot) [+ config], same concatenation update-m1n1 produces; m1n1's
`payload_run` walks it by magic, so the payload need not match our m1n1
build.

## Boot sequence plan (sequencing §2–§3)

1. m2-host to macOS (Joshua / FleetMacOSUnattendedAccess recipe). SSH up
   (m2-host = laptop alias, <tailscale-ip> / <lan-ip>).
2. From macOS: mount disk0s4 ("EFI - OMARC"), install
   `images/boot.bin.ane-dry` as `/boot/efi/m1n1/boot.bin` (keep the
   existing `/var/tmp/m2proxy-staging/boot.bin.pre-proxy`, sha
   153170e0…, as the fallback file on the same volume). Announce ≥2 min,
   reboot. FIRST BOOT IS DRY: reads only.
3. Linux up → `cat /proc/device-tree/chosen/ane-bringup-log` (tr pipe
   '\|' '\n'). Expect `mode=dry`, ADT node handles, pre/end register
   dump. Restore pre-proxy and stop if anything looks wrong.
4. Iterate single-variable: install `images/boot.bin.ane-write`, reboot,
   read log — acceptance: RVBAR readback with mode bits (0x00810100…),
   CPU_CONTROL/CPU_STATUS, SCRATCH7 READY (0x08042006) or the no-READY
   signature; box boots Omarchy after every iteration.
5. Every reboot announced ≥2 min ahead. m3-host/m1-host read-only throughout.

## Receipts

- images/boot.bin.ane-dry  sha512 5031a95c329417f8badc23d90c1eb1e1…
- images/boot.bin.ane-write sha512 53f6dbdfddfb2e1cf524e3d00fb79e6b…
- m1n1-ane-hook.patch (source diff)
- Reference boot.bin (m1-host /boot/efi/m1n1/boot.bin) sha512 727b418a763f…
- Flat fw: TEXT @0 (0xe8000) + DATA @0xe8000 (0xb8000), sha256
  db4b4abb3463221b… (first 16 hex)
