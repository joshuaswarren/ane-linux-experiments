#!/usr/bin/env python3
"""Dump LC_SYMTAB symbols from a Mach-O (nlist_64)."""
import struct, sys

def main(path, out=None):
    d = open(path, "rb").read()
    magic, cpu, cpusub, ft, ncmds, sizeofcmds, flags, res = struct.unpack_from("<IIIIIIII", d, 0)
    off = 32
    symtab = None
    for _ in range(ncmds):
        cmd, cs = struct.unpack_from("<II", d, off)
        if cmd == 0x2:  # LC_SYMTAB
            symoff, nsyms, stroff, strsize = struct.unpack_from("<IIII", d, off+8)
            symtab = (symoff, nsyms, stroff, strsize)
        off += cs
    if not symtab:
        print("no symtab"); return
    symoff, nsyms, stroff, strsize = symtab
    strs = d[stroff:stroff+strsize]
    syms = []
    for i in range(nsyms):
        n_strx, n_type, n_sect, n_desc, n_value = struct.unpack_from("<IBBQQ", d, symoff + i*16)
        end = strs.find(b"\0", n_strx)
        name = strs[n_strx:end].decode(errors="replace")
        if name:
            syms.append((n_value, name))
    print(f"{len(syms)} symbols")
    with open(out or (path + ".syms"), "w") as f:
        for v, n in sorted(set(syms)):
            f.write(f"{v:#016x} {n}\n")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
