#!/usr/bin/env python3
"""Pack and parse apple/ane/seq/NN.bin files for the T6021 legacy sequencer.

Layout matches ane_t6021_legacy_seq.h: a 32-byte header, 16-byte buffer
descriptors, 16-byte patches, the command bytes, then each buffer's fill.
"""
import struct
from dataclasses import dataclass, field

MAGIC = 0x51454E41
HDR = struct.Struct("<IHHIIIIII")
BUF = struct.Struct("<IIII")
PATCH = struct.Struct("<HHIII")
DMA, REPLY32, STEP_DMA = 1, 2, 3
COMMAND = 0xFFFF


@dataclass
class Buf:
    size: int
    fill: bytes = b""
    dump_len: int = 0


@dataclass
class Step:
    opcode: int
    command: bytes
    bufs: list[Buf] = field(default_factory=list)
    patches: list[tuple[int, int, int, int, int]] = field(default_factory=list)
    channel: int = 1
    timeout_ms: int = 5000
    dump_reply: int = 64
    settle_ms: int = 0


def pack(step: Step) -> bytes:
    if not 8 <= len(step.command) <= 0x4000:
        raise ValueError("command length out of range")
    out = [HDR.pack(MAGIC, step.opcode, step.channel, len(step.command), len(step.bufs),
                    len(step.patches), step.timeout_ms, step.dump_reply, step.settle_ms)]
    for b in step.bufs:
        if len(b.fill) > b.size or b.dump_len > b.size:
            raise ValueError("fill or dump longer than buffer")
        out.append(BUF.pack(b.size, len(b.fill), b.dump_len, 0))
    out += [PATCH.pack(*p) for p in step.patches]
    out.append(step.command)
    out += [b.fill for b in step.bufs]
    blob = b"".join(out)
    if parse(blob) != step:
        raise AssertionError("round trip mismatch")
    return blob


def parse(blob: bytes) -> Step:
    magic, opcode, channel, cmd_len, nbufs, npatch, timeout_ms, dump_reply, settle_ms = HDR.unpack_from(blob)
    if magic != MAGIC:
        raise ValueError("bad magic")
    at = HDR.size
    descs = [BUF.unpack_from(blob, at + i * BUF.size) for i in range(nbufs)]
    at += nbufs * BUF.size
    patches = [PATCH.unpack_from(blob, at + i * PATCH.size) for i in range(npatch)]
    at += npatch * PATCH.size
    command = blob[at:at + cmd_len]
    at += cmd_len
    bufs = []
    for size, fill_len, dump_len, _ in descs:
        bufs.append(Buf(size, blob[at:at + fill_len], dump_len))
        at += fill_len
    if at != len(blob):
        raise ValueError("trailing bytes")
    return Step(opcode, command, bufs, patches, channel, timeout_ms, dump_reply, settle_ms)


def demo() -> None:
    step = Step(0x200, bytes(0x1C0), [Buf(0x4000, b"\x01" * 16, 16)],
                [(DMA, COMMAND, 0x18, 0, 0), (REPLY32, COMMAND, 0x1B8, 0, 8)])
    assert parse(pack(step)) == step


if __name__ == "__main__":
    demo()
    print("h14_seq_pack self-check ok")
