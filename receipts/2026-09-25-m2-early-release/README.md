# M2 early-release hook: VENC fix built, dry image fell to recoveryOS

## Build
- Hook file /tmp/m1n1-b9/src/ane_bringup.c parses clean, VENC table +
  ane_raise_venc() wired before the ANE raise.
- Dry m1n1 5b8ffd72, dry boot.bin 0d5c2de6 (verified: m1n1-part OK,
  110 dtbs, gzip magic). Write m1n1 674be9c0, write boot.bin 9fce23c8.
- No ESP write by this lane beyond Main-ordered dry flash.

## Dry boot result
- Pre-write backup of live 43ec6090 ESP kept at
  /var/tmp/m2-b9/boot.bin.live-43ec6090.bak (SHA match).
- Flashed dry 0d5c2de6 (post-write SHA match), rebooted 02:46:59.
- Box never returned on SSH (12+ min). Webcam frame via jwm1 shows the
  macOS Boot Recovery Assistant dialog: "The version of macOS on the
  selected disk needs to be reinstalled", Startup Disk / Recovery
  buttons. Same signature as the 2026-09-23 dry fall (recoveryOS route
  after a stage-2 hang).
- Fallbacks intact, untouched: live-43ec backup + stock a3f533b9.

## Reads
- No SCRATCH6 mark, no head words, no HELLO: no Linux boot, no log.
- Mailbox API state on the prior boot stands as reported (queued,
  never drained).
