"""Convert a macOS 26 HWX Mach-O into Linux .anec input for libane."""

import struct
import sys
from dataclasses import dataclass
from pathlib import Path

TILE_SIZE = 0x4000
TD_MAGIC = 0xF401F800
MACHO_MAGIC_64 = 0xFEEDFACF
FIXTURE_MAGIC_64 = 0xBEEFFACE
LC_SEGMENT_64 = 0x19
ANEC_HEADER_SIZE = 0x1000


@dataclass(frozen=True)
class Section:
    segment: str
    name: str
    vm_address: int
    size: int
    file_offset: int

@dataclass(frozen=True)
class KDMALayout:
    enabled: tuple[int, ...]
    base_addresses: tuple[int, ...]
    buffer_sizes: tuple[int, ...]


KDMA_LANES = 16
KDMA_CONFIG_OFFSET = 52
KDMA_BASE_OFFSET = 116
KDMA_SIZE_OFFSET = 180


def _bits(data: bytes, byte_offset: int, bit: int, width: int) -> int:
    if byte_offset < 0 or byte_offset + 4 > len(data):
        raise ValueError("KDMA field exceeds the task descriptor")
    value = struct.unpack_from("<I", data, byte_offset)[0]
    return (value >> bit) & ((1 << width) - 1)


def decode_kdma(td: bytes) -> KDMALayout:
    """Decode the macOS 26 coefficient-DMA registers from one task descriptor."""
    if len(td) < KDMA_SIZE_OFFSET + 4 * KDMA_LANES:
        raise ValueError("task descriptor is too short for KDMA registers")
    return KDMALayout(
        enabled=tuple(_bits(td, KDMA_CONFIG_OFFSET + 4 * lane, 0, 1)
                      for lane in range(KDMA_LANES)),
        base_addresses=tuple(_bits(td, KDMA_BASE_OFFSET + 4 * lane, 6, 26)
                             for lane in range(KDMA_LANES)),
        buffer_sizes=tuple(_bits(td, KDMA_SIZE_OFFSET + 4 * lane, 6, 26)
                           for lane in range(KDMA_LANES)),
    )

@dataclass(frozen=True)
class HWXImage:
    sections: dict[tuple[str, str], Section]
    content_offset: int
    content_size: int
    td_offset: int
    td_size: int
    kernel_offset: int
    kernel_size: int
    command_size: int
    kdma: KDMALayout


def _name(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii")


def parse_hwx(data: bytes) -> HWXImage:
    """Parse Mach-O sections and derive the Linux ANEC payload geometry."""
    if len(data) < 32 or len(data) % 4:
        raise ValueError("HWX must have a 32-byte header and 4-byte alignment")
    header = struct.unpack_from("<8I", data)
    if header[0] not in (MACHO_MAGIC_64, FIXTURE_MAGIC_64):
        raise ValueError(f"expected 64-bit little-endian Mach-O, got {header[0]:#x}")

    ncmds, sizeofcmds = header[4], header[5]
    commands_end = 32 + sizeofcmds
    if commands_end > len(data):
        raise ValueError("Mach-O load commands exceed the file")

    sections: dict[tuple[str, str], Section] = {}
    segments: dict[str, tuple[int, int]] = {}
    command_offset = 32
    for _ in range(ncmds):
        if command_offset + 8 > commands_end:
            raise ValueError("truncated Mach-O load command")
        command, command_size = struct.unpack_from("<II", data, command_offset)
        if command_size < 8 or command_offset + command_size > commands_end:
            raise ValueError("invalid Mach-O load command size")
        if command == LC_SEGMENT_64:
            if command_size < 72:
                raise ValueError("truncated LC_SEGMENT_64")
            (
                _command, _size, raw_segment, _vm_address, _vm_size, file_offset,
                file_size, _max_protection, _init_protection, section_count, _flags,
            ) = struct.unpack_from("<II16sQQQQiiII", data, command_offset)
            segment = _name(raw_segment)
            if file_offset + file_size > len(data):
                raise ValueError(f"segment {segment} exceeds the file")
            segments[segment] = (file_offset, file_size)
            section_offset = command_offset + 72
            section_end = section_offset + section_count * 80
            if section_end > command_offset + command_size:
                raise ValueError(f"sections exceed {segment} load command")
            for index in range(section_count):
                (
                    raw_name, raw_section_segment, address, size, section_file_offset,
                    _align, _reloff, _nreloc, _flags, _reserved1, _reserved2, _reserved3,
                ) = struct.unpack_from("<16s16sQQIIIIIIII", data, section_offset + index * 80)
                name = _name(raw_name)
                section_segment = _name(raw_section_segment)
                if section_file_offset + size > len(data):
                    raise ValueError(f"section {section_segment},{name} exceeds the file")
                key = (section_segment, name)
                if key in sections:
                    raise ValueError(f"duplicate Mach-O section {section_segment},{name}")
                sections[key] = Section(
                    section_segment, name, address, size, section_file_offset
                )
        command_offset += command_size
    if command_offset != commands_end:
        raise ValueError("Mach-O load command table has trailing bytes")

    try:
        text_segment_offset, text_segment_size = segments["__TEXT"]
        text = sections["__TEXT", "__text"]
        kernel = sections["__TEXT", "__const"]
        command = sections["__FVMLIB", "__const"]
    except KeyError as error:
        raise ValueError(f"missing required Mach-O section: {error.args[0]}") from error
    if text_segment_offset != text.file_offset:
        raise ValueError("__TEXT,__text must start the __TEXT file payload")
    content_end = text_segment_offset + text_segment_size
    magic = struct.pack("<I", TD_MAGIC)
    td_hits = [
        offset - text_segment_offset
        for offset in range(text_segment_offset, content_end - 3, 4)
        if data[offset:offset + 4] == magic
    ]
    if len(td_hits) != 1:
        raise ValueError(f"expected one task descriptor in __TEXT, got {td_hits}")
    td_offset = td_hits[0]
    if td_offset + text.size > text_segment_size:
        raise ValueError("task descriptor exceeds the __TEXT payload")
    kernel_offset = kernel.file_offset - text_segment_offset
    if kernel_offset < 0 or kernel_offset + kernel.size > text_segment_size:
        raise ValueError("kernel section exceeds the __TEXT payload")
    if not command.size:
        raise ValueError("empty __FVMLIB,__const command window")
    td = data[text_segment_offset + td_offset:text_segment_offset + td_offset + text.size]
    return HWXImage(
        sections=sections,
        content_offset=text_segment_offset,
        content_size=text_segment_size,
        td_offset=td_offset,
        td_size=text.size,
        kernel_offset=kernel_offset,
        kernel_size=kernel.size,
        command_size=command.size,
        kdma=decode_kdma(td),
    )


def convert_hwx(data: bytes, in_ch: int, out_ch: int) -> bytes:
    image = parse_hwx(data)
    content = data[image.content_offset:image.content_offset + image.content_size]
    tiles = [0] * 32
    tiles[0] = (image.content_size + TILE_SIZE - 1) // TILE_SIZE

    nchw = [0] * (32 * 6)

    def put_nchw(slot: int, n: int, channels: int, height: int, width: int,
                 plane_stride: int, row_stride: int) -> None:
        nchw[slot * 6:slot * 6 + 6] = [
            n, channels, height, width, plane_stride, row_stride
        ]

    put_nchw(4, 1, out_ch, 1, 1, 0x40, 0x40)
    src_plane = (in_ch * 2 + 63) & -64
    put_nchw(5, 1, in_ch, 1, 1, src_plane, src_plane)
    tiles[5] = max(1, (in_ch * src_plane + TILE_SIZE - 1) // TILE_SIZE)
    tiles[4] = max(1, (out_ch * 0x40 + TILE_SIZE - 1) // TILE_SIZE)
    header = struct.pack(
        "<QIIQQII32I192Q",
        image.content_size, image.td_size, 1, image.td_size, image.kernel_size,
        1, 1, *tiles, *nchw,
    )
    return header + b"\0" * (ANEC_HEADER_SIZE - len(header)) + content


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: hwxv2-to-anec.py IN.hwx OUT.anec SRC_CH DST_CH", file=sys.stderr)
        return 2
    src_path, dst_path, in_ch, out_ch = argv[1], argv[2], int(argv[3]), int(argv[4])
    data = Path(src_path).read_bytes()
    image = parse_hwx(data)
    Path(dst_path).write_bytes(convert_hwx(data, in_ch, out_ch))
    enabled = [index for index, value in enumerate(image.kdma.enabled) if value]
    print(
        f"wrote={dst_path} content={image.content_size:#x} "
        f"td@content+{image.td_offset:#x} cmd={image.command_size:#x} "
        f"kernel@content+{image.kernel_offset:#x} ({image.kernel_size:#x}B) "
        f"kdma-enabled={enabled} kdma-bases={image.kdma.base_addresses} "
        f"kdma-sizes={image.kdma.buffer_sizes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
