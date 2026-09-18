#!/usr/bin/env python3
"""Find xrefs to a string in __cstring from __TEXT_EXEC code; dump surrounding code.
Also resolve adrp+add pairs to absolute addresses."""
import struct, sys, re
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

def load(path):
    d = open(path, "rb").read()
    _, _, _, _, ncmds, sizeofcmds, _, _ = struct.unpack_from("<IIIIIIII", d, 0)
    off = 32
    secs = {}
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
                    secs[f"{segname}.{sect}"] = (addr, size, d[foff:foff+size])
                so += 80
        off += cs
    return d, secs

def find_strings(secs, needle):
    hits = []
    for name, (addr, size, blob) in secs.items():
        if "cstring" not in name and "os_log" not in name:
            continue
        start = 0
        while True:
            i = blob.find(needle, start)
            if i < 0:
                break
            hits.append((name, addr + i, blob[max(0,i-4):i+len(needle)+48]))
            start = i + 1
    return hits

def main(path, needle):
    d, secs = load(path)
    hits = find_strings(secs, needle)
    for name, saddr, ctx in hits:
        print(f"string {needle!r} in {name} @ {saddr:#x}: {ctx[:60]!r}")
    if not hits:
        print("string not found"); return
    targets = {saddr for _, saddr, _ in hits}
    text = secs.get("__TEXT_EXEC.__text") or next(v for k, v in secs.items() if k.endswith(".__text"))
    taddr, tsize, tcode = text
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md.detail = False
    insns = list(md.disasm(tcode, taddr))
    adrp_reg = {}   # reg -> page addr
    xrefs = []
    for idx, ins in enumerate(insns):
        m = ins.mnemonic
        if m == "adrp":
            ops = ins.op_str.split(", ")
            try:
                adrp_reg[ops[0]] = int(ops[1].lstrip("#"), 0)
            except (ValueError, IndexError):
                pass
        elif m == "add":
            ops = ins.op_str.replace("]", "").split(", ")
            if len(ops) == 3 and ops[1] in adrp_reg and ops[2].startswith("#"):
                try:
                    a = adrp_reg[ops[1]] + int(ops[2].lstrip("#"), 0)
                    if a in targets:
                        xrefs.append(idx)
                except ValueError:
                    pass
        elif m in ("ldr", "ldrb", "str"):
            mm = re.match(r"(\w+), \[(\w+)\]$", ins.op_str)
            if mm and mm.group(2) in adrp_reg and adrp_reg[mm.group(2)] in targets:
                xrefs.append(idx)
    print(f"{len(xrefs)} xrefs")
    for idx in xrefs:
        lo = max(0, idx-40)
        hi = min(len(insns), idx+60)
        print(f"--- around {insns[idx].address:#x} ---")
        for i2 in range(lo, hi):
            mark = ">>" if i2 == idx else "  "
            print(f"{mark} {insns[i2].address:#x}: {insns[i2].mnemonic} {insns[i2].op_str}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2].encode())
