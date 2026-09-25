#!/usr/bin/env python3
"""Parse kext13.syms (chained-fixup-encoded) into file offsets + names."""
import sys
sys.path.insert(0, '/var/tmp/kext-re')
from kextmap import file_to_vm, TEXT_EXEC

def load_syms(path):
    syms = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        a, name = line.split(None, 1)
        v = int(a, 16)
        b = v.to_bytes(8, 'little')
        fo = int.from_bytes(b[2:6], 'little')     # file offset
        tag = int.from_bytes(b[6:8], 'little')    # section tag
        syms.append((fo, tag, name))
    return syms

if __name__ == '__main__':
    syms = load_syms('~/src/ane-linux-experiments/receipts/'
                     '2026-09-18-t6021-engine-layout-mined/w2/kext13.syms')
    from collections import Counter
    print(Counter(hex(t) for _, t, _ in syms))
    # functions in __TEXT_EXEC: file range 0x48000..0x13c000
    fns = sorted((fo, n) for fo, t, n in syms if 0x48000 <= fo < 0x13c000 and t == 0x40f)
    print(f"text functions: {len(fns)}")
    for fo, n in fns[:10]:
        vma, seg = file_to_vm(fo)
        print(hex(fo), hex(vma) if vma else '?', n[:70])
    # anchor check: aneCmdSend(EPvj...) expected vma 0x92AD5A8
    for fo, n in fns:
        if 'aneCmdSendEPvj' in n:
            print('aneCmdSend file', hex(fo), 'vma', hex(file_to_vm(fo)[0]), '(expected 0xfffffe00092ad5a8)')
        if 'doorBellRingEPv' in n:
            print('doorBellRing file', hex(fo), 'vma', hex(file_to_vm(fo)[0]))
        if '8ANE_InitEv' in n and 'os_log' not in n:
            print('ANE_Init file', hex(fo), 'vma', hex(file_to_vm(fo)[0]))
