import re
import struct
import sys

import capstone

md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
md.detail = False
md.skipdata = True
pats = {
    "scratch/0x184xxxx": re.compile(r"#0x184[0-9a-f]?$|#0x1840"),
    "asc/0x1408": re.compile(r"#0x1408|#0x140"),
    "0x2006": re.compile(r"#0x2006"),
    "0x804": re.compile(r"#0x804$"),
    "rvbar 0x105": re.compile(r"#0x105"),
}
for path in sys.argv[1:]:
    d = open(path, "rb").read()
    hdr = struct.unpack("<8I", d[:32])
    off = 32
    text = None
    for _ in range(hdr[4]):
        cmd, cs = struct.unpack("<2I", d[off:off + 8])
        if cmd == 0x19 and d[off + 8:off + 14] == b"__TEXT":
            vm, vs, fo, fs = struct.unpack("<4Q", d[off + 24:off + 56])
            text = (vm, fo, fs)
        off += cs
    vm, fo, fs = text
    ins = list(md.disasm(d[fo:fo + fs], vm))
    print("=====", path, "instructions", len(ins))
    for label, rx in pats.items():
        hits = [i for i in ins if i.mnemonic in ("movz", "movk", "mov", "orr", "adrp", "add") and rx.search(i.op_str)]
        print(" ", label, len(hits), [f"{i.address:#x}:{i.mnemonic} {i.op_str}" for i in hits[:6]])
