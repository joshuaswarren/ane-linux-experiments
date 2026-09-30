import struct
import sys

import capstone

path, pat = sys.argv[1], sys.argv[2]
d = open(path, "rb").read()
hdr = struct.unpack("<8I", d[:32])
off = 32
symoff = nsyms = stroff = strsize = 0
segs = []
for _ in range(hdr[4]):
    cmd, cs = struct.unpack("<2I", d[off:off + 8])
    if cmd == 0x2:
        symoff, nsyms, stroff, strsize = struct.unpack("<4I", d[off + 8:off + 24])
    if cmd == 0x19:
        name = d[off + 8:off + 24].split(b"\0")[0].decode()
        vm, vs, fo, fs = struct.unpack("<4Q", d[off + 24:off + 56])
        segs.append((name, vm, vs, fo, fs))
    off += cs
syms = []
for i in range(nsyms):
    n_strx, n_type, n_sect, n_desc, n_value = struct.unpack("<IBBHQ", d[symoff + 16 * i:symoff + 16 * i + 16])
    nm = d[stroff + n_strx:d.index(b"\0", stroff + n_strx)].decode(errors="replace")
    syms.append((n_value, nm))
syms.sort()
print("symbols", len(syms))
hits = [(a, n) for a, n in syms if pat in n]
for a, n in hits[:20]:
    print(hex(a), n)


def foff(va):
    for name, vm, vs, fo, fs in segs:
        if name == "__TEXT" and vm <= va < vm + fs:
            return fo + (va - vm)
    return None


if hits and len(sys.argv) > 3:
    a = hits[0][0]
    nxt = next((x for x, _ in syms if x > a), a + 0x400)
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    md.skipdata = True
    fo = foff(a)
    for i in md.disasm(d[fo:fo + min(nxt - a, int(sys.argv[3]))], a):
        print(f"  {i.address:#x}: {i.mnemonic} {i.op_str}")
