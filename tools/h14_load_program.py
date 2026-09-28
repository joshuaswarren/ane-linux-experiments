#!/usr/bin/env python3
"""Pack a CSNE_CMD_LOAD_PROGRAM (0x0200) the selene pre-parse accepts.

No device contact. The M2 lane submits the bytes; this file only builds them.

Proven against t602x_ane0_fw_selene_rc4x.macho __TEXT (vm 0, fileoff 0x4000):
  0x4e46c  ldrh [cmd, #4] then cmp #0x200 / #0x202 / #0x204
  0x4e53c  LOAD_PROGRAM walks nine 0x30 records at the offsets below
  0x4e640  a present record (bit 0 of byte 0) must have a nonzero u64 at
           +0x18 and a nonzero u64 at +0x20
  0x5d0c8  that pair is a blob pointer and a size. The blob must start
           with u32 1, u32 <= 0x10, and a count at +0x204 in [1, 0x200].
           The size must cover 0x208 + count * 0x30.

Unread bytes in a record stay zero. Absent sections stay zero, so the
firmware skips them (tbz bit 0). A real program still has to fill the
section blobs; this packer does not invent one.
"""
import struct
import sys

LOAD_PROGRAM = 0x0200
CMD_SIZE = 0x1B8
CMD_MAX = 0x1B88
RECORD = 0x30
BLOB_COUNT_OFF = 0x204
BLOB_TABLE_OFF = 0x208

# Kernel submit contract (ane_t6021_rtclient_main.c, csne_load_program=1).
# The driver copies this file and doorbells cursor|len<<24. It does not
# rebuild the command.
FW_NAME = "apple/ane/load_program.bin"
SUBMIT_CURSOR = 0x100

# Name, command offset. Stride is 0x30. End of the last record is CMD_SIZE.
SECTIONS = (
    ("generic", 0x08),
    ("kernel", 0x38),
    ("text", 0x68),
    ("operation", 0x98),
    ("procedure", 0xC8),
    ("kernel_prop", 0xF8),
    ("text_prop", 0x128),
    ("op_dbg", 0x158),
    ("proc_prop", 0x188),
)


def blob_header(count, field4=0):
    """Smallest blob 0x5d0c8 accepts. Nested records are absent."""
    if not 1 <= count <= 0x200:
        raise ValueError(f"section count {count} outside 1..0x200")
    if field4 > 0x10:
        raise ValueError(f"blob +4 value {field4} above 0x10")
    size = BLOB_TABLE_OFF + count * RECORD
    blob = bytearray(size)
    struct.pack_into("<II", blob, 0, 1, field4)
    struct.pack_into("<I", blob, BLOB_COUNT_OFF, count)
    return bytes(blob)


def _record(dva, size):
    if dva == 0 or size == 0:
        raise ValueError("a present section needs a nonzero dva and size")
    rec = bytearray(RECORD)
    rec[0] = 1
    struct.pack_into("<QQ", rec, 0x18, dva, size)
    return rec


def pack(sections):
    """sections: name -> (dva, size). Missing names are absent."""
    unknown = set(sections) - {name for name, _ in SECTIONS}
    if unknown:
        raise ValueError(f"unknown section {sorted(unknown)}")
    cmd = bytearray(CMD_SIZE)
    struct.pack_into("<IHH", cmd, 0, 0, LOAD_PROGRAM, 0)
    for name, off in SECTIONS:
        if name not in sections:
            continue
        dva, size = sections[name]
        cmd[off:off + RECORD] = _record(dva, size)
    if len(cmd) > CMD_MAX:
        raise ValueError("command exceeds firmware 0x1b88 bound")
    return bytes(cmd)


def fw_accepts_blob(blob, size):
    """Mirror of 0x5d0c8. True when the firmware takes the success branch."""
    if len(blob) < 8 or size > len(blob):
        return False
    magic, field4 = struct.unpack_from("<II", blob, 0)
    if magic != 1 or field4 > 0x10 or len(blob) < BLOB_COUNT_OFF + 4:
        return False
    count = struct.unpack_from("<I", blob, BLOB_COUNT_OFF)[0]
    w9 = (count - 0x201) & 0xFFFFFFFF
    if (w9 + 0x200) < 0x100000000:
        return False
    return size >= BLOB_TABLE_OFF + count * RECORD


def submit_word(cursor, length):
    """msg48 word the driver sends: cursor[23:0] | length[47:24]."""
    if cursor > 0xFFFFFF or length > 0xFFFFFF:
        raise ValueError("cursor or length does not fit the msg48 fields")
    return cursor | (length << 24)


def write_firmware(path, sections):
    """Write the blob csne_load_program submits. No device contact."""
    blob = pack(sections)
    if len(blob) != CMD_SIZE:
        raise ValueError(f"packed size {len(blob)} != {CMD_SIZE}")
    path.write_bytes(blob)
    return blob


def stage_command():
    """Command with generic present and dva 0. The driver allocates the
    section and patches the IOVA. pack() still refuses a zero dva."""
    blob = blob_header(1)
    cmd = bytearray(CMD_SIZE)
    struct.pack_into("<IHH", cmd, 0, 0, LOAD_PROGRAM, 0)
    rec = bytearray(RECORD)
    rec[0] = 1
    struct.pack_into("<QQ", rec, 0x18, 0, len(blob))
    cmd[0x08:0x08 + RECORD] = rec
    return bytes(cmd)


def stage_like_driver(iova):
    """Bytes the driver submits after dma_alloc. iova stands in for the
    coherent mapping. The filled blob must pass the 0x5d0c8 check."""
    if not iova:
        raise ValueError("the driver never submits a zero device address")
    cmd = bytearray(stage_command())
    size = struct.unpack_from("<Q", cmd, 0x28)[0]
    blob = bytearray(size)
    struct.pack_into("<I", blob, 0, 1)
    struct.pack_into("<I", blob, BLOB_COUNT_OFF, 1)
    struct.pack_into("<Q", cmd, 0x20, iova)
    return bytes(cmd), bytes(blob)


def _self_check():
    blob = blob_header(1)
    assert fw_accepts_blob(blob, len(blob))
    assert not fw_accepts_blob(blob_header(1)[:4] + b"\x11\x00\x00\x00", 8)
    assert not fw_accepts_blob(blob, len(blob) - 1)
    cmd = pack({"generic": (0x1000, len(blob))})
    assert len(cmd) == CMD_SIZE
    assert struct.unpack_from("<IHH", cmd, 0) == (0, LOAD_PROGRAM, 0)
    assert cmd[0x08] == 1
    assert struct.unpack_from("<QQ", cmd, 0x20) == (0x1000, len(blob))
    assert cmd[0x38] == 0 and cmd[0x188] == 0
    try:
        pack({"generic": (0, len(blob))})
        raise AssertionError("zero dva must fail")
    except ValueError:
        pass
    word = submit_word(SUBMIT_CURSOR, CMD_SIZE)
    assert word == 0x1B8000100
    assert struct.unpack_from("<H", cmd, 4)[0] == LOAD_PROGRAM
    staged = stage_command()
    assert len(staged) == CMD_SIZE
    assert staged[0x08] & 1
    assert struct.unpack_from("<QQ", staged, 0x20) == (0, len(blob))
    patched, filled = stage_like_driver(0x1000)
    assert struct.unpack_from("<Q", patched, 0x20)[0] == 0x1000
    assert fw_accepts_blob(filled, len(filled))
    print("h14_load_program: ok")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--stage":
        Path = __import__("pathlib").Path
        out = Path(sys.argv[2])
        out.write_bytes(stage_command())
        print(f"wrote {out} {out.stat().st_size} bytes")
        sys.exit(0)
    _self_check()
    sys.exit(0)
