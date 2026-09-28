#!/usr/bin/env python3
"""Write seq/00-02 that load, instantiate, and call the first-add program.

Usage: h14_seq_first_add.py <sections dir> <first-add artifact dir> <out dir>

<sections dir> is the output of h14_first_add_sections.py (six section
files + binding.json). <first-add artifact dir> holds the packed 32 KiB
input-a.buffer, input-b.buffer, and output-sentinel.buffer. The output
buffer is step 2 buffer 2, published by the driver as
/sys/kernel/debug/ane_t6021_seq/s02b02.
"""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h14_seq_conv_exec import create_process_step
from h14_seq_load_probe import FIRST_ADD_SECTIONS, load_step
from h14_seq_pack import COMMAND, DMA, REPLY32, Buf, Step, pack

FILL = {"a": "input-a.buffer", "b": "input-b.buffer", "y": "output-sentinel.buffer"}


def procedure_call_step(binding: dict, artifacts: Path) -> Step:
    records = binding["records"]
    cmd = bytearray(0x60 + 0x30 * len(records))
    struct.pack_into("<IIIIIIQI", cmd, 0x08, 0, 0, binding["procedure_id"], 0,
                     binding["stats_type"], 0, 0xADD0, len(records))
    bufs, patches = [], [(REPLY32, COMMAND, 0x08, 0, 0x1B8), (REPLY32, COMMAND, 0x0C, 1, 0x0C)]
    for i, r in enumerate(records):
        fill = (artifacts / FILL[r["name"]]).read_bytes()
        if len(fill) != r["size"]:
            raise SystemExit(f"{r['name']}: buffer {len(fill)} != binding size {r['size']}")
        rec = 0x60 + 0x30 * i
        struct.pack_into("<III", cmd, rec, 1, r["buffer_id"], r["type"])
        struct.pack_into("<Q", cmd, rec + 0x20, r["size"])
        patches.append((DMA, COMMAND, rec + 0x18, i, 0))
        bufs.append(Buf(r["size"], fill, 64))
    return Step(0x204, bytes(cmd), bufs, patches, timeout_ms=5000,
                dump_reply=len(cmd), settle_ms=500)


def main() -> int:
    sections, artifacts, out = (Path(p) for p in sys.argv[1:4])
    binding = json.loads((sections / "binding.json").read_text())
    if [r["name"] for r in binding["records"]] != ["a", "b", "y"]:
        raise SystemExit("binding record order must be a, b, y")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.bin"):
        old.unlink()
    steps = [load_step(sections, FIRST_ADD_SECTIONS), create_process_step(),
             procedure_call_step(binding, artifacts)]
    for i, step in enumerate(steps):
        (out / f"{i:02d}.bin").write_bytes(pack(step))
    for p in sorted(out.glob("*.bin")):
        print(p.name, p.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
