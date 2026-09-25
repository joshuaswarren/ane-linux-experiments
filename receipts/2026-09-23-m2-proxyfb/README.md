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

- No ssh on m2-host 4+ min after the reboot (baseline 113-146 s).
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

## aneresv2 boot and the preloaded firmware

- Boot 8d0eac03 returned (21:09:39 UTC, stage 2 v1.6.1-aneresv2).
- Reserved nodes, no-map, apple,asc-mem:
  ane-firmware@10000848000 size 0xc4000 (TEXT),
  ane-firmware@10001400000 size 0x438000 (DATA).
  This boot's ADT places ANE elsewhere than macOS
  (0x1000092c000/0x1000150c000, sizes 0xe8000/0x284000).
- TEXT word 0 is 0x14000081, the firmware reset branch. DATA holds
  structured data. iBoot preloads the ANE firmware on the Linux boot.
- The firmware's own stamp at TEXT+0x423c is 0x100000c4000, so it expects
  its data at IOVA 1<<40 + 0xc4000, directly after its text.
- It is not the selene file: 744964 of 802816 text bytes differ. selene's
  __TEXT is 0xe8000 and its __DATA vm address is 0xe8000, matching the
  macOS segment sizes, not this preload. The stamp is the layout to trust.
- phys 0x10000000000 (the bypass fetch target) begins "ffOH", a firmware
  object header, not code.
- SID 0 page table base 0x10012418000 is all zeros.

## RUN attempts

- VENC words read 0 after boot; the ANE islands read ACTUAL 0xf. genpd
  returned -13; the direct TARGET 0xf write raised VENC. All 15 power
  words then read ACTUAL 0xf before any engine access.
- Bypass, SID 15 TCR 0x6: RUN moved STATUS 0x2a to 0x28. No DART fault
  (bit 31 never set), SCRATCH7 0, I2A empty. The core fetched the header.
- Translate, SID 15 TCR 0x9, TTBR read back on all three, walk verified:
  IOVA 1<<40 to TEXT phys, IOVA 0x100000c4000 to DATA phys. The core was
  already running. CPU_CONTROL 0 for 3 s left STATUS at 0x28. m1n1's ASC
  has only the RUN bit, so there is no reset short of a power cycle, and
  the ps@2e0 cycle is the one that freezes the box. Not re-run.
- Fresh boot (21:16:33 UTC), core confirmed in reset (CTL 0, STATUS 0x2a),
  map installed first, one RUN: STATUS 0x2a to 0x28 again. CTL 0x10,
  SCRATCH7 0, I2A empty, no fault. Identical to the bypass result.

## Blocker

The core leaves STOPPED on RUN but parks at 0x28 with no mailbox traffic
no matter what SID 15 maps. A non-code header and the real firmware,
mapped where the firmware's own stamp places its data, give the same park.
The core is not executing. RVBAR is latched at 0x10000000001, missing the
kext mode bits 0x0081<<48, and bit 0 holds the lock. Nothing safe clears
it. That lock is the blocker to firmware READY.

## Window eight (reboot 21:22:02 UTC)

- Jwm1UsbHost armed all five capture pieces first. Stage 2 came back
  v1.6.1-aneresv2. ssh up 21:23:56, 114 s after the reboot.
- No ACM link. The PD capture shows one 0.4 s data blip at 16:22:09 local,
  before m1n1 entry, so that was iBoot. After that the chip read flat.
  No xhci, no ACM, at any point.
- The camera frames (read directly, not from a report) show the m1n1
  console through "Boot policy: sip0 = 0" and then the greeter drawn over
  it. No PROXY60 banner and no usbdbg line in any frame.
- The binary does contain the banner: built 15:36 from main.c last touched
  14:22, and the banner printf sits in an unconditional block right after the
  sip0 line. It produced neither output nor the 60 s it should have added.
  That contradiction is unresolved. Settling it needs one more boot with a
  marker that cannot be missed, and MaxDispatch is on the box now.

## Trace breadcrumb boot (reboot 22:07:52 UTC)

- Image d740845b, stage 2 v1.6.1-trace. Linux up 22:09:49 (117 s).
- /proc/device-tree/chosen/asahi,m1n1-trace:
  trace:S1@338197435;S2@338197454;S3@338659166;S4@1778751031;
- S1 after usb_init, S2 at the marker, S3 before the wait loop, S4 before
  the payload. All four ran.
- Tick deltas at the 24 MHz counter: S1 to S2 is 19 ticks, S2 to S3 is
  461712 ticks (19 ms), S3 to S4 is 1440091865 ticks = 60.00 s.
- So the wait runs its full 60 s and then boots the payload. The counter is
  correct. No proxy connected (it took the timeout path to S4, not the
  early return). The framebuffer going static is a display refresh problem,
  not an execution problem: the code runs the whole time.
- The 113-118 s boots include this 60 s wait. The 146 s boot was slow for
  another reason, not because the wait ran only then.

## PD trace boot (reboot 22:14:58 UTC)

- Image 43ec6090, stage 2 v1.6.1-pdtrace. Linux up 22:16:53.
- Reads at t0, t10, and t50 are identical, so the port state is static for
  the whole minute. Nothing changes while the wait runs.
- MODE (0x03) is 41505020 = "APP " on hpm 0, 1, and 5. All three PD chips
  are alive and in application mode, none dead or in boot.
- STATUS (0x1a), first byte: h0 0x0d, h1 0xdd, h5 0x00. By the standard
  TPS6598x fields (bit 0 plug present, bits 3:1 conn state): h0 and h1 have
  plug present and conn state 6, h5 has neither.
- POWER_STATUS (0x3f): h0 0x3f, h1 0x7f, h5 0x00.
- DATA_STATUS (0x5f): h0 0x85004186, h1 0x03000080, h5 0x00000000.
- drd DCTL: d0, d1, d2 all read 0x80f00000, RUN_STOP (bit 31) set. All three
  dwc3 controllers are in device mode and running. There is no drd5, and no
  hpm2, so the hpm digit does not pair a port to its controller.
- h5 is the port that sees no cable at all. jwm1 saw the cable attached but
  no CC partner and VBUS off, so the M2 port facing it presents no Rd. h5,
  which detects nothing, is the candidate for that port.
