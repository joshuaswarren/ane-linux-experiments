# m2-host m1n1 ANE hook — run status at handoff (Stage A done, boot window pending)

Date: 2026-09-22 · M2M1n1Hook · sanitized

## Hardware state

- m2-host (m2-host) is in iBoot RECOVERY (USB 05ac:1905, serial WR1CQCYQ67,
  confirmed against its own ADT capture). Only a physical picker exit gets it
  to macOS. Main's final ordering: M2UartProxy takes the FIRST window
  (ESP park 9ad08653, UART bring-up from m1-host-macOS); the hook route is
  fallback-only. I hold until they hand the box back.
- ESP disk0s4 "EFI - OMARC" currently has boot.bin = v1 hook 65d1e8ae
  (DEAD — hangs; treat as poison). Intact fallbacks on the same volume:
  boot.bin.pre-proxy.on-esp (153170e0, stock Omarchy) and
  boot.bin.proxy-swuf.installed (6dc0ec5d).
- The v1 dry boot hung the fabric exactly as the 09-20 rule predicts: it read
  engine registers with the island unpowered, before any pmgr bring-up.

## What is proven (receipts in this directory)

1. Bridge restore executed: m1-host's boot.bin (sha512 727b418a…) was written
   over m2-host-lan SSH, sha-verified on the ESP, box rebooted to Omarchy,
   SSH confirmed on m2-host-linux (<linux-ts-ip>). Then the ORIGINAL
   /var/tmp/m2proxy-staging/boot.bin.pre-proxy was restored to
   /boot/efi/m1n1/boot.bin and sha256-verified 153170e0…ad1ff5. ESP layout
   and write mechanics are proven end-to-end.
2. Hook v1 built and installed (65d1e8ae) — boot hung (see above). Its boot
   was announced ≥2 min to all peers; Linux never returned, which is the
   first real datapoint for the fabric-hang theory.

## Hook images (latest = v3, WDT-safe; install v3 only, never v1)

| image                        | sha256  | contents                                        |
|------------------------------|---------|-------------------------------------------------|
| images/boot.bin.ane-dry-v3   | 1b241669… | m1n1 + hook DRY mode + ref payload (t6021-j414c dtb verified at payload 0x157276) |
| images/boot.bin.ane-write-v3 | f916390e… | same, write arm, selene fw embedded (verified byte-identical prefix) |

v3 differences vs v1/v2 (m1n1-ane-hook-v3-wdtsafe.patch vs upstream main
4184923):

- pmgr chain raised FIRST ("/arm-io/ane" + "/arm-io/dart-ane0",
  pmgr_adt_power_enable walks parents, polls ACTUAL) before ANY engine read,
  in dry mode too.
- Every MMIO read is log-then-read: "reading <reg>@<addr>" is committed to
  the FDT log buffer AND printed to the console ("ANE: …") BEFORE the read,
  so a hang names the guilty register as the last line on the UART.
- Primary WDT ("/arm-io/wdt", registers 0x10/0x14/0x1c per m1n1 wdt.c and
  drivers/watchdog/apple_wdt.c) armed with a 30 s timeout, tick rate
  self-calibrated by timing WDT_COUNT over a 100 ms delay (24 MHz fallback),
  covering the register window; disarmed at the done label.
- 10 s in-hook deadline (timeout_calculate) bounds polls; polls ≤1000×1 ms.
- Write arm unchanged: RVBAR 0x0081010000000001 write+readback (abort on
  mismatch), dart-ane0 SID 0 mapping of selene at DVA 0x10000000000
  (TEXT @+0, DATA @+0xe8000), TTBR0 shared to dart reg instances 1/2,
  dapf_instance-0 applied, CPU_CONTROL 0→0x10, SCRATCH7 == 0x08042006 poll,
  publish SCRATCH0/1 = fw DVA, wake 0xF7FBDFF9, poll B.
- On completion the log goes to the FDT: /chosen/ane-bringup-log, readable
  at /proc/device-tree/chosen/ane-bringup-log.

## Known limitations (honest)

- No sticky reset-reason skip yet: if the WDT bites, the next boot re-enters
  the hook. Exposure is small (the WDT only covers the register window that
  v2's pmgr-first ordering should make safe) but the loop is not excluded by
  code — it is excluded by v3's design assumption that powered reads don't
  hang. Wiring a proven reset-reason bit is the next hardening step.
- The 30 s WDT timeout can fire on a legitimately slow poll chain
  (2×1000×1 ms polls + 10 s deadline < 30 s, so only a true fabric hang
  triggers it).
- WDT arm/disarm paths compile and the decision logic is code-reviewed but
  are NOT hardware-tested (no box available).

## Acceptance status vs ticket

- Receipt with dry-boot log via /proc/device-tree/chosen: PENDING (blocked
  on the boot window; mechanism staged, ESP write proven).
- Write-arm logs (RVBAR mode bits, CPU_STATUS, SCRATCH7 READY): PENDING,
  images staged.
- M2 booting Omarchy after every iteration: proven once (bridge + restore);
  v1 iteration ended in the documented hang + recovery.
