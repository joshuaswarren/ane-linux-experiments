#!/usr/bin/env python3
"""Build T6021 legacy-sequencer step files for any H14 program.

  h14_seq_program.py chain <sections> <artifacts> <out dir>
      Write 00-04: PRINT_ENABLE, TRACE_ENABLE, LOAD_PROGRAM, CREATE_PROCESS,
      PROCEDURE_CALL (the chain validated on the M2, boots 874b3bd2/8f468602).
  h14_seq_program.py call <sections> <artifacts> <out file>
      One more PROCEDURE_CALL with fresh buffers, bound to chain steps 2/3.
  h14_seq_program.py cmd <opcode> <length> <out file> [off=u32|off=u64:value ...]
      One plain command, e.g. `cmd 0x29 0x10 05.bin 8=u64:0x28e084000`.

<sections> is tools/h14_sections.py output (six .bin files + binding.json).
<artifacts> holds one fill file per binding record: <name>.buffer, or the
first-add legacy names input-<in>.buffer / output-sentinel.buffer. Each fill
must be exactly the record's size (the generic entry allocation).

Layouts (13.5 firmware, sha256 a9c4b771...): envelope u32 0, u16 opcode @+4
(driver-written), u16 result @+6. LOAD 0x200: nine 0x30 records at +8 (flags
+0, id +4, address +0x18, size +0x20), ProgramId out at +0x1b8. CREATE 0x202:
ProgramId +8, ProcessId out +0xc. CALL 0x204: ProgId +8, ProcId +0xc,
procedure +0x10, priority +0x18 in [2,7], uuid +0x20, count +0x28, 0x30-byte
records at +0x60 (flags bit0, bufferId, type 0 in/1 out, dma +0x18, size
+0x20).
"""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h14_seq_pack import COMMAND, DMA, REPLY32, Buf, Step, pack

SECTIONS = [("generic.bin", 1), ("kernel.bin", 2), ("descriptor.bin", 3),
            ("operation.bin", 4), ("procedure.bin", 5), (None, 0),
            ("tdprop.bin", 7), (None, 0), (None, 0)]
LOAD_STEP, CREATE_STEP = 2, 3


def command_step(opcode: int, length: int, fields: dict[int, tuple[str, int]]) -> Step:
    cmd = bytearray(length)
    for off, (fmt, value) in fields.items():
        struct.pack_into(fmt, cmd, off, value)
    return Step(opcode, bytes(cmd), timeout_ms=3000, dump_reply=length)


def load_step(sections: Path) -> Step:
    cmd = bytearray(0x1C0)
    struct.pack_into("<I", cmd, 0x1B8, 0xFFFFFFFF)
    bufs, patches = [], []
    for slot, (name, ident) in enumerate(SECTIONS):
        if name is None:
            continue
        data = (sections / name).read_bytes()
        rec = 8 + slot * 0x30
        struct.pack_into("<II", cmd, rec, 1, ident)
        struct.pack_into("<Q", cmd, rec + 0x20, len(data))
        patches.append((DMA, COMMAND, rec + 0x18, len(bufs), 0))
        bufs.append(Buf(max(0x4000, -(-len(data) // 0x4000) * 0x4000), data))
    return Step(0x200, bytes(cmd), bufs, patches, timeout_ms=5000, dump_reply=0x1C0)


def create_process_step() -> Step:
    cmd = bytearray(0x10)
    struct.pack_into("<I", cmd, 0x0C, 0xFFFFFFFF)
    return Step(0x202, bytes(cmd), patches=[(REPLY32, COMMAND, 0x08, LOAD_STEP, 0x1B8)],
                timeout_ms=3000, dump_reply=0x10)


def fill_file(artifacts: Path, record: dict) -> Path:
    candidates = [artifacts / f"{record['name']}.buffer"]
    if record["type"] == 0:
        candidates.append(artifacts / f"input-{record['name']}.buffer")
    else:
        candidates.append(artifacts / "output-sentinel.buffer")
    for path in candidates:
        if path.is_file():
            return path
    raise SystemExit(f"no fill for record {record['name']}: tried "
                     + ", ".join(str(p) for p in candidates))


def procedure_call_step(sections: Path, artifacts: Path) -> Step:
    binding = json.loads((sections / "binding.json").read_text())
    records = binding["records"]
    if not 1 <= len(records) <= 64:
        raise SystemExit(f"{len(records)} io records outside the checker "
                         "range [1,64] (fw135 0x48e0c)")
    cmd = bytearray(0x60 + 0x30 * len(records))
    struct.pack_into("<IIIIIIQI", cmd, 0x08, 0, 0, binding["procedure_id"], 0,
                     binding["stats_type"], 0, 0xADD0, len(records))
    bufs = []
    patches = [(REPLY32, COMMAND, 0x08, LOAD_STEP, 0x1B8), (REPLY32, COMMAND, 0x0C, CREATE_STEP, 0x0C)]
    for i, r in enumerate(records):
        fill = fill_file(artifacts, r).read_bytes()
        if len(fill) != r["size"]:
            raise SystemExit(f"{r['name']}: buffer {len(fill)} != binding size {r['size']}")
        rec = 0x60 + 0x30 * i
        struct.pack_into("<III", cmd, rec, 1, r["buffer_id"], r["type"])
        struct.pack_into("<Q", cmd, rec + 0x20, r["size"])
        patches.append((DMA, COMMAND, rec + 0x18, i, 0))
        bufs.append(Buf(r["size"], fill, 64))
    return Step(0x204, bytes(cmd), bufs, patches, timeout_ms=5000,
                dump_reply=len(cmd), settle_ms=1500)


def parse_field(text: str) -> tuple[int, tuple[str, int]]:
    off, _, value = text.partition("=")
    fmt, _, number = value.rpartition(":")
    return int(off, 0), ({"": "<I", "u32": "<I", "u64": "<Q"}[fmt], int(number, 0))


def main() -> int:
    mode, args = sys.argv[1], sys.argv[2:]
    if mode == "chain":
        sections, artifacts, out = (Path(p) for p in args)
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("*.bin"):
            old.unlink()
        steps = [command_step(0x04, 0x0C, {8: ("<I", 1)}), command_step(0x21, 0x0C, {8: ("<I", 0xE)}),
                 load_step(sections), create_process_step(), procedure_call_step(sections, artifacts)]
        for i, step in enumerate(steps):
            (out / f"{i:02d}.bin").write_bytes(pack(step))
            print(f"wrote {out / f'{i:02d}.bin'}")
    elif mode == "call":
        sections, artifacts, out = (Path(p) for p in args)
        out.write_bytes(pack(procedure_call_step(sections, artifacts)))
        print(f"wrote {out}")
    elif mode == "cmd":
        opcode, length, out = int(args[0], 0), int(args[1], 0), Path(args[2])
        out.write_bytes(pack(command_step(opcode, length, dict(map(parse_field, args[3:])))))
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
