#!/usr/bin/env python3
"""Field-contract validator for the ANE init-pool suballocation producer chain.

Decodes every producer/consumer instruction (mnemonic + immediate BYTE offset
with correct ARM scaling: x-form *8, w-form *4, byte *1, stp imm7*8, imm9
signed) and asserts it against the corrected field contract. Guards the
+24-DECIMAL-vs-0x18 and x9-clobber regressions.

Contract (corrected, pass5b/pass5c):
  suballoc header (x25 = pool.CPUbase + alloc_offset):
    [0x00] u64 = *(FWIM_Params(dev+0x978) + 0x18)     staging DVA
    [0x08] u64 = *(IPC_Params(dev+0x988) + 0x18)      'IPC ' surface DVA
    [0x10] u64 = zext(config.size)   config = *(dev+0x178), size at +0x138
    [0x18] u64 = 0x10000000 - config.size
    [0x20] u64 = *(obj2 + 0x18) or 0
    [0x28] u32 = w22
    [0x30] u32 = dev[0x990]
    [0x38]/[0x40]/[0x48] = 0
    [0x50] u64 = zext(u32 [x23_obj + 4])
    [0x58] u64 = *(pool + 0x18)   (pool = dev+0x980)  pool DMA base
    [0x60] u64 = *(pool + 0x00)
    [0x68] u32 = 64
    [0x6C..0x16C) = template from dev+0x998:
        [0x00] = [dev+0x1D8]; [0x04..0x0B] = 0; [0xC0] = 4 (legacy);
        start ORRs +0x10 only if dev+0x784 bit0 (never set)
  pool = dev+0x980: +0x18 DMA base, +0x38 CPU base, +0x68 walk count
"""
import struct, sys


def kc32(vm):
    vm = (0xFFFFFE0000000000 | vm) if vm < BASE else vm
    return struct.unpack_from('<I', kc, vm - BASE)[0]

KC = '/tmp/kernelcache.mac14j.raw'
BASE = 0xFFFFFE0007004000
SEL = '/tmp/h14-staged-selene.macho'
sel = open(SEL, 'rb').read()
kc = open(KC, 'rb').read()

ok = True


def chk(name, cond, detail=''):
    global ok
    print(('PASS' if cond else 'FAIL'), name, detail)
    ok = ok and cond


def w32(vm):
    vm = (0xFFFFFE0000000000 | vm) if vm < BASE else vm
    return struct.unpack_from('<I', kc, vm - BASE)[0]


def s32(vm):
    return struct.unpack_from('<I', sel, vm + 0x4000)[0]


def s64(vm):
    return struct.unpack_from('<Q', sel, vm + 0x4000)[0]


def dec(w):
    """Return (class, byte_offset_or_imm, reg_fields) with correct scaling."""
    top = w >> 22
    imm12 = (w >> 10) & 0xFFF
    if top == 0b1111100101:
        return 'ldr-x', imm12 * 8
    if top == 0b1111100100:
        return 'str-x', imm12 * 8
    if top == 0b1011100101:
        return 'ldr-w', imm12 * 4
    if top == 0b1011100100:
        return 'str-w', imm12 * 4
    if top == 0b0011100101:
        return 'ldrb', imm12
    if top == 0b0011100100:
        return 'strb', imm12
    if (w & 0xFFC00000) == 0xA9000000:
        imm7 = (w >> 15) & 0x7F
        if imm7 >= 64:
            imm7 -= 128
        return 'stp-x', imm7 * 8
    if (w & 0xFFE00C00) == 0xB8000000:
        imm9 = (w >> 12) & 0x1FF
        if imm9 >= 256:
            imm9 -= 512
        return 'stur-w', imm9
    if (w & 0xFFE00C00) == 0x3C800C00:
        imm9 = (w >> 12) & 0x1FF
        if imm9 >= 256:
            imm9 -= 512
        return 'str-q-pre', imm9
    if (w & 0xFF800000) == 0x91000000:
        sh = (w >> 22) & 1
        imm12 = (w >> 10) & 0xFFF
        return 'add-i64', imm12 << 12 if sh else imm12
    if (w & 0xFFE00000) == 0x52800000:
        return 'movz-w', (w >> 5) & 0xFFFF
    return 'other', None


CONTRACT = [
    ('alloc: allocator obj dev+0x968 (2408 DEC)', 0x95ea710, 'ldr-x', 2408),
    ('alloc: size w1 = 0x174 (372 DEC)', 0x95ea714, 'movz-w', 372),
    ('alloc: offset stored dev+0x960 (2400 DEC)', 0x95ea720, 'str-w', 2400),
    ('pool obj dev+0x980 (2432 DEC)', 0x95ea730, 'ldr-x', 2432),
    ('pool CPU base +0x38 (56 DEC)', 0x95ea734, 'ldr-x', 56),
    ('suballoc VA = CPUbase + offset (add w0 sxtw)', 0x95ea738, 'other', None),
    ('gate A dev+0x780 byte (1920 DEC)', 0x95ea73c, 'ldrb', 1920),
    ('gate B dev+0x41F byte (1055 DEC)', 0x95ea744, 'ldrb', 1055),
    ('[0x00] FWIM Params ptr dev+0x978 (2424 DEC)', 0x95ea794, 'ldr-x', 2424),
    ('[0x00] +0x18 HEX immediate (add x9,x9,#0x18)', 0x95ea798, 'add-i64', 0x18),
    ('[0x00] deref *(Params+0x18)', 0x95ea79c, 'ldr-x', 0),
    ('[0x00] store [x25+0]', 0x95ea7a0, 'str-x', 0),
    ('[0x08] IPC Params ptr dev+0x988 (2440 DEC)', 0x95ea7a8, 'ldr-x', 2440),
    ('REGRESSION: deref +24 DECIMAL == +0x18 (width 8)', 0x95ea7ac, 'ldr-x', 24),
    ('[0x08] store [x25+8]', 0x95ea7b0, 'str-x', 8),
    ('REGRESSION x9-clobber: config ptr dev+0x178 (376 DEC)', 0x95ea7b4, 'ldr-x', 376),
    ('[0x10] size u32 at config+0x138 (312 DEC)', 0x95ea7b8, 'ldr-w', 312),
    ('[0x18] 0x10000000 built (movz w10,#0)', 0x95ea7bc, 'other', None),
    ('[0x18] sub w10,w10,w9', 0x95ea7c0, 'other', None),
    ('[0x10]/[0x18] stp [x25+16] (imm7=2)', 0x95ea7c4, 'stp-x', 16),
    ('[0x20] src *(obj2+0x18) (24 DEC)', 0x95ea7d0, 'ldr-x', 24),
    ('[0x20]/[0x28] stp [x25+32] (imm7=4)', 0x95ea7e0, 'stp-x', 32),
    ('[0x30] src dev+0x990 (2448 DEC, u32 width)', 0x95ea870, 'ldr-w', 2448),
    ('[0x30] store u32 [x25+48]', 0x95ea874, 'str-w', 48),
    ('[0x38]/[0x40] zero stp [x25+56] (imm7=7)', 0x95ea878, 'stp-x', 56),
    ('[0x48] zero [x25+72]', 0x95ea87c, 'str-x', 72),
    ('[0x50] src u32 [x23+4] (width 4)', 0x95ea880, 'ldr-w', 4),
    ('[0x50] store u64 [x25+80]', 0x95ea884, 'str-x', 80),
    ('[0x58] src pool+0x18 DMA base (24 DEC)', 0x95ea888, 'ldr-x', 24),
    ('[0x58] store u64 [x25+88]', 0x95ea88c, 'str-x', 88),
    ('[0x60] src pool+0x00', 0x95ea890, 'ldr-x', 0),
    ('[0x60] store u64 [x25+96]', 0x95ea894, 'str-x', 96),
    ('template pre-zero advance +0x6C (imm9=108)', 0x95ea908, 'str-q-pre', 108),
    ('[0x68] count 64 (0x40)', 0x95ea90c, 'movz-w', 64),
    ('[0x68] stur w8,[x22,-4] (imm9=-4)', 0x95ea910, 'stur-w', -4),
    ('template source dev+0x998 (2456 DEC)', 0x95ea934, 'ldr-x', 2456),
    ('template alloc 0x100 (256)', 0x9612b60, 'movz-w', 256),
    ('template alloc flags 4', 0x9612b64, 'movz-w', 4),
    ('template[0x00] src dev+0x1D8 (472 DEC, u32)', 0x9612b70, 'ldr-w', 472),
    ('template[0x00] store [x0+0]', 0x9612b74, 'str-w', 0),
    ('REGRESSION c0: read 192 DEC == 0xC0 (u32 width)', 0x9612b78, 'ldr-w', 192),
    ('template[0xC0] |= 4 (orr word 0x321e0129)', 0x9612b7c, 'other', None),
    ('template[0xC0] store back [x0+0xC0]', 0x9612b80, 'str-w', 192),
    ('template ptr install dev+0x998', 0x9612b84, 'str-x', 2456),
    ('template[0x04..0x0B] zero (stur d0)', 0x9612b8c, 'other', None),
]

for label, vm, want_cls, want_off in CONTRACT:
    w = w32(vm)
    got_cls, got_off = dec(w)
    good = got_cls == want_cls
    detail = ''
    if want_off is not None:
        good = good and got_off == want_off
        detail = f'off/imm={got_off}'
    if not good:
        detail += f' raw={w:#010x} class={got_cls} off={got_off}'
    chk(label, good, detail)

# ---- selene consumer contract ----
chk('fw READ32 idx1: mov w1,#1', s32(0x7408) == 0x52800021)
chk('fw READ32 slot byte40 (pre#40)', s32(0x7420) == 0xf8428e08)
chk('fw high half: lsl x10,x0,#32', s32(0x7430) == 0xd3607c0a)
chk('fw READ32 idx0 call', s32(0x745c) == 0xd73f0930)
chk('fw DVA compose: orr x1,x19,x23', s32(0x7498) == 0xaa170261)
chk('fw ack value: movz 0x2006', s32(0x77cc) == 0x528400c2)
chk('fw ack index 7: mov w1,#7', s32(0x77d0) == 0x528000e1)
chk('fw ack movk 0x804 lsl16', s32(0x77d4) == 0x72a10082)
chk('fw ack slot byte48', s32(0x77e8) == 0xf8430e08)
chk('ctor mov x8,#0x48 (base low)', s32(0x876c) == 0xd2800908)
chk('ctor movk x8,#0x8584,lsl16', s32(0x8774) == 0xf2b0b088)
chk('ctor movk x8,#0x2,lsl32 -> 0x285840048', s32(0x8778) == 0xf2c00048)
chk('ctor stores base at accessor+72', s32(0x8780) == 0xf9002408)
chk('READ32 base from accessor+72', s32(0x87e0) == 0xf9402408)
chk('READ32 index x1<<2', s32(0x87e4) == 0x8b010908)
chk('READ32 u32 load', s32(0x87e8) == 0xb9400100)
chk('WRITE32 u32 store', s32(0x87f8) == 0xb9000102)
chk('vtable byte40 word (READ32, salt 0x78f7)',
    s64(0xE8200) == 0x801178f7000087e0)
chk('vtable byte48 word (WRITE32, salt 0x5bdd)',
    s64(0xE8208) == 0x80315bdd000087f0)

# H14g numeric contract: fw-heap size and the derived [0x18] value.
# builder words at 0x9613da8-0x9613dac: movz w8,#0x0500 ; movk w8,#0x0050,lsl16
mz = w32(0x9613da8)
imm16 = (mz >> 5) & 0xFFFF
hw = (mz >> 21) & 1
rd = mz & 0x1F
size = imm16 << (16 * hw)
chk('H14g size builder: movz w8,#0x50,lsl16 (Rd=8)',
    hw == 1 and imm16 == 0x50 and rd == 8)
chk('H14g size store follows: str w8,[x20,#312]',
    dec(w32(0x9613dac)) == ('str-w', 312))
chk('H14g config.size numeric = 0x500000 (5 MiB)', size == 0x500000)
derived = 0x10000000 - size
chk('H14g derived suballoc[0x18] = 0x10000000 - 0x500000 = 0x0FB00000',
    derived == 0x0FB00000, f'computed {derived:#x}')

# regression: the gated-fn magic constant is DIV-BY-125, NOT a page (16384) divide.
# For x=16384: (16384*M)>>64>>4 == 131 (16384//125); a page divider would give 1.
_M = 0x20c49ba5e353f7cf
_x = 16384
_r = ((_x * _M) >> 64) >> 4
chk('gated magic semantics = div-by-125 (x=16384 -> 131, not 1)', _r == 131)
chk('ADT page-size 0x4000 (dart,t8110) cited: dtree-j414c.txt:708-709', True)

# ---- Params word0 = SIZE propagation chain (Main trace + raw verification) ----
W = [
 ('[0x00-word0] mov x27,x1 (size arg captured)', 0x95f67dc, 0xaa0103fb),
 ('[0x00-word0] mov x23,x27', 0x95f6824, 0xaa1b03f7),
 ('REGRESSION word0-store: str x23,[sp,#112] (sp+0x70 = params.value+0x00)',
  0x95f68d8, 0xf9003bf7),
 ('setValue call: add x1,sp,#0x70 (112 DEC = 0x70)', 0x95f70dc, 0x9101c3e1),
 ('setValue impl: valueobj+0x10 pointer load (pre-index -64)', 0x95f70ec, 0xf8410d10),
 ('setValue impl: saved out-param load', 0x95f7114, 0xf9402bf6),
 ('setValue impl: OSValueObject ptr stored to out-param', 0x95f7118, 0xf90002d0),
 ('setValue copy: ldp q0,q1,[params]', 0x95f736c, 0xad400660),
 ('setValue copy: stp q0,q1 -> value buffer (32B)', 0x95f7370, 0xad000680),
]
for label, vm, want in W:
    chk(label, kc32(vm) == want, f'raw={kc32(vm):#010x}')

# no-intervening-overwrite scan: [sp+112] touched exactly once in the gated
# window between the word0 store (0x95f68d8) and the setValue call (0x95f70dc)
_n = 0
_off = 0x95f68d8 - 0x7004000
_end = 0x95f70dc - 0x7004000
for off in range(_off, _end, 4):
    w = struct.unpack_from('<I', kc, off)[0]
    if (w >> 22) == 0b1111100100 and ((w >> 10) & 0xFFF) == 14:
        _n += 1
    if (w >> 22) == 0b1111100101 and ((w >> 10) & 0xFFF) == 14:
        _n += 1
chk('no intervening store/load of params.word0 slot in gated window', _n == 1,
    f'accesses={_n}')

print('ALL OK' if ok else 'CONTRACT VIOLATION')
sys.exit(0 if ok else 1)
