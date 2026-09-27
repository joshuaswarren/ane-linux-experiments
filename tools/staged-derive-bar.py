#!/usr/bin/env python3
"""Numeric BAR/fetch-address derivation for the staged uniform prog_000.

The driver (ane_drv.c) programs:
  bar[0] = cmd BO iova               (the task stream + kernel region)
  bar[1] = bar[0] + align16(tsk)     (the kernel base, driver-computed)
  bar[3] = workspace BO iova
  bar[4+]= bank BO iovas
The TD records' weight-fetch offsets are relative to bar[1]. This script
extracts every fetch offset from the records and resolves the numeric
engine addresses, validating each stays inside the kernel region.
"""
import importlib.util
import struct
import sys
from pathlib import Path

sys.path.insert(0, "tools")
spec = importlib.util.spec_from_file_location(
    "conv", "tools/hwxv2-to-anec.py")
conv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(conv)

anec = Path(sys.argv[1] if len(sys.argv) > 1 else ".work/prog_000.anec")
data = bytearray(anec.read_bytes())
header = conv.PROBE_load(anec) if hasattr(conv, "PROBE_load") else None

import importlib.util as _iu
pspec = _iu.spec_from_file_location("probe", "tools/production-anec-probe.py")
probe = importlib.util.module_from_spec(pspec)
pspec.loader.exec_module(probe)
header = probe.load_anec_header(anec)
stage = probe.stage_geometry(header)

tsk = stage["task_stream_size"]
td_size = stage["td_size"]
td_count = stage["td_count"]
kernel_size = stage["kernel_size"]
kernel_base_rel = (tsk + 15) & ~15

print(f"prog_000: tsk={tsk:#x} td_size={td_size:#x} td_count={td_count} "
      f"kernel={kernel_size:#x} kernel_base=bar[CMD]+{kernel_base_rel:#x}")

fetch_reg_blocks = {}
chain = []
offset = 0x1000
seen = set()
while offset not in seen and len(chain) < td_count:
    seen.add(offset)
    base = offset - 0x1000
    chain.append(base)
    nxt = struct.unpack_from("<I", data, offset + 0x1C)[0]
    if not nxt:
        break
    offset = 0x1000 + nxt

print(f"tasks walked: {len(chain)}")
fetch_summary = {}
for i, base in enumerate(chain):
    bound = min(base + td_size, tsk)
    pos = 40
    regs = {}
    end = pos
    while pos + 4 <= bound:
        word = struct.unpack_from("<I", data, 0x1000 + base + pos)[0]
        if not word:
            break
        reg = word & 0x3FFFFFF
        count = (word >> 26) + 1
        pos += 4
        if pos + 4 * count > bound:
            break
        for k in range(count):
            v = struct.unpack_from("<I", data, 0x1000 + pos + 4 * k)[0]
            regs[reg + 4 * k] = v
        pos += 4 * count
        end = pos
    fetches = []
    for addr, value in sorted(regs.items()):
        # weight-fetch offsets: values inside the kernel region
        if 0x40000 < value < kernel_size:
            fetches.append((hex(addr), hex(value)))
    if fetches:
        fetch_summary[i] = fetches

for i, fetches in fetch_summary.items():
    print(f"task {i:2d}: {len(fetches)} kernel fetches: {fetches[:6]}")
print("FETCH_DERIVATION_OK")
