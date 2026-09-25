# M2 early-release hook: VENC fix built, images verified, ESP on hold

## Hook change (/tmp/m1n1-b9/src/ane_bringup.c, untracked vs upstream)
- Repaired duplicated table/comment header at lines 434-450 (gcc
  -fsyntax-only rc=0).
- Added VENC provider chain (venc_sys 0x2902803e0, pipe4/5 + me0/1 at
  0x290288008/010/018/020), parent-first TARGET=0xf, ACTUAL=0xf gate,
  wired via ane_raise_venc() before the ANE island raise.

## Images (built, verified, staged only at /var/tmp/m2-b9/)
- dry: m1n1 5b8ffd72 (mode=dry, venc strings present), boot.bin
  0d5c2de6 (m1n1-part OK 0x110000, 110 dtbs to 0x5a0e15, gzip magic 1f8b).
- write: m1n1 674be9c0 (mode=write), boot.bin 9fce23c8 (m1n1-part OK
  0x2b4000, mode string present).
- Neither installed. ESP untouched.

## ESP hold
Live ESP 43ec6090 vs stock-a3f533b9 fallback unresolved. No flash, no
reboot from this lane.
