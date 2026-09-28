#!/usr/bin/env python3
"""Write seq/00-02: LOAD_PROGRAM (h14conv sample) -> CREATE_PROCESS ->
PROCEDURE_CALL, for the T6021 legacy sequencer.

Usage: h14_seq_conv_exec.py <h14conv dir> <out dir>

Layouts. Handler names come from the h14j image; the M2 runs the macOS 13.5
image (sha a9c4b771...), whose checker addresses are cited below.
  0x200 LOAD      nine 0x30 records at +0x08 (addr +0x18, size +0x20);
                  ProgramId written to +0x1b8, -1 = failure.
  0x202 CREATE    ProgramId at +0x08; ProcessId written to +0x0c.
  0x204 PROC CALL ProgId +0x08, ProcId +0x0c, procedure +0x10, +0x18 in
                  [2,7], uuid +0x20, count +0x28 (1..64), 0x30 records at
                  +0x60. CAneProgramCheckerH14 (13.5 0x48df8) requires per
                  record: +0x00 flags bit0, +0x04 bufferId matching one
                  generic-section entry id, +0x20 size >= that entry's size.
                  +0x08 carries the direction (0 in, 1 out) [INFERENCE from
                  generic entry +0x08].
The h14conv generic section lists two 0x1000-byte buffers: id 0 then id 1.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h14_seq_load_probe import load_step
from h14_seq_pack import COMMAND, DMA, REPLY32, Buf, Step, pack

BUF_BYTES = 0x1000
SENTINEL = 0xAA


def create_process_step() -> Step:
    cmd = bytearray(0x10)
    struct.pack_into("<I", cmd, 0x0C, 0xFFFFFFFF)
    return Step(0x202, bytes(cmd), patches=[(REPLY32, COMMAND, 0x08, 0, 0x1B8)],
                timeout_ms=3000, dump_reply=0x10)


def procedure_call_step() -> Step:
    records = [("input", 0, struct.pack("<H", 0x3C00) * (BUF_BYTES // 2)),
               ("output", 1, bytes([SENTINEL]) * BUF_BYTES)]
    cmd = bytearray(0x60 + 0x30 * len(records))
    struct.pack_into("<IIIIIIQI", cmd, 0x08, 0, 0, 0, 0, 2, 0, 0x1234, len(records))
    assert struct.unpack_from("<I", cmd, 0x18)[0] == 2 and struct.unpack_from("<I", cmd, 0x28)[0] == 2
    bufs, patches = [], [(REPLY32, COMMAND, 0x08, 0, 0x1B8), (REPLY32, COMMAND, 0x0C, 1, 0x0C)]
    for i, (_, rtype, fill) in enumerate(records):
        rec = 0x60 + 0x30 * i
        struct.pack_into("<II", cmd, rec, 1, i)  # 0x48df8: flags bit0, bufferId = generic entry id
        struct.pack_into("<I", cmd, rec + 0x08, rtype)
        struct.pack_into("<Q", cmd, rec + 0x20, BUF_BYTES)
        patches.append((DMA, COMMAND, rec + 0x18, i, 0))
        bufs.append(Buf(0x4000, fill, 256))
    return Step(0x204, bytes(cmd), bufs, patches, timeout_ms=5000,
                dump_reply=len(cmd), settle_ms=500)


def main() -> int:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.bin"):
        old.unlink()
    steps = [load_step(src), create_process_step(), procedure_call_step()]
    for i, step in enumerate(steps):
        (out / f"{i:02d}.bin").write_bytes(pack(step))
    for p in sorted(out.glob("*.bin")):
        print(p.name, p.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
