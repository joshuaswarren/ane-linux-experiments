#!/usr/bin/env python3
"""Pair every PAC vmethod call (blraa/braa) in a disassembly listing with the
vtable slot it loads, the object register, and the PAC diversity constant.

Reads the output of disasm_range.py on stdin. Understands these idioms:
  ldr x16, [xN]              ; vptr load
  add x16, x16, #slot        ; slot select
  ldr xN, [xM, #slot]!       ; pre-indexed slot load
  ldr xN, [xM, #slot]        ; plain slot load
  movk xK, #imm, lsl #48     ; PAC diversity salt
  autda/autdb/autia          ; auth
  blraa x8, x16 / braa ...
"""
import re, sys, bisect

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
        return '??'
    nm = names[addrs[i]]
    off = vm - addrs[i]
    return f'{nm}{"+0x%x" % off if off else ""}'


INSN = re.compile(r'^\s*([0-9a-f]{16}):\t([0-9a-f]{8})\s+(\S+)\s*(.*)$')


def main():
    window = []
    for line in sys.stdin:
        m = INSN.match(line)
        if not m:
            continue
        vm, raw, op, rest = int(m.group(1), 16), m.group(2), m.group(3), m.group(4)
        rest = rest.split('//@')[0].split('//')[0].strip()
        window.append((vm, raw, op, rest))
        if op in ('blraa', 'braa', 'blraaz', 'braaz', 'blr', 'bl'):
            if op == 'bl':
                t = int(rest.split()[0], 16)
                t = t + 0xFFFFFE0007004000 if t < 0x7744000 else t
                print(f'{vm:#x} bl  -> {fname(t)}')
            else:
                idx = rest.split()[0]  # branch target register
                slot = None; obj = None; salt = None; authop = None
                movs = {}   # reg -> small immediate
                built = {}  # destreg -> (slot, basereg)
                IM = r'(0x[0-9a-f]+|\d+)'

                def imm(s):
                    return int(s, 0)
                for vm2, _raw, op2, rest2 in window[:-1][-24:]:
                    text = op2 + ' ' + rest2
                    mm = re.match(rf'mov (x\d+), #{IM}$', text)
                    if mm:
                        v = imm(mm.group(2))
                        if v % 8 == 0 and v <= 0x1000:
                            movs[mm.group(1)] = v
                        continue
                    mm = re.match(rf'add (x\d+), (x\d+), #{IM}$', text)
                    if mm:
                        v = imm(mm.group(3))
                        if v % 8 == 0 and v <= 0x1000:
                            built[mm.group(1)] = (v, mm.group(2))
                        continue
                    mm = re.match(r'add (x\d+), (x\d+), (x\d+)$', text)
                    if mm and mm.group(3) in movs:
                        built[mm.group(1)] = (movs[mm.group(3)], mm.group(2))
                        continue
                    mm = re.match(rf'ldr (x\d+), \[(x\d+), #{IM}\]!?$', text)
                    if mm:
                        v = imm(mm.group(3))
                        if v % 8 == 0 and v <= 0x1000:
                            slot = v; obj = mm.group(2)
                        continue
                    mm = re.match(r'ldr (x\d+), \[(x\d+)\]$', text)
                    if mm and mm.group(2) in built:
                        slot, obj = built[mm.group(2)]
                        continue
                    mm = re.match(r'movk (x\d+), #(0x[0-9a-f]+), lsl #48', text)
                    if mm and salt is None:
                        salt = int(mm.group(2), 16)
                    if op2 in ('autda', 'autdb', 'autia', 'autib') and authop is None:
                        authop = op2
                print(f'{vm:#x} {op} {rest.split()[0]:6} slot={slot and hex(slot)} obj={obj} salt={salt and hex(salt)} auth={authop}')


if __name__ == '__main__':
    main()
