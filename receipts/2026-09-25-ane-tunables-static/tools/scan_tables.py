#!/usr/bin/env python3
"""Generic XNU tunable-table scanner.

Validated record layout on T8103 mac13g (jwm1 stub cache): 20-byte records
  {u32 zero, u32 offset (bit30/31 flags, low bits = register offset),
   u32 clear, u32 set, u32 zero}
terminator record = {0, 0xffffffff, 0xffffffff, 0xffffffff, 0}.
Walks back from every terminator through plausible records.
"""
import struct, sys

def load_macho_segments(data):
    ncmds, = struct.unpack_from("<I", data, 16)
    off = 32
    segs = []
    while off < 32 + ncmds * 8 and off < len(data):
        cmd, csize = struct.unpack_from("<II", data, off)
        if cmd == 0x19:
            name = data[off+8:off+24].rstrip(b"\0").decode()
            vm, msz, fo, fsz = struct.unpack_from("<QQQQ", data, off+24)
            segs.append((name, vm, msz, fo, fsz))
        off += csize
    return segs

def fo2va(segs, fo):
    for name, vm, msz, f, fsz in segs:
        if f <= fo < f + fsz:
            return vm + (fo - f), name
    return None, None

TERM = struct.pack("<IIIII", 0, 0xffffffff, 0xffffffff, 0xffffffff, 0)

def plausible_record(data, fo):
    if fo < 0:
        return None
    w0, off, clr, setv, w4 = struct.unpack_from("<IIIII", data, fo)
    if w0 != 0 or w4 != 0:
        return None
    if off == 0xffffffff:
        return None
    eff = off & 0x0fffffff
    if off & 0x0fff0000 or eff > 0x800000:
        return None
    return (off, clr, setv)

def scan(path, min_entries=4):
    data = open(path, "rb").read()
    segs = load_macho_segments(data)
    print(f"# {path} ({len(data)} bytes)")
    tables = []
    start = 0
    while True:
        i = data.find(TERM, start)
        if i < 0:
            break
        start = i + 4
        entries = []
        fo = i - 20  # terminator record precedes
        while True:
            e = plausible_record(data, fo)
            if e is None:
                break
            entries.append(e)
            fo -= 20
        entries.reverse()
        if len(entries) >= min_entries:
            va, seg = fo2va(segs, fo + 20)
            tables.append((fo + 20, va, seg, entries))
    for fo, va, seg, entries in tables:
        print(f"TABLE file={fo:#x} va={va:#x} seg={seg} entries={len(entries)}")
        for off, clr, setv in entries:
            print(f"    {{ {off:#x}, {clr:#x}, {setv:#x} }}")
    print(f"# {len(tables)} tables >= {min_entries} entries")
    return tables

if __name__ == "__main__":
    scan(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4)
