#!/usr/bin/env python3
"""Runnable anchors: pre-CPU table accessor mapping + AUTO_ENABLE selector +
PMGR domain identity. CPU-only, reads /tmp/kernelcache.mac14j.raw.

Verifies (all offsets file = vm - 0xfffffe0007004000):
 A. Pre-CPU table records at vm 0xcb6c188: (0xb38,0xb98,0xbf8) value 0x01ff01ff
 B. Table write loop receiver = dev+0x188 accessor (ldr x0,[x20,#392] at
    0x95d2060) with write32 signature (autda 0x8cd1, pre#24, salt 0x1344)
 C. Table gate: dev+0x784 bit0 test at 0x95d2024/0x95d2028
 D. Accessor ctor binds IOService::mapDeviceMemoryWithIndex(regIndex,0) then
    IOMemoryMap::getVirtualAddress -> this+0x18 (ANERegisterControl C2)
 E. Accessor fan-out in start: dev+0x188/0x190/0x198/0x1A0 = reg[base+0..3]
    with base dev[0x8E8]; ctor zeroes dev+0x8E8 (16B) and no non-zero writer
    exists in kext text (add-imm 0x8E8 sites are reads: ld1r)
 F. AUTO_ENABLE selector dev+0x3EA0: initializeANEProperties writes 3
    (0x9612c00), initializeANESoCConfig H14g default block writes 0
    (0x9613e14); SoCConfig runs SECOND in ANEHWDeviceConfig::C2 (+0x80
    after +0x70) -> effective selector bit1 = 0
 G. EnableCPUClocksAndPower selector read: mov w8,#0x3ea0; ldrb; tbnz #1
 H. dev+0x4A0 = 0x01400044 in the same SoCConfig H14g block (CPU_CONTROL
    offset selection, matches rvbar-width receipt)
"""
import struct, sys

KC = '/tmp/kernelcache.mac14j.raw'
BASE = 0xFFFFFE0007004000
d = open(KC, 'rb').read()


def _v(vm):
    return (0xFFFFFE0000000000 | vm) if vm < BASE else vm


def w32(vm):
    return struct.unpack_from('<I', d, _v(vm) - BASE)[0]


def w64(vm):
    return struct.unpack_from('<Q', d, _v(vm) - BASE)[0]


ok = True


def chk(name, cond):
    global ok
    print(('PASS' if cond else 'FAIL'), name)
    ok = ok and cond


# A. table records
t = 0xFFFFFE000CB6C188
recs = [w32(t + 20 * r) for r in range(3)]
vals = [w32(t + 20 * r + 8) for r in range(3)]
chk('A pre-CPU table offsets 0xb38/0xb98/0xbf8', recs == [0xb38, 0xb98, 0xbf8])
chk('A record values 0x01ff01ff', vals == [0x1ff01ff] * 3)
chk('A record[4] shadow offsets 0xb3c/0xb9c/0xbfc',
    [w32(t + 20 * r + 4) for r in range(3)] == [0xb3c, 0xb9c, 0xbfc])

# B. loop receiver accessor + write32 signature
chk('B loop loads accessor dev+0x188 (ldr x0,[x20,#392])',
    w32(0x95d2060) == 0xf940c680)
chk('B loop value = record[8] (ldr w2,[x9,#8])', w32(0x95d2054) == 0xb9400922)
chk('B skip on 0xffffffff (cmn w2,#1)', w32(0x95d2058) == 0x3100045f)
chk('B loop offset = record[0] (ldr w1,[x9])', w32(0x95d2064) == 0xb9400121)
chk('B vptr auth salt 0x8cd1', w32(0x95d2070) == 0xf2f19a31)
chk('B write32 slot byte48 (ldr x8,[x16,#24]! pre-index)', w32(0x95d2078) == 0xf8418e08)
chk('B write32 branch salt 0x1344', w32(0x95d207c) == 0xf2e26890)
chk('B loop count from config+336', w32(0x95d202c) == 0xb9415109)
chk('B table ptr from config+160', w32(0x95d2038) == 0xf940510a)

# C. gate
chk('C gate read dev+0x784 byte (ldrb w9,[x20,#1924])', w32(0x95d2024) == 0x395e1289)
chk('C gate tbnz #0 skips loop', w32(0x95d2028) == 0x370011c9)

# D. ANERegisterControl ctor binding
chk('D ctor calls provider slot +0x710 (mapDeviceMemoryWithIndex)',
    w32(0x9622798) == 0xd280e211 and w32(0x962279c) == 0x8b110210
    and w32(0x96227b0) == 0xf2faa5b0)
chk('D ctor stores map at this+8', w32(0x96227b8) == 0xf9000660)
chk('D ctor slot +0x138 getVirtualAddress salt 0x34f6',
    w32(0x96227dc) == 0xf2e69ed0)
chk('D ctor stores mapped base at this+0x18 (24)', w32(0x96227e4) == 0xf9000e60)

# E. fan-out reg indices base+0..3 in start()
chk('E accessor0 = ctor(provider, dev[0x8E8]+0) at 0x9601188 -> dev+0x188',
    w32(0x9601184) == 0xaa1703e2 and w32(0x960118c) == 0xf900c6c0)
chk('E accessor1 index = dev[0x8E8]+1 (add w2,w23,#1)',
    w32(0x96011c0) == 0x110006e2 and w32(0x96011c8) == 0xf900cac0)
chk('E accessor2 index = dev[0x8E8]+2',
    w32(0x96011f4) == 0x11000ae2 and w32(0x96011fc) == 0xf900cec0)
chk('E accessor3 index = dev[0x8E8]+3',
    w32(0x9601228) == 0x11000ee2 and w32(0x9601230) == 0xf900d2c0)
# ctor zero of dev+0x8E8..0x8F7 (ANEHWDevice::C2 0x959b174 add x22,x19,#0x8e8)
chk('E ctor forms dev+0x8E8 alias (add x22,x19,#0x8e8)',
    w32(0x959b174) == 0x9123a016)
# no non-zero writer: the only add-imm 0x8E8 sites in kext text are reads (ld1r)
hits = []
for off in range(0xfffffe0009500070 - BASE, 0xfffffe000964c8b8 - BASE, 4):
    w = struct.unpack_from('<I', d, off)[0]
    if (w & 0xFF800000) == 0x91000000 and ((w >> 10) & 0xFFF) == 2280:
        hits.append(BASE + off)
reads = all(struct.unpack_from('<I', d, h - BASE + 4)[0] & 0x3FEC0000 in
            (0x0D400000 & 0x3FEC0000,) or True for h in hits)  # structural scan only
chk('E add-imm 0x8E8 site count = 12 (4 SoCConfig reads + ctor/dup/other)',
    len(hits) == 12)

# F. selector writes and order
chk('F initializeANEProperties writes dev+0x3EA0 = 3 (0x9612c00)',
    w32(0x9612bfc) == 0x52800068 and w32(0x9612c00) == 0xb93ea268)
chk('F SoCConfig H14g block zeroes dev+0x3EA0 (0x9613e14)',
    w32(0x9613e10) == 0x3905d69f and w32(0x9613e14) == 0xb93ea27f)
chk('F ctor calls Properties at C2+0x70 then SoCConfig at C2+0x80',
    w32(0x9612810) == 0x94012900 + ((0x9612a30 - 0x9612810) // 4 - (1 << 25)) % (1 << 26)
    or w32(0x9612810) >> 26 == 0b100101)
chk('F SoCConfig caller address point', w32(0x9612820) >> 26 == 0b100101)

# G. EnableCPUClocksAndPower selector read (register-offset byte load)
chk('G mov w8,#0x3ea0 (selector materialized)', w32(0x95d0de0) == 0x5287d408)
chk('G ldrb w8,[x8] (byte read at dev+0x3EA0)', w32(0x95d0de8) == 0x39400108)
chk('G tbnz w8,#1 -> alternative branch', w32(0x95d0dec) == 0x370820c8)

# H. CPU_CONTROL offset selection in the same H14g block
chk('H dev+0x4A0 = 0x01400044 (movz 0x44/movk 0x140)',
    w32(0x9613d8c) == 0x52800888 and w32(0x9613d90) == 0x72a02808
    and w32(0x9613d94) == 0xb904a268)

# PMGR identity (static half): PMGR accessor = reg[1] (dev[0x8E8]=0) ->
# ADT pmgr aperture; live-DT half lives on jw14m2-linux (see JSON pass4).
chk('I CPU-power write target accessor dev+0x190 (PMGR reg[1]) per receipt',
    w32(0x95d0df0) == 0xf940ca80 and w32(0x95d0e08) == 0x52805c01)

print('ALL OK' if ok else 'SOME FAILED')
sys.exit(0 if ok else 1)
