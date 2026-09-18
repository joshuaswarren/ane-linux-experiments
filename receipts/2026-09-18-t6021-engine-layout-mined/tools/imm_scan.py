#!/usr/bin/env python3
"""Disassemble Mach-O __text sections; find instructions with effective immediates
matching targets. Handles '<imm>, lsl #<sh>' forms and movz/movk chains."""
import struct, sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

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
                    out.append((f"{segname}.{sect}", addr, d[foff:foff+size]))
                so += 80
        off += cs
    return out

def main(path, targets):
    tset = set(targets)
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
                    out.append(v << sh)
                except ValueError:
                    pass
            i += 1
        return out

    for label, addr, code in text_sections(path):
        md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        n = 0
        for ins in md.disasm(code, addr):
            if "#" not in ins.op_str:
                continue
            for eff in eff_imms(ins.op_str):
                if eff in tset:
                    print(f"{eff:#x} {label} {ins.address:#x}: {ins.mnemonic} {ins.op_str}")
                    n += 1
                    if n > 60:
                        print(" ... truncated")
                        return

if __name__ == "__main__":
    main(sys.argv[1], [int(x, 0) for x in sys.argv[2:]])
