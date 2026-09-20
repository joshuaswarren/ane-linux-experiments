#!/usr/bin/env python3
"""Disassemble a VM range of the pinned KC with symbol annotation.

file_offset = vm - 0xfffffe0007004000 (flat KC layout, verified against all
nine LC_SEGMENT_64 vm/file pairs). objdump cannot take VMs > 2^63, so we map
the file at vma 0 (addresses == file offsets) and rebase + annotate in Python.

Usage: disasm_range.py <vm_start> <vm_end>   (full 64-bit VMs)
"""
import subprocess, sys, bisect, re

KC = '/tmp/kernelcache.mac14j.raw'
VM_BASE = 0xFFFFFE0007004000
HERE = __file__.rsplit('/', 1)[0]


def load_syms():
    addrs, names = [], {}
    with open(HERE + '/../all_kext.syms') as f:
        for line in f:
            v, n = line.split(None, 1)
            addrs.append(int(v, 16))
            names[int(v, 16)] = n.strip()
    addrs.sort()
    return addrs, names


def main():
    lo = int(sys.argv[1], 0)
    hi = int(sys.argv[2], 0)
    addrs, names = load_syms()
    r = subprocess.run(
        ['aarch64-linux-gnu-objdump', '-D', '-b', 'binary', '-m', 'aarch64',
         '--adjust-vma', '0',
         '--start-address', hex(lo - VM_BASE), '--stop-address', hex(hi - VM_BASE),
         KC],
        capture_output=True, text=True, check=True)
    out = []
    for line in r.stdout.splitlines():
        m = re.match(r'^\s*([0-9a-f]{5,16}):\t', line)
        if m:
            foff = int(m.group(1), 16)
            vm = VM_BASE + foff
            line = line.replace(m.group(1) + ':', f'{vm:016x}:', 1)
            # annotate branch targets (raw file-offset form from objdump)
            for tok in re.split(r'[\s,\[\]]+', line):
                if tok.startswith('0x') and len(tok) >= 5:
                    try:
                        t = int(tok, 16)
                    except ValueError:
                        continue
                    vm_t = t + VM_BASE if t < 0x7744000 else t
                    if VM_BASE <= vm_t <= VM_BASE + 0x7744000:
                        i = bisect.bisect_right(addrs, vm_t) - 1
                        if i >= 0 and vm_t - addrs[i] < 0x800:
                            nm = names[addrs[i]]
                            suffix = '' if vm_t == addrs[i] else f'+{vm_t-addrs[i]:#x}'
                            line += f'   ; -> {nm[:120]}{suffix}'
                        break
        out.append(line)
    print('\n'.join(out))


if __name__ == '__main__':
    main()
