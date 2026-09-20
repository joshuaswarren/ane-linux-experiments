# jwm1 ANE DT deployed, payload rebuilt, one controlled reboot — node live, DARTs bound, STOP before ane.ko (2026-09-20)

Lane: Jwm1AnePlan (controlled deploy). Authorization: Main review of
`49415f5` (corrected dtb `033a3fc4…`, engine `0x26bc04000/0x24000`, phandles
`c5-c8`, no DART overlap) + explicit deploy/one-reboot authorization; GPU
owner confirmed the 12-round window NOT STARTED and held. This lane owned the
exclusive jwm1 boot window. **STOPPED at the ane.ko gate per instruction —
nothing below loads the module.**

## Preflight (all green)

- Identity: serial `C02DP17UQ05P` ✓, compatible `apple,j293 apple,t8103
  apple,arm-platform` ✓, kernel `7.1.13-3-2-ARCH` (unchanged) ✓.
- Services pre: sddm / NetworkManager / sshd active.
- **Fresh GRUB cmp PASS** re-run immediately pre-reboot (vmlinuz + initramfs
  rc=0 both), plus a third PASS after update-m1n1 and again — btrfs path
  untouched by the payload change.
- Pre-hashes recorded: stock dtb `ea32173d…`, `boot.bin` `50601efe…`,
  `boot.bin.old` `566227f9…`, `ubootefi.var` `a6e5ec85…`.
- Staged dtb hash re-verified on jwm1 after transfer: `033a3fc4…`.

## Deploy

1. Independent backups (named files, not relying on rotation):
   `/var/tmp/jwm1-ane-restore/backup/t8103-j293.stock-20260920T192547Z.dtb`
   (`ea32173d…`) and `boot.bin.pre-ane-20260920T192547Z` (6,212,622 B).
2. Installed the reviewed dtb over
   `/usr/lib/modules/7.1.13-3-2-ARCH/dtbs/t8103-j293.dtb`; installed sha
   re-read `033a3fc4…` ✓.
3. `update-m1n1` (default `*-ARCH` glob; no `/etc/default/update-m1n1`
   override): "m1n1 updated at /run/.system-efi/m1n1/boot.bin".
   Payload changed `50601efe… → 66604ffab562826876975ecfe8a194c035dfb022481cf4cd26297b8d57c047bd`
   (6,212,622 → 6,213,446 B — +824 B, exactly the patched-dtb delta), and
   `boot.bin.old` rotated to hold the pre-ANE payload `50601efe…`.

## Reboot (exactly one)

`sudo systemctl reboot`; machine returned 14:26:28 UTC (~33 s), SSH resumed
on first poll.

## Post-reboot verification (all green)

| check | result |
|---|---|
| serial / kernel | `C02DP17UQ05P` / `7.1.13-3-2-ARCH` unchanged ✓ |
| CPUs | **nproc = 8, online `0-7`** — the September one-core failure mode did not recur ✓ |
| ANE node | `/proc/device-tree/soc/ane@26a000000` live; compatible readback `apple,t8103-ane` ✓ |
| DARTs | all three bound: `26b800000/26b810000/26b820000.iommu → apple-dart`, dmesg "DART [pagesize 4000, 16 streams …] initialized" ×3 ✓ |
| ANE platform device | `platform 26bc04000.ane: Adding to iommu group 0` — the September proven signature, now from the ADT-derived node ✓ |
| module state | `lsmod ane` = 0; `/dev/accel` absent; ane.ko staged at `/var/tmp/jwm1-ane-restore/ane/ane.ko` (`14ff769f…`, vermagic-exact) — **not loaded, STOP honored** |
| services | sddm / NetworkManager / sshd active; GUI back; Wi-Fi/password/APFS/GRUB-config untouched |

No failure path was exercised: zero unexpected reboots, zero mutations
beyond the authorized dtb + payload.

## Next gate (awaiting Main)

ane.ko load → `/dev/accel/accel0` → fp16 64-el exact smoke → compiler
package ladder → schema-4 → islands → soak. The module is vermagic-exact and
staged; it loads only on Main's authorization of this receipt.
