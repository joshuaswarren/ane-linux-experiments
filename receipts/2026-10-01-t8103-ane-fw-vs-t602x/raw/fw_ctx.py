import re
import struct
import sys

import capstone

md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
md.skipdata = True


def text_of(d):
    hdr = struct.unpack("<8I", d[:32])
    off = 32
    for _ in range(hdr[4]):
        cmd, cs = struct.unpack("<2I", d[off:off + 8])
        if cmd == 0x19 and d[off + 8:off + 14] == b"__TEXT":
            vm, vs, fo, fs = struct.unpack("<4Q", d[off + 24:off + 56])
            return vm, fo, fs
        off += cs
    return None


path, first = sys.argv[1], sys.argv[2]
vm, fo, fs = text_of(open(path, "rb").read())
d = open(path, "rb").read()
ins = list(md.disasm(d[fo:fo + fs], vm))
idx = {i.address: n for n, i in enumerate(ins)}
# READY: 'mov w2, #0x2006' followed within 4 insns by movk w2, #0x804, lsl #16 -> value 0x08042006
def show(center, before=6, after=14):
    n = idx[center]
    for i in ins[max(0, n - before):n + after]:
        mark = "=>" if i.address == center else "  "
        print(f"  {mark} {i.address:#x}: {i.mnemonic} {i.op_str}")


print("=====", path)
sites = [i for i in ins if i.mnemonic in ("mov", "movz") and i.op_str.endswith("#0x2006")]
for s in sites:
    n = idx[s.address]
    window = ins[n:n + 6]
    if any(w.mnemonic == "movk" and "#0x804" in w.op_str for w in window):
        print(" READY-value site (0x2006 + movk #0x804):", hex(s.address))
        show(s.address)
wake = [i for i in ins if i.mnemonic in ("mov", "movz", "movk") and ("#0xdff9" in i.op_str or "#0xf7fb" in i.op_str)]
print(" wake halves:", [f"{i.address:#x} {i.mnemonic} {i.op_str}" for i in wake][:8])
if len(sys.argv) > 3:
    show(int(sys.argv[3], 16), 4, 12)
