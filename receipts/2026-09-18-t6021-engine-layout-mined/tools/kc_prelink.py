#!/usr/bin/env python3
"""Extract kext records from a prelink-style kernel collection's __PRELINK_INFO."""
import struct, sys, plistlib, json

def sections(data, off_segs_limit):
    """yield (segname, sectname, addr, size, offset)"""
    magic, cputype, cpusub, filetype, ncmds, sizeofcmds, flags, res = struct.unpack_from("<IIIIIIII", data, 0)
    off = 32
    while off < min(32 + sizeofcmds, len(data)):
        cmd, cmdsize = struct.unpack_from("<II", data, off)
        if cmd == 0x19:
            segname = data[off+8:off+24].rstrip(b"\0").decode(errors="replace")
            nsects = struct.unpack_from("<I", data, off+64)[0]
            so = off + 72
            for i in range(nsects):
                sectname = data[so:so+16].rstrip(b"\0").decode(errors="replace")
                s = data[so+16:so+32].rstrip(b"\0").decode(errors="replace")
                addr, size = struct.unpack_from("<QQ", data, so+32)
                offset = struct.unpack_from("<I", data, so+48)[0]
                yield (segname, s, addr, size, offset)
                so += 80
        off += cmdsize

def main(path, out_json):
    with open(path, "rb") as f:
        data = f.read()
    for seg, sect, addr, size, offset in sections(data, None):
        if seg == "__PRELINK_INFO" and sect == "__info":
            xml = data[offset:offset+size]
            pl = plistlib.loads(xml)
            print(f"__PRELINK_INFO.__info at {offset:#x} size {size} -> {len(pl)} entries")
            recs = {}
            for e in pl:
                bid = e.get("CFBundleIdentifier", "?")
                recs[bid] = {k: (v if isinstance(v, (int, str, bool)) else str(v))
                             for k, v in e.items() if k.startswith("_Prelink") or k == "CFBundleIdentifier"}
            with open(out_json, "w") as f:
                json.dump(recs, f, indent=1)
            hits = [b for b in recs if "ANE" in b.upper() or "H11" in b]
            for h in hits:
                print(json.dumps(recs[h], indent=1))
            print(f"total kext records: {len(recs)}; ANE-ish: {len(hits)}")
            return
    print("__PRELINK_INFO.__info not found")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
