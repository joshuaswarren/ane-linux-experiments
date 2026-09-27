#!/usr/bin/env python3
"""Offline: normalize a staged anec's task stream to a uniform stride.

Parses the original stream with full assertions, re-lays every task to a
uniform slot size (max extent rounded to 0x100), rewrites links, zero-fills
slot tails, and re-parses the result to prove records survived
byte-identical and the chain resolves in the same order.
"""
import hashlib
import importlib.util
import struct
import sys
from pathlib import Path

WORK = Path("/var/tmp/qc-gaps2")
sys.path.insert(0, str(WORK))
pspec = importlib.util.spec_from_file_location("probe", str(WORK / "production-anec-probe.py"))
probe = importlib.util.module_from_spec(pspec)
pspec.loader.exec_module(probe)
tspec = importlib.util.spec_from_file_location("sts", str(Path(__file__).parent / "staged-task-stream.py"))
sts = importlib.util.module_from_spec(tspec)
tspec.loader.exec_module(sts)


def normalize(path, out_path, stride):
    data = bytearray(Path(path).read_bytes())
    header = probe.load_anec_header(Path(path))
    stage = probe.stage_geometry(header)
    td_count = stage["td_count"]
    old_stream = stage["task_stream_size"]
    view = data[0x1000:0x1000 + old_stream]
    # chain walk (assertions inside normalize_stride re-walk too)
    chain = []
    offset = 0
    seen = set()
    while offset not in seen and len(chain) < td_count:
        seen.add(offset)
        chain.append(offset)
        nxt = struct.unpack_from("<I", view, offset + 0x1C)[0]
        if not nxt:
            break
        offset = nxt
    # per-task max record extent drives the stride
    max_end = 0
    for base in chain:
        bound = min(chain[chain.index(base) + 1], old_stream) \
            if chain.index(base) + 1 < len(chain) else old_stream
        _records, end, term, trunc = sts.parse_task(bytes(view), base, bound)
        max_end = max(max_end, end)
    if stride is None:
        stride = (max_end + 0xFF) & ~0xFF
    new_stream, mapping = sts.normalize_stride(bytes(view), chain, stride)
    # header update: task_stream_size (Q @16), td_size clamp no longer
    # needed at uniform stride; keep header td_size at the stride
    new_td_size = stride
    struct.pack_into("<I", data, 8, new_td_size)
    struct.pack_into("<Q", data, 16, len(new_stream))
    data[0x1000:0x1000 + old_stream] = new_stream
    # if the new stream is shorter/longer, splice correctly
    if len(new_stream) != old_stream:
        rest = bytes(data[0x1000 + old_stream:])
        data = data[:0x1000] + new_stream + rest
    out = Path(out_path)
    out.write_bytes(bytes(data))
    print(f"{path} -> stride {stride:#x} slots {len(chain)} "
          f"stream {old_stream:#x}->{len(new_stream):#x} "
          f"sha {hashlib.sha256(bytes(data)).hexdigest()[:16]}")


for arg in sys.argv[1:]:
    name = Path(arg).name
    normalize(arg, str(Path("/var/tmp/qc-gaps2/gapzero") / name), None)
print("NORMALIZED")
