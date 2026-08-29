"""Convert a macOS 26 HWX Mach-O into Linux .anec input for libane."""

import argparse
import mmap
import struct
import sys
from dataclasses import dataclass

TILE_SIZE = 0x4000
TD_MAGIC = 0xF401F800
TD_SIZE = 0x274
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
    task_stream_size: int
    td_offset: int
    td_count: int
    td_size: int
    kernel_offset: int
    kernel_size: int
    command_size: int
    kdma: KDMALayout



def _name(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii")
def find_task_offsets(data: bytes | mmap.mmap, content_offset: int, content_size: int) -> tuple[int, ...]:
    """Return all aligned task descriptors in one HWX text section."""
    if content_offset < 0 or content_size < 0:
        raise ValueError("task search range must be non-negative")
    end = content_offset + content_size
    if end > len(data):
        raise ValueError("task search range exceeds the HWX")
    magic = struct.pack("<I", TD_MAGIC)
    return tuple(
        offset - content_offset
        for offset in range(content_offset, end - 3, 4)
        if data[offset:offset + 4] == magic
    )

def parse_hwx(data: bytes | mmap.mmap) -> HWXImage:
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
                if key in sections and section_segment != "__FVMLIB":
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
    td_hits = find_task_offsets(data, text.file_offset, text.size)
    if not td_hits:
        raise ValueError("expected at least one task descriptor in __TEXT")
    td_offset = td_hits[0] + text.file_offset - text_segment_offset
    if td_offset + TD_SIZE > text_segment_size:
        raise ValueError("task descriptor exceeds the __TEXT payload")
    kernel_offset = kernel.file_offset - text_segment_offset
    if kernel_offset < 0 or kernel_offset + kernel.size > text_segment_size:
        raise ValueError("kernel section exceeds the __TEXT payload")
    if not command.size:
        raise ValueError("empty __FVMLIB,__const command window")
    td = data[text_segment_offset + td_offset:text_segment_offset + td_offset + TD_SIZE]
    return HWXImage(
        sections=sections,
        content_offset=text_segment_offset,
        content_size=text_segment_size,
        task_stream_size=text.size,
        td_offset=td_offset,
        td_count=len(td_hits),
        td_size=TD_SIZE,
        kernel_offset=kernel_offset,
        kernel_size=kernel.size,
        command_size=command.size,
        kdma=decode_kdma(td),
    )


def _shape_strides(height: int, width: int) -> tuple[int, int]:
    if height < 1 or width < 1:
        raise ValueError("tensor dimensions must be positive")
    row_stride = max(0x40, (width * 2 + 0x3F) & -0x40)
    return height * row_stride, row_stride


def _build_header(
    image: HWXImage,
    in_shape: tuple[int, int, int, int],
    out_shape: tuple[int, int, int, int],
) -> bytes:
    in_n, in_ch, in_h, in_w = in_shape
    out_n, out_ch, out_h, out_w = out_shape
    in_plane, in_row = _shape_strides(in_h, in_w)
    out_plane, out_row = _shape_strides(out_h, out_w)
    tiles = [0] * 32
    tiles[0] = (image.content_size + TILE_SIZE - 1) // TILE_SIZE
    tiles[5] = max(1, (in_n * in_ch * in_plane + TILE_SIZE - 1) // TILE_SIZE)
    tiles[4] = max(1, (out_n * out_ch * out_plane + TILE_SIZE - 1) // TILE_SIZE)
    nchw = [0] * (32 * 6)
    nchw[4 * 6:4 * 6 + 6] = [out_n, out_ch, out_h, out_w, out_plane, out_row]
    nchw[5 * 6:5 * 6 + 6] = [in_n, in_ch, in_h, in_w, in_plane, in_row]
    return struct.pack(
        "<QIIQQII32I192Q",
        image.content_size,
        image.td_size,
        image.td_count,
        image.task_stream_size,
        image.kernel_size,
        1,
        1,
        *tiles,
        *nchw,
    )


def convert_hwx(
    data: bytes,
    in_ch: int,
    out_ch: int,
    in_shape: tuple[int, int, int, int] | None = None,
    out_shape: tuple[int, int, int, int] | None = None,
) -> bytes:
    image = parse_hwx(data)
    in_shape = (1, in_ch, 1, 1) if in_shape is None else in_shape
    out_shape = (1, out_ch, 1, 1) if out_shape is None else out_shape
    header = _build_header(image, in_shape, out_shape)
    content = data[image.content_offset:image.content_offset + image.content_size]
    return header + b"\0" * (ANEC_HEADER_SIZE - len(header)) + content


def convert_hwx_file(
    src_path: str,
    dst_path: str,
    in_ch: int,
    out_ch: int,
    in_shape: tuple[int, int, int, int] | None = None,
    out_shape: tuple[int, int, int, int] | None = None,
) -> HWXImage:


    with open(src_path, "rb") as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
        image = parse_hwx(data)
        in_shape = (1, in_ch, 1, 1) if in_shape is None else in_shape
        out_shape = (1, out_ch, 1, 1) if out_shape is None else out_shape
        header = _build_header(image, in_shape, out_shape)
        with open(dst_path, "wb") as output:
            output.write(header)
            output.write(b"\0" * (ANEC_HEADER_SIZE - len(header)))
            start = image.content_offset
            end = start + image.content_size
            while start < end:
                chunk_end = min(start + 16 * 1024 * 1024, end)
                output.write(data[start:chunk_end])
                start = chunk_end
        return image

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("src_path")
    parser.add_argument("dst_path")
    parser.add_argument("input_channels", type=int)
    parser.add_argument("output_channels", type=int)
    parser.add_argument("--input-height", type=int, default=1)
    parser.add_argument("--input-width", type=int, default=1)
    parser.add_argument("--output-height", type=int, default=1)
    parser.add_argument("--output-width", type=int, default=1)
    args = parser.parse_args(argv[1:])
    image = convert_hwx_file(
        args.src_path,
        args.dst_path,
        args.input_channels,
        args.output_channels,
        (1, args.input_channels, args.input_height, args.input_width),
        (1, args.output_channels, args.output_height, args.output_width),
    )
    enabled = [index for index, value in enumerate(image.kdma.enabled) if value]
    print(
        f"wrote={args.dst_path} content={image.content_size:#x} "
        f"task-stream={image.task_stream_size:#x} td-count={image.td_count} "
        f"td@content+{image.td_offset:#x} cmd={image.command_size:#x} "
        f"kernel@content+{image.kernel_offset:#x} ({image.kernel_size:#x}B) "
        f"kdma-enabled={enabled} kdma-bases={image.kdma.base_addresses} "
        f"kdma-sizes={image.kdma.buffer_sizes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
