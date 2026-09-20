#!/usr/bin/env python3
"""Resolve bl targets that are PAC GOT trampolines in the ANE kext.

A trampoline is 4 instructions:
  adrp x17, <pg> ; add x17, x17, #<off> ; ldr x16, [x17] ; braa x16, x17
The real callee sits in the __DATA_CONST GOT word at vm(pg+off); on disk that
word is a DYLD_CHAINED_PTR_64_KERNEL_CACHE fixup whose target30 + __TEXT vm
is the callee.

Usage: resolve_tramp.py <bl_target_vm> [more...]
"""
import struct, sys, bisect

KC = '/tmp/kernelcache.mac14j.raw'
BASE = 0xFFFFFE0007004000

addrs = []
names = {}
with open(__file__.rsplit('/', 1)[0] + '/../all_kext.syms') as f:
    for line in f:
        v, n = line.split(None, 1)
        addrs.append(int(v, 16))
        names[int(v, 16)] = n.strip()
addrs.sort()


def fname(vm):
    i = bisect.bisect_right(addrs, vm) - 1
    if i < 0:
        return f'{vm:#x}??'
    off = vm - addrs[i]
    return f'{names[addrs[i]]}{"+0x%x" % off if off else ""}'


def decode_fixup(v):
    return v & 0x3FFFFFFF


def got_word(vm):
    d = open(KC, 'rb').read()
    fo = vm - BASE
    return struct.unpack_from('<Q', d, fo)[0]


def resolve_stub(vm):
    d = open(KC, 'rb').read()
    fo = vm - BASE
    w1, w2 = struct.unpack_from('<II', d, fo)
    if (w1 >> 24) != 0x90000000 | 0 and (w1 >> 31) != 1:
        return None
    # adrp: op=1 immlo[2] 10000 immhi[19] Rd[5]
    rd = w1 & 0x1f
    immlo = (w1 >> 29) & 3
    immhi = (w1 >> 5) & 0x7ffff
    imm = (immhi << 2) | immlo
    if imm & (1 << 20):
        imm -= 1 << 21
    pg = ((vm >> 12) + imm) << 12
    if (w2 >> 24) != 0x91:  # add x17, x17, #off  (Rd=Rn=17)
        return None
    off = (w2 >> 10) & 0xfff
    got = pg + off
    word = got_word(got)
    tgt = BASE + decode_fixup(word)
    return got, tgt


def main():
    B = 0xFFFFFE0007004000
    for a in sys.argv[1:]:
        vm = int(a, 0)
        if vm < B:
            vm += B
        r = resolve_stub(vm)
        if not r:
            print(f'{vm:#x}: not a trampoline')
            continue
        got, tgt = r
        print(f'{vm:#x}: GOT {got:#x} -> {tgt:#x} {fname(tgt)}')


if __name__ == '__main__':
    main()
