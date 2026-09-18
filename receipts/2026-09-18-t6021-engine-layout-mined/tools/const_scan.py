#!/usr/bin/env python3
"""Disassemble a Mach-O's __text with capstone; track movz/movk constant chains.
Report instructions/functions that construct target constants."""
import struct, sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

def sections(path):
    d = open(path, "rb").read()
    _, _, _, _, ncmds, sizeofcmds, _, _ = struct.unpack_from("<IIIIIIII", d, 0)
    off = 32
    segs = []
    for _ in range(ncmds):
        cmd, cs = struct.unpack_from("<II", d, off)
        if cmd == 0x19:
            segname = d[off+8:off+24].rstrip(b"\0").decode(errors="replace")
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<QQQQ", d, off+24)
            nsects = struct.unpack_from("<I", d, off+64)[0]
            so = off + 72
            for _ in range(nsects):
                sect = d[so:so+16].rstrip(b"\0").decode(errors="replace")
                addr, size = struct.unpack_from("<QQ", d, so+32)
                foff = struct.unpack_from("<I", d, so+48)[0]
                segs.append((segname, sect, addr, size, foff, d[foff:foff+size] if foff and size else b""))
                so += 80
        off += cs
    return d, segs

def scan(path, targets):
    d, segs = sections(path)
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md.detail = False
    hits = {}
    text = next(((addr, code) for sg, st, addr, size, fo, code in segs if st == "__text"), None)
    if not text:
        print("no __text"); return
    addr, code = text
    regs = {}
    for ins in md.disasm(code, addr):
        m = ins.mnemonic
        if m in ("movz", "mov"):
            ops = ins.op_str.split(", ")
            if len(ops) == 3 and ops[2].startswith("#"):
                try:
                    v = int(ops[2][1:].split("lsl")[0].strip(), 0)
                    sh = 0
                    if "lsl" in ops[2]:
                        sh = int(ops[2].split("lsl")[1].strip().lstrip("#"), 0)
                    regs[ops[0]] = (v << sh, ins.address)
                except ValueError:
                    pass
        elif m == "movk":
            ops = ins.op_str.split(", ")
            if len(ops) == 4 and ops[0] in regs:
                try:
                    v = int(ops[1].lstrip("#").split("lsl")[0].strip(), 0)
                    sh = 0
                    if "lsl" in ops[3]:
                        sh = int(ops[3].split("lsl")[1].strip().lstrip("#"), 0)
                    base, _ = regs[ops[0]]
                    regs[ops[0]] = (base | (v << sh), ins.address)
                    cur = regs[ops[0]][0]
                    if cur in targets:
                        hits.setdefault(cur, []).append((ins.address, ins.mnemonic, ins.op_str))
                except ValueError:
                    pass
    for t in sorted(targets):
        lst = hits.get(t, [])
        print(f"const {t:#x}: {len(lst)} hits")
        for a, m, o in lst[:6]:
            print(f"   {a:#x}: {m} {o}")

if __name__ == "__main__":
    path = sys.argv[1]
    targets = set(int(x, 0) for x in sys.argv[2:])
    scan(path, targets)
