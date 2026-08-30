"""Convert a macOS 26 HWX Mach-O into Linux .anec input for libane."""

import argparse
import mmap
import struct
import sys
from dataclasses import dataclass

TILE_SIZE = 0x4000
TD_MAGIC = 0xF401F800
TD_SIZE = 0x274
TASK_HEADER_SIZE = 0x2C
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
    workspace_size: int
    input_size: int
    output_size: int
    kdma: KDMALayout



def _name(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii")


def find_task_offsets(
    data: bytes | mmap.mmap, content_offset: int, content_size: int
) -> tuple[int, ...]:
    """Return every linked task descriptor base in one HWX text section."""
    if content_offset < 0 or content_size < 0:
        raise ValueError("task search range must be non-negative")
    end = content_offset + content_size
    if end > len(data):
        raise ValueError("task search range exceeds the HWX")
    magic = struct.pack("<I", TD_MAGIC)
    seeds = {
        offset - content_offset - 0x28
        for offset in range(content_offset + 0x28, end - 3, 4)
        if data[offset:offset + 4] == magic
        and (offset - content_offset - 0x28) % 0x100 == 0
    }
    tasks: set[int] = set()
    for seed in sorted(seeds):
        current = seed
        chain: set[int] = set()
        while current not in chain and current + TASK_HEADER_SIZE <= content_size:
            chain.add(current)
            tasks.add(current)
            next_pointer = struct.unpack_from(
                "<I", data, content_offset + current + 0x1C
            )[0]
            if not next_pointer or next_pointer + TASK_HEADER_SIZE > content_size:
                break
            if next_pointer % 0x100:
                raise ValueError(f"unaligned task link {next_pointer:#x}")
            current = next_pointer

    predecessors: dict[int, list[int]] = {}
    for current in range(0, content_size - TD_SIZE + 1, 0x100):
        next_pointer = struct.unpack_from(
            "<I", data, content_offset + current + 0x1C
        )[0]
        if (
            next_pointer <= current
            or next_pointer % 0x100
            or next_pointer + TASK_HEADER_SIZE > content_size
        ):
            continue
        current_id = struct.unpack_from("<I", data, content_offset + current)[0]
        next_id = struct.unpack_from("<I", data, content_offset + next_pointer)[0]
        if (next_id & 0xFFFFFF) == (current_id & 0xFFFFFF) + 1:
            predecessors.setdefault(next_pointer, []).append(current)
    pending = list(tasks)
    while pending:
        for predecessor in predecessors.get(pending.pop(), ()):
            if predecessor not in tasks:
                tasks.add(predecessor)
                pending.append(predecessor)
    return tuple(sorted(tasks))

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
    section_ranges: dict[tuple[str, str], list[tuple[int, int]]] = {}
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
                if file_size and section_file_offset + size > len(data):
                    raise ValueError(f"section {section_segment},{name} exceeds the file")
                key = (section_segment, name)
                if key in sections and section_segment != "__FVMLIB":
                    raise ValueError(f"duplicate Mach-O section {section_segment},{name}")
                sections[key] = Section(
                    section_segment, name, address, size, section_file_offset
                )
                section_ranges.setdefault(key, []).append((address, size))
        command_offset += command_size
    if command_offset != commands_end:
        raise ValueError("Mach-O load command table has trailing bytes")

    try:
        text_segment_offset, text_segment_size = segments["__TEXT"]
        text = sections["__TEXT", "__text"]
        kernel = sections["__TEXT", "__const"]
        input_sections = section_ranges["__FVMLIB", "__const"]
        output_sections = section_ranges["__FVMLIB", "__data"]
    except KeyError as error:
        raise ValueError(f"missing required Mach-O section: {error.args[0]}") from error
    workspace_sections = section_ranges.get(("__DATA", "__bss"), [])

    def span(entries: list[tuple[int, int]]) -> int:
        return max(address + size for address, size in entries) - min(
            address for address, _ in entries
        )

    input_size = span(input_sections)
    output_size = span(output_sections)
    workspace_size = span(workspace_sections) if workspace_sections else 0
    if text_segment_offset != text.file_offset:
        raise ValueError("__TEXT,__text must start the __TEXT file payload")
    task_offsets = find_task_offsets(data, text.file_offset, text.size)
    if not task_offsets:
        raise ValueError("expected at least one task descriptor in __TEXT")
    td_offset = task_offsets[0] + text.file_offset - text_segment_offset
    if td_offset + TD_SIZE > text_segment_size:
        raise ValueError("task descriptor exceeds the __TEXT payload")
    kernel_offset = kernel.file_offset - text_segment_offset
    if kernel_offset < 0 or kernel_offset + kernel.size > text_segment_size:
        raise ValueError("kernel section exceeds the __TEXT payload")
    if not input_size or not output_size:
        raise ValueError("empty input or output buffer span")
    kdma_offset = next(
        offset
        for offset in task_offsets
        if struct.unpack_from("<I", data, text_segment_offset + offset + 0x28)[0]
        == TD_MAGIC
    )
    td = data[
        text_segment_offset + kdma_offset:
        text_segment_offset + kdma_offset + TD_SIZE
    ]
    return HWXImage(
        sections=sections,
        content_offset=text_segment_offset,
        content_size=text_segment_size,
        task_stream_size=text.size,
        td_offset=td_offset,
        td_count=len(task_offsets),
        td_size=TD_SIZE,
        kernel_offset=kernel_offset,
        kernel_size=kernel.size,
        workspace_size=workspace_size,
        input_size=input_size,
        output_size=output_size,
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
    tiles[3] = (image.workspace_size + TILE_SIZE - 1) // TILE_SIZE
    input_bytes = max(image.input_size, in_n * in_ch * in_plane)
    output_bytes = max(image.output_size, out_n * out_ch * out_plane)
    tiles[5] = max(1, (input_bytes + TILE_SIZE - 1) // TILE_SIZE)
    tiles[4] = max(1, (output_bytes + TILE_SIZE - 1) // TILE_SIZE)
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
    with open(src_path, "rb") as source, mmap.mmap(
        source.fileno(), 0, access=mmap.ACCESS_READ
    ) as data:
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
        f"td@content+{image.td_offset:#x} workspace={image.workspace_size:#x} "
        f"input={image.input_size:#x} output={image.output_size:#x} "
        f"kernel@content+{image.kernel_offset:#x} ({image.kernel_size:#x}B) "
        f"kdma-enabled={enabled} kdma-bases={image.kdma.base_addresses} "
        f"kdma-sizes={image.kdma.buffer_sizes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
