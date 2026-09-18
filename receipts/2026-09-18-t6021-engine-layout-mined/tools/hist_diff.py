#!/usr/bin/env python3
"""Histogram of effective immediates in __text code for two Mach-Os."""
import struct, sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from collections import Counter

def text_sections(path):
    d = open(path, "rb").read()
    _, _, _, _, ncmds, sizeofcmds, _, _ = struct.unpack_from("<IIIIIIII", d, 0)
    off = 32
    out = []
    for _ in range(ncmds):
        cmd, cs = struct.unpack_from("<II", d, off)
        if cmd == 0x19:
            segname = d[off+8:off+24].rstrip(b"\0").decode(errors="replace")
            nsects = struct.unpack_from("<I", d, off+64)[0]
            so = off + 72
            for _ in range(nsects):
                sect = d[so:so+16].rstrip(b"\0").decode(errors="replace")
                addr, size = struct.unpack_from("<QQ", d, so+32)
                foff = struct.unpack_from("<I", d, so+48)[0]
                if sect == "__text":
                    out.append((addr, d[foff:foff+size]))
                so += 80
        off += cs
    return out

def eff_imms(op_str):
    toks = op_str.split(", ")
    out = []
    i = 0
    while i < len(toks):
        t = toks[i].strip()
        if t.startswith("#"):
            try:
                v = int(t[1:], 0)
                sh = 0
                if i + 1 < len(toks) and toks[i+1].strip().startswith("lsl"):
                    sh = int(toks[i+1].split("#")[1], 0)
                out.append((v << sh, toks[i+1].strip() if i+1 < len(toks) else ""))
            except ValueError:
                pass
        i += 1
    return out

def hist(path, minval=0x1000):
    c = Counter()
    for addr, code in text_sections(path):
        md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        for ins in md.disasm(code, addr):
            if "#" not in ins.op_str:
                continue
            for eff, shift in eff_imms(ins.op_str):
                if eff >= minval:
                    c[(ins.mnemonic, eff, shift)] += 1
    return c

a = hist(sys.argv[1]); b = hist(sys.argv[2])
keys = sorted(set(a) | set(b), key=lambda k: -max(a.get(k,0), b.get(k,0)))
print(f"{'(mnemonic, imm, lsl)':60} {'H13':>6} {'H14J':>6}")
for k in keys:
    va, vb = a.get(k,0), b.get(k,0)
    if max(va,vb) >= 2:
        print(f"{str(k):60} {va:6d} {vb:6d}")
