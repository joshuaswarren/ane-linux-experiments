import struct, subprocess, sys
from pathlib import Path

SRC = Path("/tmp/fresh-net.hwx").read_bytes()
BASE = 0x1000 + 0x28
CONV_VALS = {0x114: 0, 0x118: 0, 0x11C: 0, 0x120: 0, 0x15C: 0x4144405,
             0x218: 0x10, 0x21C: 0x30, 0x220: 0x30, 0x224: 0x30, 0x258: 0xC1}

def build(patches, path):
    data = SRC[0x4000:0x4000 + 0x340]
    buf = bytearray(data)
    for off, val in patches.items():
        struct.pack_into("<I", buf, 0x28 + off, val)
    tiles = [1, 0, 0, 0, 1, 1] + [0] * 26
    nchw = [0] * (32 * 6)
    nchw[4*6:4*6+6] = [1, 3, 1, 1, 0x40, 0x40]
    nchw[5*6:5*6+6] = [1, 3, 1, 1, 0x40, 0x40]
    header = struct.pack("<QIIQQII32I192Q", 0x340, 0x274, 1, 0x274, 0xC0, 1, 1, *tiles, *nchw)
    header += b"\x00" * (0x1000 - len(header))
    Path(path).write_bytes(header + bytes(buf))

CASES = {
    "none": {},
    "fmtbits": {0x15C: 0x4144405, 0x258: 0xC1},
    "eng114": {k: CONV_VALS[k] for k in (0x114, 0x118, 0x11C, 0x120)},
    "eng218": {k: CONV_VALS[k] for k in (0x218, 0x21C, 0x220, 0x224)},
    "all": dict(CONV_VALS),
}
for name, patches in CASES.items():
    path = f"/tmp/fresh-bisect-{name}.ane"
    build(patches, path)
    out = subprocess.run(
        ["python3", "/tmp/run-anec.py", path],
        env={"PYTHONPATH": "/home/joshuawarren/src/eiln-ane/bindings/python/python",
             "PATH": "/usr/bin:/bin", "HOME": "/home/joshuawarren"},
        capture_output=True, text=True, timeout=60,
    )
    tail = [ln for ln in out.stdout.splitlines() if "exec_result" in ln or "output0_head" in ln]
    print(name, "->", " | ".join(tail) if tail else out.stderr.splitlines()[-1:])
