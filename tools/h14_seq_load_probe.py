#!/usr/bin/env python3
"""Write seq/00 (LOAD_PROGRAM replay of the h14conv sections) and seq/01
(REQUEST_PROGRAM_ID 0x400 probe) for the T6021 legacy sequencer.

Usage: h14_seq_load_probe.py <h14conv dir> <out dir>

Step 00 reproduces the driver's built-in load byte for byte: header,
nine 0x30 records at +0x08 (flags=1, id at +4, address +0x18, size +0x20),
program_id=0xffffffff at +0x1b8. A result=0 here proves the sequencer path.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h14_seq_pack import COMMAND, DMA, Buf, Step, pack

SECTIONS = [("generic.bin", 1), ("kernel.bin", 2), ("text.bin", 3), ("operation.bin", 4),
            ("procedure.bin", 5), (None, 0), ("text-property.bin", 7), (None, 0), (None, 0)]
FIRST_ADD_SECTIONS = [("generic.bin", 1), ("kernel.bin", 2), ("descriptor.bin", 3),
                      ("operation.bin", 4), ("procedure.bin", 5), (None, 0),
                      ("tdprop.bin", 7), (None, 0), (None, 0)]


def load_step(src: Path, sections=SECTIONS) -> Step:
    cmd = bytearray(0x1C0)
    struct.pack_into("<I", cmd, 0x1B8, 0xFFFFFFFF)
    bufs, patches = [], []
    for slot, (name, ident) in enumerate(sections):
        if name is None:
            continue
        data = (src / name).read_bytes()
        rec = 8 + slot * 0x30
        struct.pack_into("<II", cmd, rec, 1, ident)
        struct.pack_into("<Q", cmd, rec + 0x20, len(data))
        patches.append((DMA, COMMAND, rec + 0x18, len(bufs), 0))
        bufs.append(Buf(max(0x4000, -(-len(data) // 0x4000) * 0x4000), data))
    return Step(0x200, bytes(cmd), bufs, patches, timeout_ms=5000, dump_reply=0x1C0)


def request_program_id_step() -> Step:
    cmd = bytearray(0x20)
    cmd[6] = 0x20
    return Step(0x400, bytes(cmd), timeout_ms=3000, dump_reply=0x20)


def main() -> int:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    (out / "00.bin").write_bytes(pack(load_step(src)))
    (out / "01.bin").write_bytes(pack(request_program_id_step()))
    for p in sorted(out.glob("*.bin")):
        print(p.name, p.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
