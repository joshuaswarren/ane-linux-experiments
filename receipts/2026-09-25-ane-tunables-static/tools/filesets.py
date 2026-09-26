#!/usr/bin/env python3
"""Parse LC_FILESET_ENTRY (kext) ranges from a kernelcache Mach-O and map
file offsets to kext install names."""
import struct, sys

LC_FILESET_ENTRY = 0x80000025

def filesets(data):
    ncmds, = struct.unpack_from("<I", data, 16)
    off = 32
    out = []
    while off < 32 + ncmds * 8 and off < len(data):
        cmd, csize = struct.unpack_from("<II", data, off)
        if cmd == LC_FILESET_ENTRY:
            # struct fileset_entry_command: cmd,cmdsize, entry_id offset+size
            # (LC_STR), content_vmaddr, content_fileoff
            idoff, idsize, vmaddr, fileoff = struct.unpack_from("<IIQQ", data, off+8)
            name = data[off+idoff: off+idoff+idsize].split(b"\0")[0].decode()
            out.append((name, vmaddr, fileoff))
        off += csize
    return out

def main(path, offsets):
    data = open(path, "rb").read()
    fs = filesets(data)
    print(f"# {len(fs)} fileset entries in {path}")
    for name, vm, fo in fs:
        print(f"  {name:60s} content_vmaddr={vm:#x} content_fileoff={fo:#x}")
    for off in offsets:
        owner = None
        best = -1
        for name, vm, fo in fs:
            if fo <= off and fo > best:
                best = fo; owner = name
        print(f"offset {off:#x} -> {owner}")

if __name__ == "__main__":
    main(sys.argv[1], [int(x, 16) for x in sys.argv[2:]])
