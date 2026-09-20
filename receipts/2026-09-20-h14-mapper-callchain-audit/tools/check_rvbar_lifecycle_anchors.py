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

print('ALL OK' if ok else 'SOME FAILED')
sys.exit(0 if ok else 1)
