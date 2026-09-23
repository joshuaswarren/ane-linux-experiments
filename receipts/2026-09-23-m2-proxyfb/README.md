# M2 proxy-with-fallback image (2026-09-23)

v1.6.1 + one-line config.h patch: EARLY_PROXY_TIMEOUT 5 -> 60.
Built in dg-alarm-py314:sep23 with M1N1_VERSION_TAG=v1.6.1.

- m1n1 part: 2ac417e7b34d1654f7c4bd7daf49b67ad9d5eca238f56b4c5341d62cb5d1110e
- stock m1n1 part: 9ad08653 (diff is the version tag path plus the timeout path only)
- stock boot.bin: a3f533b9 (first 1114112 bytes are 9ad08653, then STACKBOOT payloads)

Behavior: 60 s proxy wait with dots, then normal payload boot on timeout.

## Window five: gate dropped, wait proven in binary

- main.c: display/sip0 gate replaced with if (1).
- config.h: FB_SILENT_MODE off, EARLY_PROXY_TIMEOUT 60.
- part 9f04394f (1163264 B): all four wait strings present.
- boot 7ac6f874 with stock payload tail b73cd565.

## Window six: self-identifying build

- Tag v1.6.1-proxy60-4184923, banner PROXY60 line before the wait.
- part e5d6777c, boot with stock tail appended (sha below at write time).

## Window seven: USB debug prints

- src/usb.c: usbdbg lines for each hpm path with idx and ok/FAIL, and each phy bringup idx.
- part 6c7e4e3c, boot ff485221 with stock tail.

## ANE reservation build

- kboot.c: dt_reserve_asc_firmware("/arm-io/ane", NULL, "ane", true, 0)
  plus tolerant reserve when the FDT ane node is absent.
- part 3c0cd558, boot 31bd993e with stock tail. Tag v1.6.1-aneresv.
- Proxy wait 60 s and usbdbg prints kept.

## Reservation boot 31bd993e did not return (20:30:41 UTC)

- No ssh on jw14m2-linux 4+ min after the reboot (baseline 113-146 s).
- Cause in my patch (diff against the pristine v1.6.1 kboot.c): the T6021
  ADT node is `/arm-io/ane0` (macOS ioreg `"name" = <"ane0">`), not
  `/arm-io/ane`. My change removed the early `return 0` for a missing FDT
  node, so the call reached `adt_path_offset("/arm-io/ane")`, which fails,
  and `bail()` returned -1. That makes `kboot_prepare_dt` fail
  (payload.c:345 "Failed to prepare FDT!"), `payload_run` returns -1, and
  main.c:129-140 prints "No valid payload found" and parks in
  `uartproxy_run` with no timeout. jwm1 was offline, so no host.
- Recovery: boot picker to macOS (Joshua), then write from macOS.

## Fixed build aneresv2

- kboot.c reset to pristine v1.6.1, plus `dt_reserve_ane_firmware()`: ADT
  `/arm-io/ane0` then `/arm-io/ane`; each segment becomes a no-map
  `ane-firmware@<phys>` reserved node. Every failure prints and returns;
  the function returns void, so it cannot block the boot.
  `dt_set_memory` skips no-map nodes, so the RAM-map bails do not apply.
- part 37265871 (1163264 B), boot 8d0eac03 with stock tail b73cd565.
  Strings checked in the binary: PROXY60, usbdbg, "ANE: reserved",
  "ane-firmware@", "/arm-io/ane0", tag v1.6.1-aneresv2.
- Note: macOS-boot phys 0x1000092c000 is a hole outside Linux RAM, so a
  reservation does not change what Linux can overwrite there. The value of
  this boot is that the node names give this boot's ADT segment phys.
