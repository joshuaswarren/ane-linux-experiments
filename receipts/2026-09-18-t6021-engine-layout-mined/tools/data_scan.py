#!/usr/bin/env python3
"""Scan Mach-O data sections for u32/u64 occurrences of target constants."""
import struct, sys

def sections(path):
    d = open(path, "rb").read()
    _, _, _, _, ncmds, sizeofcmds, _, _ = struct.unpack_from("<IIIIIIII", d, 0)
    off = 32
    segs = []
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
                if size and foff:
                    segs.append((segname, sect, addr, size, foff))
                so += 80
        off += cs
    return d, segs

def main(path, targets):
    d, segs = sections(path)
    tset = set(targets)
    for sg, st, addr, size, foff in segs:
        if st == "__text":
            continue
        blob = d[foff:foff+size]
        # u32 scan
        for i in range(0, len(blob)-3):
            v = struct.unpack_from("<I", blob, i)[0]
            if v in tset:
                print(f"u32 {sg}.{st} addr={addr+i:#x} off={foff+i:#x}: {v:#x}")
        # u64 scan (dedup with u32 prints acceptable noise; keep)
        for i in range(0, len(blob)-7):
            v = struct.unpack_from("<Q", blob, i)[0]
            if v in tset:
                print(f"u64 {sg}.{st} addr={addr+i:#x} off={foff+i:#x}: {v:#x}")

if __name__ == "__main__":
    main(sys.argv[1], [int(x, 0) for x in sys.argv[2:]])
