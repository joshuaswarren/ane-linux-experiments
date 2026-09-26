# T6021 dart-ane0 DAPF lock: live clear blocked, stage-1 access aborts (2026-09-25)

## Leg 1, 20:47, run-204714
Module omarchy-ane agent/t6021-leg-baseline 0eaf1dd, sha256
b00d7abfdb09eced69bc49b8b2714930333b00058506937e81e12bfc464a464a,
params `fw_start_mpm_off=1 fw_start_venc_gates=0 patch_timer_freq=0x016e3600
fw_start_dapf=1 fw_start_dart_single_stream=1`.

Power form landed (ane_sys_mpm 0x3ff to 0x300, islands in macOS form).
DART single-stream landed (ENABLE 0xffff to 1; dart0 PROTECT 0x2 to 0x6).
DAPF writes did not land. All five entries, and the unused slot, read
r0=0 r4=0 start=0 end=3 r20=0 before and after. Firmware parked:
CPU_STATUS 0x2a to 0x28, no SCRATCH7 READY, FW-TT region all zero.

## Why the writes were dropped
m1n1 `R_PROTECT` (dart8110.py): bit 0 LOCK_TCR_TTBR, bit 1 LOCK_REG_4xx,
bit 2 unknown in m1n1. M2PreRunRE, from AppleT8110DART, says bit 1
write-protects the DAPF aperture at reg[3] (0x285804000) and bit 2 is the
extra DAPF protect bit macOS also sets. UNPROTECT at +0x204 clears a bit
unless PROTECT_LOCK at +0x208 has that bit set. A set PROTECT_LOCK bit
cannot be cleared until reset.

Live helper at 20:56, same boot, read:
PROTECT=0x6, UNPROTECT=0x6, PROTECT_LOCK=0x2, CPU_STATUS=0x28,
SCRATCH7=0. Bit 1 is set-once. The helper did not program. SCRATCH7
stayed 0 for 10 s.

Linux `drivers/iommu/apple-dart.c` defines PROTECT_LOCK and never writes
it. It locks only bit 0. m1n1 `dart.c` sets only PROTECT bit 0. The
set-once bit was therefore set before this Linux session.

## Stage-1 cannot reach the register
`sudo reboot` at 20:57. The catcher connected. Every read of
0x285800200 aborted: FAR 0x285800200, ESR 0x96000010 (synchronous
external abort), E_MMU_ERR_STS 0. The proxy returned 0xabad1dea. Stage-1
has the aperture unpowered, so the lock state at that point was not
measured and nothing was programmed. The chainload still ran. Linux ssh
had not answered by 21:02 (the previous boot answered in 25 s). A 21:00
frame shows the screen on, the Omarchy wordmark, and a kernel console,
not the U-Boot hang.

The catcher script now calls `pmgr_adt_power_enable("/arm-io/dart-ane0")`
before the read. That path has not run. It needs the next catch.
