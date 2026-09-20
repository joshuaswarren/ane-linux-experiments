#!/usr/bin/env python3
"""Regression for the fixed nlist_64 parser (<IBBHQ>, 16 B) against known anchors.

Anchors were derived independently (capstone content traces + Main's raw
gMetaClass read) on AppleH11ANEInterface-10.19.2-mac14j-26A428:
  __ZN13OSValueObjectI28ANESharedMemorySurfaceParamsE10gMetaClassE = 0xfffffe000cb6e5e8
  __ZN13OSValueObjectI28ANESharedMemorySurfaceParamsE6createEv     = 0xfffffe00095f727c
  __ZTV13OSValueObjectI28ANESharedMemorySurfaceParamsE             = 0xfffffe000814d7d8

Run: python3 macho_syms_regression.py <kext_path>
"""
import struct
import sys

ANCHORS = {
    "__ZN13OSValueObjectI28ANESharedMemorySurfaceParamsE10gMetaClassE": 0xFFFFFE000CB6E5E8,
    "__ZN13OSValueObjectI28ANESharedMemorySurfaceParamsE6createEv": 0xFFFFFE00095F727C,
    "__ZTV13OSValueObjectI28ANESharedMemorySurfaceParamsE": 0xFFFFFE000814D7D8,
}


def main(path):
    d = open(path, "rb").read()
    ncmds = struct.unpack_from("<I", d, 16)[0]
    off = 32
    symtab = None
    for _ in range(ncmds):
        cmd, cs = struct.unpack_from("<II", d, off)
        if cmd == 0x2:
            symtab = struct.unpack_from("<IIII", d, off + 8)
        off += cs
    assert symtab, "no LC_SYMTAB"
    symoff, nsyms, stroff, strsize = symtab
    ok = 0
    seen = {}
    for i in range(nsyms):
        n_strx, n_type, n_sect, n_desc, n_value = struct.unpack_from("<IBBHQ", d, symoff + i * 16)
        e = d.find(b"\0", stroff + n_strx)
        name = d[stroff + n_strx:e].decode(errors="replace")
        if name:
            seen[name] = n_value
    for name, want in ANCHORS.items():
        got = seen.get(name)
        status = "OK" if got == want else "FAIL"
        if got == want:
            ok += 1
        print(f"{status} {name}: {hex(got) if got is not None else None} (expect {hex(want)})")
    total = len(ANCHORS)
    print(f"{ok}/{total} anchors")
    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    main(sys.argv[1])
