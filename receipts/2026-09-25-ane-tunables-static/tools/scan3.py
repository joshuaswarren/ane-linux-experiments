#!/usr/bin/env python3
"""Generic XNU tunable-table scanner, v3.

Validated layout: 16-byte records {off, clear, set, pad0} separated by a
4-byte zero word; table ends with separator + {ff,ff,ff,0} terminator.
Backward walk from each 16-byte terminator through (separator, record) steps.
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

TERM = struct.pack("<IIII", 0xffffffff, 0xffffffff, 0xffffffff, 0)
Z4 = b"\0\0\0\0"

def ok_entry(off):
    if off == 0xffffffff:
        return False
    eff = off & 0x0fffffff
    if off & 0x0fff0000 or eff > 0x800000:
        return False
    return True

def scan(path, min_entries=4):
    data = open(path, "rb").read()
    segs = load_macho_segments(data)
    print(f"# {path} ({len(data)} bytes)")
    tables = []
    start = 0
    terms = 0
    while True:
        i = data.find(TERM, start)
        if i < 0:
            break
        start = i + 4
        terms += 1
        if i < 24 or data[i-4:i] != Z4:
            continue
        entries = []
        ent = i - 20
        while ent >= 0:
            if data[ent-4:ent] != Z4:
                break
            off, clr, setv, pad = struct.unpack_from("<IIII", data, ent)
            if pad != 0 or not ok_entry(off):
                break
            entries.append((off, clr, setv))
            ent -= 20
        entries.reverse()
        if len(entries) >= min_entries:
            va, seg = fo2va(segs, ent + 20)
            tables.append((ent + 20, va, seg, entries))
    for fo, va, seg, entries in tables:
        print(f"TABLE file={fo:#x} va={va:#x} seg={seg} entries={len(entries)}")
        for off, clr, setv in entries:
            print(f"    {{ {off:#x}, {clr:#x}, {setv:#x} }}")
    print(f"# terminators={terms}; tables={len(tables)}")
    return tables

if __name__ == "__main__":
    scan(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4)
