import struct
import sys

import capstone

path, needle = sys.argv[1], sys.argv[2].encode()
d = open(path, "rb").read()
hdr = struct.unpack("<8I", d[:32])
off = 32
segs = []
symoff = nsyms = stroff = 0
for _ in range(hdr[4]):
    cmd, cs = struct.unpack("<2I", d[off:off + 8])
    if cmd == 0x19:
        name = d[off + 8:off + 24].split(b"\0")[0].decode()
        vm, vs, fo, fs = struct.unpack("<4Q", d[off + 24:off + 56])
        segs.append((name, vm, vs, fo, fs))
    if cmd == 0x2:
        symoff, nsyms, stroff, _ss = struct.unpack("<4I", d[off + 8:off + 24])
    off += cs
syms = []
for i in range(nsyms):
    n_strx, _t, _s, _dsc, val = struct.unpack("<IBBHQ", d[symoff + 16 * i:symoff + 16 * i + 16])
    syms.append((val, d[stroff + n_strx:d.index(b"\0", stroff + n_strx)].decode(errors="replace")))
syms.sort()


def sym_of(a):
    best = None
    for v, n in syms:
        if v <= a:
            best = (v, n)
        else:
            break
    return best


def va_of_file(fo_):
    for name, vm, vs, fo, fs in segs:
        if fo <= fo_ < fo + fs:
            return vm + (fo_ - fo)


pos = 0
addrs = []
while True:
    p = d.find(needle, pos)
    if p < 0:
        break
    addrs.append(va_of_file(p))
    pos = p + 1
print("string va:", [hex(a) for a in addrs if a is not None])
tv, tfo, tfs = next((s[1], s[3], s[4]) for s in segs if s[0] == "__TEXT")
md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
md.skipdata = True
ins = list(md.disasm(d[tfo:tfo + tfs], tv))
for target in [a for a in addrs if a is not None][:2]:
    for n, i in enumerate(ins):
        if i.mnemonic == "adr":
            try:
                tgt = int(i.op_str.split("#")[1], 16)
            except (IndexError, ValueError):
                continue
            if tgt == target:
                print("xref adr at", hex(i.address), "in", sym_of(i.address))
        if i.mnemonic == "adrp" and n + 2 < len(ins):
            try:
                page = int(i.op_str.split("#")[1], 16)
            except (IndexError, ValueError):
                continue
            for j in ins[n + 1:n + 3]:
                if j.mnemonic == "add" and "#0x" in j.op_str and (page + int(j.op_str.split("#0x")[-1], 16)) == target:
                    print("xref adrp+add at", hex(i.address), "in", sym_of(i.address))
