import struct
import sys

import capstone

path, disp = sys.argv[1], sys.argv[2]
d = open(path, "rb").read()
hdr = struct.unpack("<8I", d[:32])
off = 32
segs = []
sy = None
for _ in range(hdr[4]):
    cmd, cs = struct.unpack("<2I", d[off:off + 8])
    if cmd == 0x19:
        name = d[off + 8:off + 24].split(b"\0")[0].decode()
        vm, vs, fo, fs = struct.unpack("<4Q", d[off + 24:off + 56])
        segs.append((name, vm, vs, fo, fs))
    if cmd == 0x2:
        sy = struct.unpack("<4I", d[off + 8:off + 24])
    off += cs
so, ns, sto, _ss = sy
syms = []
for i in range(ns):
    n_strx, _t, _s, _dsc, val = struct.unpack("<IBBHQ", d[so + 16 * i:so + 16 * i + 16])
    syms.append((val, d[sto + n_strx:d.index(b"\0", sto + n_strx)].decode(errors="replace")))
syms.sort()


def sym_of(a):
    best = ("?", 0)
    for v, n in syms:
        if v <= a:
            best = (n, v)
        else:
            break
    return best


tv, tfo, tfs = next((s[1], s[3], s[4]) for s in segs if s[0] == "__TEXT")
md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
md.skipdata = True
for i in md.disasm(d[tfo:tfo + tfs], tv):
    if i.mnemonic in ("ldrb", "strb", "ldr", "str") and f"#{disp}]" in i.op_str:
        n, v = sym_of(i.address)
        print(f"{i.address:#x} {i.mnemonic} {i.op_str}  in {n} +{i.address - v:#x}")
