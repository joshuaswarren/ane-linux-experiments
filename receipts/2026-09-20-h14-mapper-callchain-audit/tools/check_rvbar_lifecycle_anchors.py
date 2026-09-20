#!/usr/bin/env python3
"""RVBAR latch/reset lifecycle byte anchors (lane: M2ResetLifecycle, 2026-09-20).

KC: /tmp/kernelcache.mac14j.raw sha256 8304156fe05849a45f1c15807432e82cb0e8ac8cb9c883541889bf51287340fa
file_offset = vm - 0xfffffe0007004000 (flat layout, verified in mapper receipt).

Anchors prove:
  A. ANE_Init RVBAR gate/compose/write64 + CPU_CONTROL order + ack poll
  B. ANE_Init internal power-cycle retry (power_off -> power_on -> re-entry)
  C. power_off_hardware_gated -> ANE_deInit + DisableANEClocksAndPower
  D. PMGR PS disable write32(value=0) via dev+0x190 (enable side 0xf per pass4)
  E. start() getProperty("pre-loaded") -> dev+0x41F sole set/clear sites
"""
import struct, sys

KC = '/tmp/kernelcache.mac14j.raw'
BASE = 0xFFFFFE0007004000
d = open(KC, 'rb').read()


def w32(vm):
    return struct.unpack_from('<I', d, vm - BASE)[0]


ok = True


def chk(name, vm, want):
    global ok
    got = w32(vm)
    good = got == want
    print(('PASS' if good else 'FAIL'), f'{name:58s} {vm:x}: {got:08x}' + ('' if good else f' != {want:08x}'))
    ok = ok and good


# --- A. ANE_Init 0x95e942c: RVBAR block 0x95e9850..0x95e99b8 ---
chk('A1 gate ldrb dev+0x41F', 0xFFFFFE00095E9850, 0x39507E68)
chk('A2 tbnz #0 skip', 0xFFFFFE00095E9854, 0x370009C8)
chk('A3 mov w1,#0x1050000', 0xFFFFFE00095E985C, 0x52A020A1)
chk('A4 bl read64OneShot', 0xFFFFFE00095E9860, 0x9400E4A9)
chk('A5 tbnz w0,#0 skip (bit0)', 0xFFFFFE00095E9864, 0x37000940)
chk('A6 mask lo movz -0x800', 0xFFFFFE00095E9868, 0x9280FFF6)
chk('A7 mask hi movk 0xff7e', 0xFFFFFE00095E986C, 0xF2FFEFD6)
chk('A8 base lo movz 1', 0xFFFFFE00095E9870, 0xD2800035)
chk('A9 base hi movk 0x81', 0xFFFFFE00095E9874, 0xF2E01035)
chk('A10 ldr Params dev+0x978', 0xFFFFFE00095E9880, 0xF944BE68)
chk('A11 ldr [Params+0x18] DVA', 0xFFFFFE00095E9884, 0xF9400D08)
chk('A12 and x8,x8,x22', 0xFFFFFE00095E9888, 0x8A160108)
chk('A13 orr x21,x8,x21', 0xFFFFFE00095E988C, 0xAA150115)
chk('A14 accessor dev+0x188', 0xFFFFFE00095E997C, 0xF940C660)
chk('A15 mov w1,#0x1050000', 0xFFFFFE00095E9980, 0x52A020A1)
chk('A16 mov x2,x21', 0xFFFFFE00095E9984, 0xAA1503E2)
chk('A17 bl write64', 0xFFFFFE00095E9988, 0x9400E4C1)
# CPU_CONTROL order (both paths converge here)
chk('A18 ldr w1,[dev+0x4A0]', 0xFFFFFE00095E9990, 0xB944A261)
chk('A19 write32 w2=0', 0xFFFFFE00095E99A8, 0x52800002)
chk('A20 write32 w2=0x10', 0xFFFFFE00095E99D0, 0x52800202)
# fw-ready ack
chk('A21 movz w24 0x2006', 0xFFFFFE00095E9A60, 0x528400D8)
chk('A22 movk w24 0x0804', 0xFFFFFE00095E9A64, 0x72A10098)
chk('A23 cmp w0,w24', 0xFFFFFE00095E9AB0, 0x6B18001F)

# --- B. ANE_Init retry: power cycle ---
chk('B1 bl power_off_hardware_gated', 0xFFFFFE00095EB280, 0x94007332)
chk('B2 bl power_on_hardware_gated', 0xFFFFFE00095EB3AC, 0x940070CE)

# --- C. power_off_hardware_gated 0x9607f48 ---
chk('C1 guard ldrb dev+0x3FB', 0xFFFFFE0009608020, 0x394FEE68)
chk('C2 tbz #0 skip deInit', 0xFFFFFE0009608024, 0x360000C8)
chk('C3 bl ANE_deInit', 0xFFFFFE000960802C, 0x97FF90D1)
chk('C4 bl DisableANEClocksAndPower #1', 0xFFFFFE00096082D0, 0x97FF2A8C)
chk('C5 bl DisableANEClocksAndPower #2', 0xFFFFFE0009608320, 0x97FF2A78)

# --- D. DisableCPUClocksAndPower 0x95d396c: PMGR PS write 0 ---
chk('D1 PMGR accessor dev+0x190', 0xFFFFFE00095D3D80, 0xF940CA80)
chk('D2 write32 slot pre-index', 0xFFFFFE00095D3D94, 0xF8418E08)
chk('D3 write32 value 0x00000000', 0xFFFFFE00095D3D9C, 0x52800002)

# --- E. start() 0x96005e8: "pre-loaded" -> dev+0x41F ---
chk('E1 set w8=1', 0xFFFFFE0009600ED0, 0x52800028)
chk('E2 strb dev+0x41F =1', 0xFFFFFE0009600ED4, 0x39107EC8)
chk('E3 mov w8=0', 0xFFFFFE0009600FD8, 0x52800008)
chk('E4 strb dev+0x41F =0', 0xFFFFFE0009600FDC, 0x39107EDF)
s = 0xFFFFFE00074C4968 - BASE
chk('E5 "pre-loaded" string @0x74c4968', None if d[s:s + 10] == b'pre-loaded\0' else 0,
    None if d[s:s + 10] == b'pre-loaded\0' else 1) if False else None
print(('PASS' if d[s:s + 11] == b'pre-loaded\0' else 'FAIL'),
      'E5 "pre-loaded" cstring @0x74c4968'); ok &= d[s:s + 11] == b'pre-loaded\0'

# --- F. ack handshake ordering (pass5): SCRATCH7 pulse/probe/wake/done ---
chk('F1 InitASR entry bti', 0xFFFFFE000960F2A8, 0xD503245F)
chk('F2 InitASR clears [dev+0x438]', 0xFFFFFE000960F2C4, 0xB9443A61)
chk('F3 write32 [dev+0x450]=SCRATCH6off', 0xFFFFFE00095E9554, 0xB9445261)
chk('F4 pulse w2=1 [dev+0x454]', 0xFFFFFE00095E9674, 0x52800022)
chk('F5 pulse w2=0 [dev+0x454]', 0xFFFFFE00095E9704, 0x52800002)
chk('F6 probe read1 [dev+0x454]', 0xFFFFFE00095E979C, 0xB9445661)
chk('F7 probe read2 [dev+0x454]', 0xFFFFFE00095E97F8, 0xB9445661)
chk('F8 attempt counter mov 0x230', 0xFFFFFE00095E9840, 0x52804608)
chk('F9 pub SCRATCH0 field dev+0x438', 0xFFFFFE00095EAA98, 0xB9443A61)
chk('F10 pub SCRATCH1 field dev+0x43C', 0xFFFFFE00095EAAD0, 0xB9443E61)
chk('F11 wake movz 0xdff9', 0xFFFFFE00095EAB24, 0x529BFF22)
chk('F12 wake movk 0xf7fb -> 0xF7FBDFF9', 0xFFFFFE00095EAB28, 0x72BEFF62)
chk('F13 wake write32 [dev+0x454]', 0xFFFFFE00095EAB0C, 0xB9445661)
chk('F14 done movz 0x2006', 0xFFFFFE00095EAA88, 0x528400D6)
chk('F15 done movk 0x0804', 0xFFFFFE00095EAA8C, 0x72A10096)
chk('F16 done cmp w0,w22', 0xFFFFFE00095EAB58, 0x6B16001F)
chk('F17 loopA bound cmp 1000', 0xFFFFFE00095E9AF4, 0x710FA39F)
chk('F18 loopB bound cmp 1000', 0xFFFFFE00095EAB94, 0x710FA37F)
chk('F19 dsb st before publication', 0xFFFFFE00095EAA90, 0xD5033E9F)

chk('G1 r32 SCRATCH3 field', 0xFFFFFE00095EA424, 0xF940C660)
chk('G2 mov x22,x0', 0xFFFFFE00095EA448, 0xAA0003F6)
chk('G4 ldr cap dev+0x3A90', 0xFFFFFE00095EA690, 0xF95D4A69)
chk('G5 csel MAX', 0xFFFFFE00095EA698, 0x9A888136)
chk('G6 heap tag lo', 0xFFFFFE00095EA6C0, 0x52882A04)
chk('G6 heap tag hi', 0xFFFFFE00095EA6C4, 0x72A908A4)
chk('G7 bl AllocSharedSurf', 0xFFFFFE00095EA6D4, 0x94002FE8)
chk('G8 obj2 null init', 0xFFFFFE00095EA618, 0xF90047FF)
chk('G10 obj2 DVA load', 0xFFFFFE00095EA7D0, 0xF9400D3A)
chk('G11 stp [0x20][0x28]', 0xFFFFFE00095EA7E0, 0xA9025B3A)
chk('G12 DMM ptr', 0xFFFFFE00095EA710, 0xF944B660)
chk('G13 size 0x174', 0xFFFFFE00095EA714, 0x52802E81)
chk('G15 off save dev+0x960', 0xFFFFFE00095EA720, 0xB9096260)
chk('G16 pool load', 0xFFFFFE00095EA730, 0xF944C268)
chk('G17 pool hostVA', 0xFFFFFE00095EA734, 0xF9401D09)
chk('G18 suballoc base', 0xFFFFFE00095EA738, 0x8B20C139)
chk('G19 ctx[0]=SCRATCH0', 0xFFFFFE00095EA0F8, 0xB90002E0)
chk('G20 +1', 0xFFFFFE00095EA120, 0x11000408)
chk('G21 ctx[4]', 0xFFFFFE00095EA124, 0xB90006E8)
chk('G22 hdr50 src', 0xFFFFFE00095EA880, 0xB94006E9)
chk('G23 pool word0', 0xFFFFFE00095EA890, 0xF9400108)
chk('G24 hdr60 store', 0xFFFFFE00095EA894, 0xF9003328)
chk('G25 fwld gate 420', 0xFFFFFE00095F0164, 0x39508288)
chk('G25 fwld store 990', 0xFFFFFE00095F0180, 0xB9099297)
chk('G25 fwld mov w23,w24', 0xFFFFFE00095F0184, 0x2A1803F7)
chk('G25 fwld zero', 0xFFFFFE0009612B00, 0xB909927F)
chk('G26 pool out dev980', 0xFFFFFE000960402C, 0x912602C2)
chk('G26 pool size 0x40000', 0xFFFFFE000960403C, 0x52A00081)
chk('G26 ddm tag lo', 0xFFFFFE0009604044, 0x5289A404)
chk('G26 ddm tag hi', 0xFFFFFE0009604048, 0x72A889A4)

# --- H. params word0 producer (pass8: hdr[0x60] = requested size) ---
chk('H1 mov x23,x27 (size)', 0xFFFFFE00095F6824, 0xAA1B03F7)
chk('H2 save [sp,#96]', 0xFFFFFE00095F687C, 0xF90033F7)
chk('H3 restore [sp,#96]', 0xFFFFFE00095F6894, 0xF94033F7)
chk('H4 str word0 -> [sp,#112]', 0xFFFFFE00095F68D8, 0xF9003BF7)
chk('H5 setValue struct base sp+0x70', 0xFFFFFE00095F70DC, 0x9101C3E1)
chk('H6 setValue call', 0xFFFFFE00095F70E4, 0x9400008C)
chk('H7 out-param reload [sp,#80]', 0xFFFFFE00095F7114, 0xF9402BF6)
chk('H8 *out = value buffer', 0xFFFFFE00095F7118, 0xF90002D0)

# --- I. DONE readback semantics (pass9): request threshold + address pair ---
chk('I1 ldr ctx[0]', 0xFFFFFE00095EA1D4, 0xB94002E8)
chk('I2 cmp ctx[0],#0x21', 0xFFFFFE00095EA1D8, 0x7100851F)
chk('I3 b.cc (<0x21) -> IPC alloc', 0xFFFFFE00095EA1DC, 0x540001C3)
chk('I4 ldr ctx[4] ordinal', 0xFFFFFE00095EA214, 0xB94006E8)
chk('I5 ldr floor dev+0x3A90', 0xFFFFFE00095EA218, 0xF95D4A69)
chk('I6 csel MAX(ordinal,floor)', 0xFFFFFE00095EA220, 0x9A888128)
chk('I7 IPC tag movz 0x4320', 0xFFFFFE00095EA248, 0x52886404)
chk('I8 IPC tag movk 0x4950', 0xFFFFFE00095EA24C, 0x72A92A04)
chk('I9 orr SCRATCH1<<32|SCRATCH0', 0xFFFFFE00095EAD54, 0xAA168101)
chk('I10 bl aneAddressToHostAddress', 0xFFFFFE00095EAD5C, 0x9400031E)
chk('I11 cbz fw-image -> error', 0xFFFFFE00095EAD00, 0xB40026A0)
chk('I12 retry bound cmp #2', 0xFFFFFE00095EB088, 0x7100095F)
chk('I13 retry counter dev+0x400', 0xFFFFFE00095EB078, 0xB944026A)

# --- J. translator whitelist (pass9b): owned windows only ---
chk('J1 ldr FWIM params dev+0x978', 0xFFFFFE00095EBA4C, 0xF944BE88)
chk('J2 cbz params -> fail', 0xFFFFFE00095EBA50, 0xB4000128)
chk('J3 ldr dva +0x18', 0xFFFFFE00095EBA54, 0xF9400D0A)
chk('J4 ldr config size +312', 0xFFFFFE00095EBA64, 0xB941396B)
chk('J5 ldr IPC params dev+0x988', 0xFFFFFE00095EBA74, 0xF944C688)
chk('J6 cbz IPC -> skip', 0xFFFFFE00095EBA78, 0xB4000108)
chk('J7 ldr IPC word0 size', 0xFFFFFE00095EBA88, 0xF940010B)
chk('J8 fail return x0=0', 0xFFFFFE00095EBAD0, 0xD2800000)
chk('J9 ldr kva +0x38', 0xFFFFFE00095EBBDC, 0xF9401D08)
chk('J10 host = off + kva', 0xFFFFFE00095EBBE0, 0x8B080120)
chk('J11 image ptr -> dev+0x3FC0', 0xFFFFFE00095EACFC, 0xF91FE260)
chk('J12 shifted FWIM -> dev+0x3FC8', 0xFFFFFE00095EACF0, 0xB93FCA69)

# --- K. >=0x21 fail-closed epilogue (pass9b correction) ---
chk('K1 b -> vm 0x95ea330 epilogue', 0xFFFFFE00095EA2C4, 0x1400001B)
chk('K2 sub w21,#0x1e (0xE00002BC)', 0xFFFFFE00095EA330, 0x51007AB5)
chk('K3 stack-canary ldur', 0xFFFFFE00095EA334, 0xF85A03A8)
chk('K4 mov x0,x21 (return code)', 0xFFFFFE00095EA34C, 0xAA1503E0)
chk('K5 retab', 0xFFFFFE00095EA36C, 0xD65F0FFF)
chk('K6 poll A timeout -> epilogue', 0xFFFFFE00095EB178, 0x17FFFC6F)

print('ALL OK' if ok else 'SOME FAILED')
sys.exit(0 if ok else 1)
