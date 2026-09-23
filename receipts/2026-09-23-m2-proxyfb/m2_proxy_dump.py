#!/usr/bin/env python3
# Read-only: chip ID, ADT ane0 segments, and the preloaded ANE firmware bytes.
import hashlib
import os
import struct
import sys
import time

os.environ.setdefault("M1N1DEVICE", "/dev/ttyACM0")
OUT = os.path.join(os.environ.get("M2OUT", "$HOME/m2proxy"), "dump-" + time.strftime("%H%M%S"))
os.makedirs(OUT, exist_ok=True)

from m1n1.setup import *  # noqa: E402,F401,F403  (connects: p, u, iface)

log = open(os.path.join(OUT, "log.txt"), "w")


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    log.write(s + "\n")
    log.flush()


say("chipid", hex(p.get_chipid()))
p.nop()
say("nop ok")

adt = u.adt
node = None
for path in ("/arm-io/ane0", "/arm-io/ane"):
    if path.split("/")[-1] in adt["arm-io"]:
        node = adt[path]
        say("ane node", path)
        break
if node is None:
    say("no ane node in ADT")
    sys.exit(1)

for k in ("compatible", "pre-loaded", "firmware-name", "segment-names", "reg", "clock-gates",
          "power-gates"):
    say(" ", k, "=", node.getprop(k))

raw = node.getprop("segment-ranges")
segs = []
if isinstance(raw, (bytes, bytearray)):
    for off in range(0, len(raw) - len(raw) % 32, 32):
        phys, iova, remap, size, unk = struct.unpack_from("<QQQII", raw, off)
        segs.append((phys, iova, remap, size))
        say(f"  seg phys {phys:#x} iova {iova:#x} remap {remap:#x} size {size:#x} unk {unk:#x}")
else:
    say("  segment-ranges not bytes:", raw)

mm = adt["chosen"]["memory-map"]
for k, v in mm._properties.items():
    if k != "name":
        say("  memory-map", k, v)

addrs = [(f"seg{i}", s[0], s[3]) for i, s in enumerate(segs)]
addrs += [("mac_text", 0x1000092C000, 0xE8000), ("mac_data", 0x1000150C000, 0x284000)]
for name, pa, size in addrs:
    words = [p.read32(pa + 4 * i) for i in range(16)]
    say(f"{name} {pa:#x}:", " ".join(f"{w:08x}" for w in words))
    if words[0] == 0x14000081:
        say(f"  {name}: reset branch 0x14000081 at offset 0")
    data = iface.readmem(pa, size)
    path = os.path.join(OUT, f"{name}-{pa:x}.bin")
    open(path, "wb").write(data)
    say(f"  saved {path} {len(data)} B sha256 {hashlib.sha256(data).hexdigest()}")

say("done", OUT)
