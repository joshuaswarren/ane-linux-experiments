#!/usr/bin/env python3
"""Selene-side consumer anchors for init-header field 0x60 (pool word0).

Image: /tmp/h14-staged-selene.macho sha256 9f7915c431d288a2bdc2132c399db8cf5574716a3b1e94af76be6a291c2e665b
file = vm + 0x4000 (__TEXT/__DATA, mapper receipt convention). Addresses below are vm.
"""
import struct, sys

P = '/tmp/h14-staged-selene.macho'
d = open(P, 'rb').read()


def w32(foff):
    # objdump addresses on the raw blob are FILE offsets (= vm + 0x4000)
    return struct.unpack_from('<I', d, foff)[0]


ok = True


def chk(name, vm, want):
    global ok
    got = w32(vm)
    good = got == want
    print(('PASS' if good else 'FAIL'), f'{name:52s} vm 0x{vm:x}: {got:08x}' + ('' if good else f' != {want:08x}'))
    ok = ok and good


# hdr[0x60] spill and gated consumer (fn 0x71A4 post-wake continuation)
chk('S1 hdr[0x60] load (x11=[x0,#96])', 0xB524, 0xF940300B)
chk('S2 spill to [sp]', 0xB530, 0xF90003EB)
chk('S3 x1=[sp,#8] pool window', 0xB6C0, 0xF94007E1)
chk('S4 cbz window -> skip call', 0xB6C4, 0xB4000081)
chk('S5 x0=[x19] image ops ptr', 0xB6C8, 0xF9400260)
chk('S6 x2=[sp] pool word0', 0xB6CC, 0xF94003E2)
chk('S7 bl 0x24908 consumer', 0xB6D0, 0x9400648E)

# fn 0x24908: word0 zero-reject + verbatim store
chk('S8 cbz x2 -> NULL return', 0x24908, 0xB4000382)
chk('S9 mov x20,x1 window', 0x24948, 0xAA0103F4)
chk('S10 mov x21,x2 word0', 0x2494C, 0xAA0203F5)
chk('S11 sub delta window-host', 0x24958, 0xCB000288)
chk('S12 stp window,word0 -> ops+0x60/0x68', 0x2495C, 0xA9065674)
chk('S13 str delta -> ops+0x70', 0x24964, 0xF9003A68)
chk('S14 NULL tail mov x0,xzr', 0x24978, 0xAA1F03E0)

# context: hdr[0x50] caps x27 (boot ordinal MIN) before 0x24980
chk('S15 ldp hdr[0x48],[hdr0x50]', 0xB52C, 0xA944A78A)
chk('S16 csel x27 = MIN', 0xB540, 0x9A89837B)
# DONE ack
chk('S17 DONE movz 0x2006 (w2)', 0xB7CC, 0x528400C2)
chk('S18 DONE w1=7', 0xB7D0, 0x528000E1)
chk('S19 DONE movk 0x0804', 0xB7D4, 0x72A10082)

print('ALL OK' if ok else 'SOME FAILED')
sys.exit(0 if ok else 1)
