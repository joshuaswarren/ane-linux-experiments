# iBoot ANE DART state at m1n1 proxy — 2026-09-24 20:38 UTC

Chip 0x6021. Stock m1n1 USB proxy. No guest. Log:
jwm1:~/m2proxy/hvlogs/iboot-dart/capture.txt

## Power, before any write
Every ANE island was off.
- ane_sys 0x28e080260 = 0xf000300 (WAS_PWRGATED|WAS_CLKGATED, ACTUAL=0, DESIRED=0)
- ane_cpu 0x28e0802e0 = 0xf000300 (same)
- ane_sys_mpm/td/base/set1-4 at 0x4000..0x4030 = 0x300 (ACTUAL=0, DESIRED=0)

## Power-on
pmgr_adt_power_enable succeeded for /arm-io/ane, /arm-io/ane0,
/arm-io/dart-ane0, dart-ane1, dart-ane2. Direct TARGET=0xf on the
0x4000 islands. Poll then showed ACTUAL=0xf on all nine words.
RVBAR read 0x10000000001.

## DART after that power-on
dart-ane0 (0x285800000): ENABLE all zero. TTBR[0..15] all zero.
TCR 0x1 on sid 0-13 and 15; sid14 TCR 0x6. No valid TTBR, so no
page was read.

dart-ane1 (0x285810000) and dart-ane2 (0x285820000): ENABLE all
zero. TTBR valid bit clear on every sid (values such as 0x3b7fb3fc).
Not a coherent page table.

## Kernel comparison (previous Linux boot, same machine)
All three instances: TCR0=0x9, TTBR0=0x10012535, inst0 ENABLE=0xfffe.
That is a kernel-installed table. It does not match iBoot's proxy-time
state, because iBoot left no valid TTBR. The domains were already
power-gated, so any flop state was gone before the TARGET write.

## Return
Proxy p.reboot() returned Linux 7.1.13-3-1-ARCH (up 15:41 CDT).
