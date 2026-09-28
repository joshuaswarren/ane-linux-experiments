#!/usr/bin/env python3
"""Read T6021 ANE firmware ExeLoop state from host-side memory dumps.

Usage: h14_heap_inspect.py <firmware.macho> <heap.bin> <fwbuf.bin>

<heap.bin> and <fwbuf.bin> are /sys/kernel/debug/ane_t6021_seq/{heap,fwbuf}.
Firmware VA 0x20fc000000 + off is heap offset off; VA 0x2000000000 + off
is fwbuf offset off; low VAs (TEXT, FSM tables) are macho file offset
VA + 0x4000. Offsets are for the 13.5 selene firmware (sha256 a9c4b771...)
only.
"""
import struct
import sys
from pathlib import Path

HEAP_VA, FWBUF_VA, TEXT_FILE_OFF = 0x20FC000000, 0x2000000000, 0x4000
FSM_MAGIC, ELFSM_TABLE = 0x12483579, 0xC8020


class Mem:
    def __init__(self, image: bytes, heap: bytes, fwbuf: bytes):
        self.dumps = [(HEAP_VA, heap), (FWBUF_VA, fwbuf)]
        self.regions = self.dumps + [(-TEXT_FILE_OFF, image)]

    def read(self, va: int, fmt: str) -> int | None:
        for base, data in self.regions:
            off = va - base
            if 0 <= off <= len(data) - struct.calcsize(fmt):
                return struct.unpack_from(fmt, data, off)[0]
        return None


def fsm_cores(mem: Mem):
    """Yield (core_va, table, state_id, ctx) for every FSM core in the dumps."""
    magic = struct.pack("<I", FSM_MAGIC)
    for base, data in mem.dumps:
        at = data.find(magic)
        while at != -1:
            core = base + at - 0x20
            cur = mem.read(core + 0x38, "<Q")
            state = None if cur is None else mem.read(cur + 8, "<I")
            yield core, mem.read(core + 0x28, "<Q"), state, mem.read(core + 0x48, "<Q")
            at = data.find(magic, at + 1)


def engine_report(mem: Mem, engine: int) -> dict:
    def u8(o):
        return mem.read(engine + o, "<B")

    def u32(o):
        return mem.read(engine + o, "<I")

    sched = mem.read(engine + 0x6B8, "<Q") or 0
    return {
        "engine": hex(engine),
        "override_1a0": u8(0x1A0), "power_1a1": u8(0x1A1), "secure_phase_1a2": u8(0x1A2),
        "nonSec2SecCnt": u32(0x61C), "sec2NonSecCnt": u32(0x620),
        "free_slot": [u32(0x6C4 + 4 * i) for i in range(8)],
        "dummy_network": [(u8(0x4968 + 2 * i), u8(0x4969 + 2 * i)) for i in range(8)],
        "schedule_info": [(mem.read(sched + 8 * i, "<i"), mem.read(sched + 8 * i + 4, "<I"))
                          for i in range(u32(0x198) or 0)],
    }


def main() -> int:
    image, heap, fwbuf = (Path(p).read_bytes() for p in sys.argv[1:4])
    mem = Mem(image, heap, fwbuf)
    cores = list(fsm_cores(mem))
    for core, table, state, ctx in cores:
        print(f"fsm core {core:#x} table {table:#x} state {state} ctx {ctx:#x}")
    elfsm = [c for c in cores if c[1] == ELFSM_TABLE]
    if len(elfsm) != 1 or elfsm[0][3] is None:
        raise SystemExit(f"expected one ELFSM core, found {len(elfsm)}")
    for key, value in engine_report(mem, elfsm[0][3]).items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
