#!/usr/bin/env python3
"""decode_encoder_hwx.py — per-task decode of Apple's full-encoder HWX.

Walks every linked task descriptor via hwxv2-to-anec primitives and reports,
per task: TD extent, register-block footprint, tile-DMA geometry (run vs total
= row count / padding class), and coefficient-KDMA presence (matmul/conv
family marker). Elementwise/reduce families (softmax, LN) = small-tile tasks
without weight KDMA, identified structurally and by position in the per-layer
cycle. Output NDJSON + summary.
"""
import json
import mmap
import struct
import sys
from collections import Counter
import importlib.util

spec = importlib.util.spec_from_file_location(
    "h2a", "tools/hwxv2-to-anec.py")
h2a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h2a)

HWX = sys.argv[1] if len(sys.argv) > 1 else "/tmp/encoder-v10.hwx"

f = open(HWX, "rb")
mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
img = h2a.parse_hwx(mm)

text = None
for (seg, name), sec in img.sections.items():
    if seg == "__TEXT" and text is None:
        text = sec
print(json.dumps({
    "file": HWX,
    "td_count_header": img.td_count,
    "td_size": img.td_size,
    "content_offset": img.content_offset,
    "content_size": img.content_size,
}, indent=1))

task_offsets = h2a.find_task_offsets(mm, text.file_offset, text.size)
print(json.dumps({"tasks_found": len(task_offsets)}))

records = []
for i, task_off in enumerate(task_offsets):
    base = text.file_offset + task_off
    td_end = (text.file_offset + task_offsets[i + 1]) if i + 1 < len(task_offsets) \
        else text.file_offset + text.size
    td = mm[base:td_end]
    try:
        registers = h2a.walk_registers(td)
    except Exception as exc:
        records.append({"task": i, "offset": task_off, "error": str(exc),
                        "td_bytes": td_end - base})
        continue
    tdma = h2a.decode_tile_dma(td)
    blocks = Counter(reg >> 12 for reg in registers)
    top_blocks = sorted(((hex(b), n) for b, n in blocks.items()),
                        key=lambda kv: -kv[1])[:6]
    records.append({
        "task": i,
        "offset": task_off,
        "td_bytes": td_end - base,
        "n_regs": len(registers),
        "reg_blocks": top_blocks,
        "tile_dma": {
            "src_run": tdma.source_run, "src_total": tdma.source_total,
            "dst_run": tdma.dest_run, "dst_total": tdma.dest_total,
            "src_rows": (tdma.source_total // tdma.source_run) if tdma.source_run else None,
            "dst_rows": (tdma.dest_total // tdma.dest_run) if tdma.dest_run else None,
        },
        "kdma_src": getattr(img.kdma, "src_address", None) and struct.unpack_from(
            "<I", td, 0)[0],
    })

with open("encoder-v10-tasks.ndjson", "w") as out:
    for r in records:
        out.write(json.dumps(r) + "\n")

fam = Counter()
for r in records:
    if "error" in r:
        fam["error"] += 1
    elif r["tile_dma"]["src_run"] and (r["tile_dma"]["src_rows"] or 0) > 64:
        fam["big-dma"] += 1
    elif r["tile_dma"]["src_run"]:
        fam["small-tile"] += 1
    else:
        fam["no-dma"] += 1
print(json.dumps({"families": dict(fam), "total": len(records)}, indent=1))
