import re
import struct
import sys

import capstone


def load(path):
    return open(path, "rb").read()


def macho(d):
    hdr = struct.unpack("<8I", d[:32])
    ncmds = hdr[4]
    off = 32
    segs, entry, extra = [], None, []
    for _ in range(ncmds):
        cmd, cs = struct.unpack("<2I", d[off:off + 8])
        if cmd == 0x19:
            name = d[off + 8:off + 24].split(b"\0")[0].decode()
            vmaddr, vmsize, fileoff, filesize = struct.unpack("<4Q", d[off + 24:off + 56])
            nsects = struct.unpack("<I", d[off + 64:off + 68])[0]
            sects = []
            so = off + 72
            for _s in range(nsects):
                sn = d[so:so + 16].split(b"\0")[0].decode()
                saddr, ssize = struct.unpack("<2Q", d[so + 32:so + 48])
                sects.append((sn, saddr, ssize))
                so += 80
            segs.append((name, vmaddr, vmsize, fileoff, filesize, sects))
        elif cmd == 0x5:
            flavor, count = struct.unpack("<2I", d[off + 8:off + 16])
            regs = struct.unpack("<%dQ" % (count // 2), d[off + 16:off + 16 + count * 4])
            entry = regs[32] if len(regs) > 32 else None  # pc after x0..x28, fp, lr, sp
            extra.append(("unixthread", flavor, count, [hex(r) for r in regs[28:34]]))
        else:
            extra.append((hex(cmd), cs))
        off += cs
    return hdr, segs, entry, extra


def words(d, base_off, n):
    return [struct.unpack("<I", d[base_off + 4 * i:base_off + 4 * i + 4])[0] for i in range(n)]


def disas(d, fileoff, vmaddr, count):
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    return list(md.disasm(d[fileoff:fileoff + 4 * count], vmaddr))


for name in sys.argv[1:]:
    d = load(name)
    hdr, segs, entry, extra = macho(d)
    print("=====", name, len(d), hex(len(d)))
    print("cputype", hex(hdr[1]), "cpusub", hex(hdr[2]), "filetype", hdr[3], "flags", hex(hdr[6]))
    for s in segs:
        print("SEG", s[0], "vm", hex(s[1]), hex(s[2]), "file", hex(s[3]), hex(s[4]), "sects", [(a, hex(b), hex(c)) for a, b, c in s[5]])
    print("extra", extra)
    print("entry", hex(entry) if entry is not None else None)
    # strings of interest
    strs = sorted(set(m.group().decode() for m in re.finditer(rb"[ -~]{8,}", d)))
    keys = [s for s in strs if re.search(r"RTKit Version|IPC |FWIM|Ipc|Version|SCRATCH|PowerControl|build|selene|styx|eos|2026|2023|2022|2021|2024", s, re.I) and "/" not in s[:2]]
    for s in keys[:30]:
        print("  STR", s[:110])
    # literal constants: movz/movk pairs for the ready code and the wake word as raw 32-bit
    for label, val in (("READY 0x08042006", 0x08042006), ("WAKE 0xf7fbdff9", 0xF7FBDFF9), ("0x01ff01ff", 0x01FF01FF)):
        raw = struct.pack("<I", val)
        hits = [m.start() for m in re.finditer(re.escape(raw), d)]
        print("  literal", label, "hits at", [hex(h) for h in hits[:6]])
    # instruction-level: movz w,#0x2006 ... movk lsl 16 #0x804
    ins = []
    if segs:
        text = segs[0]
        ins = disas(d, text[3], text[1], text[4] // 4)
    ready = [i for i in ins if i.mnemonic in ("movz", "movk") and ("#0x2006" in i.op_str)]
    ready2 = [i for i in ins if i.mnemonic == "movk" and "#0x804" in i.op_str]
    wake1 = [i for i in ins if i.mnemonic in ("movz", "movk") and ("#0xdff9" in i.op_str or "#0xf7fb" in i.op_str)]
    print("  code hits movz/movk #0x2006:", [hex(i.address) for i in ready][:6], "movk #0x804:", [hex(i.address) for i in ready2][:6], "wake halves:", [hex(i.address) for i in wake1][:6])
    if entry is not None and segs:
        t = segs[0]
        fo = t[3] + (entry - t[1])
        print("  entry code:")
        for i in disas(d, fo, entry, 24):
            print("   ", hex(i.address), i.mnemonic, i.op_str)
