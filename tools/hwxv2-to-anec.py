"""Convert a macOS 26 HWX Mach-O into Linux .anec input for libane."""

import argparse
import mmap
import struct
import sys
from dataclasses import dataclass

# Apple v10 containers are consumed with libane's tile_shift at 9, so the
# header's tile counts are 512-B units.
TILE_UNIT = 0x200
TILE_SIZE = 0x4000
# The first record header of a task is a register write to 0x01f800. Its top
# byte carries the record's word count, which differs between macOS build
# versions (0xf401f800 and 0x4401f800 both seen), so match the register only.
TD_RECORD_REGISTER = 0x01F800
TD_MAGIC = 0xF401F800
H13_HEADER_SIZE = 40
TASK_HEADER_SIZE = 0x2C
MACHO_MAGIC_64 = 0xFEEDFACF
FIXTURE_MAGIC_64 = 0xBEEFFACE
LC_SEGMENT_64 = 0x19
ANEC_HEADER_SIZE = 0x1000
# A CoreML weight blob file is a 0x40 header, then 0x40-byte metadata records
# each opening with this sentinel. The record carries the coefficient payload's
# own offset, which is the only place that offset is stated: the MIL declares
# BLOBFILE(offset = 64), the record it names sits there, and the payload starts
# past it. Nothing in the format fixes the distance, so it is read, not assumed.
BLOB_HEADER_SIZE = 0x40
BLOB_RECORD_SIZE = 0x40
BLOB_SENTINEL = 0xDEADBEEF
BLOB_RECORD_BYTES_OFFSET = 0x08
BLOB_RECORD_PAYLOAD_OFFSET = 0x18
# Tile-DMA byte counts, per task. RUN is the contiguous run the engine moves,
# TOTAL the whole surface. Their ratio is the row count, which is what says
# whether a surface is dense or 64-byte-plane padded.
TILE_DMA_SOURCE_RUN = 0x13810
TILE_DMA_SOURCE_TOTAL = 0x13814
TILE_DMA_DEST_RUN = 0x1780C
TILE_DMA_DEST_TOTAL = 0x17810


def is_task_record(word: int) -> bool:
    """True when a header word is the task's leading 0x01f800 register write."""
    return word & 0xFFFFFF == TD_RECORD_REGISTER

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

def extra_header_bytes(td: bytes) -> int:
    """One extra word precedes the first record when header[9] low bits are 0b11.

    Bit 1 alone is not the predicate: 0x26 has bit 1 set and no extra word.
    """
    if len(td) < H13_HEADER_SIZE:
        raise ValueError("task descriptor is shorter than the H13 header")
    last = struct.unpack_from("<I", td, H13_HEADER_SIZE - 4)[0]
    return 4 if last & 0x3 == 0x3 else 0


def walk_registers(td: bytes) -> dict[int, int]:
    """Return {register byte address: value} for one task descriptor.

    A record header carries the register byte address in bits 0..25 and the
    word count less one in bits 26..31, then that many consecutive register
    values. A record that runs past the descriptor is the -110 defect class,
    so it is an error rather than a partial decode.
    """
    registers: dict[int, int] = {}
    offset = H13_HEADER_SIZE + extra_header_bytes(td)
    while offset + 4 <= len(td):
        header = struct.unpack_from("<I", td, offset)[0]
        if not header:
            break
        register = header & 0x3FFFFFF
        count = (header >> 26) + 1
        offset += 4
        if offset + 4 * count > len(td):
            raise ValueError(
                f"register record at {offset - 4:#x} runs past the task descriptor"
            )
        for index in range(count):
            registers[register + 4 * index] = struct.unpack_from(
                "<I", td, offset + 4 * index
            )[0]
        offset += 4 * count
    return registers


@dataclass(frozen=True)
class TileDMA:
    """The task's own byte counts for the source and destination surfaces."""

    source_run: int
    source_total: int
    dest_run: int
    dest_total: int


def decode_tile_dma(td: bytes) -> TileDMA:
    """Read the tile-DMA byte counts one task states for its own surfaces."""
    registers = walk_registers(td)
    return TileDMA(
        source_run=registers.get(TILE_DMA_SOURCE_RUN, 0),
        source_total=registers.get(TILE_DMA_SOURCE_TOTAL, 0),
        dest_run=registers.get(TILE_DMA_DEST_RUN, 0),
        dest_total=registers.get(TILE_DMA_DEST_TOTAL, 0),
    )


def is_weight_blob(head: bytes) -> bool:
    """True when a kernel section carries a CoreML weight blob file verbatim."""
    if len(head) < BLOB_HEADER_SIZE + 4:
        return False
    return struct.unpack_from("<I", head, BLOB_HEADER_SIZE)[0] == BLOB_SENTINEL


def blob_payload_offset(blob: bytes, size: int) -> int:
    """Return the offset of the `size`-byte coefficient payload in a blob file.

    The offset comes out of the blob's own metadata record. Every candidate is
    checked against the record and the file, and an ambiguous or unaccounted
    blob is an error: a coefficient stream is not something to guess at.
    """
    matches = []
    offset = BLOB_HEADER_SIZE
    while offset + BLOB_RECORD_SIZE <= len(blob):
        if struct.unpack_from("<I", blob, offset)[0] != BLOB_SENTINEL:
            break
        declared = struct.unpack_from(
            "<Q", blob, offset + BLOB_RECORD_BYTES_OFFSET
        )[0]
        payload = struct.unpack_from(
            "<Q", blob, offset + BLOB_RECORD_PAYLOAD_OFFSET
        )[0]
        offset += BLOB_RECORD_SIZE
        if (
            declared == size
            and payload >= offset
            and payload + size <= len(blob)
        ):
            matches.append(payload)
    if len(matches) != 1:
        raise ValueError(
            f"weight blob does not name exactly one {size}-byte payload "
            f"(found {len(matches)})"
        )
    return matches[0]


def kernel_payload(image: "HWXImage", blob: bytes | None) -> bytes | None:
    """Return the coefficients the engine must read, or None to copy verbatim.

    For a BLOBFILE constant the HWX embeds the blob file from byte 0, so the
    section holds the blob header where coefficients belong and truncates the
    real tail. The payload has to come from the blob itself.
    """
    if not image.kernel_is_blob:
        return None
    if blob is None:
        raise ValueError(
            "the kernel section is a CoreML weight blob file, so its "
            "coefficients are offset by the blob header; pass the bundle's "
            "weights.bin to source them from the blob payload"
        )
    offset = blob_payload_offset(blob, image.kernel_size)
    return blob[offset:offset + image.kernel_size]

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
    input_sections: tuple[tuple[int, int], ...]
    output_sections: tuple[tuple[int, int], ...]
    kdma: KDMALayout
    tile_dma: TileDMA
    kernel_is_blob: bool



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
    seeds = {
        offset - content_offset - 0x28
        for offset in range(content_offset + 0x28, end - 3, 4)
        if is_task_record(struct.unpack_from("<I", data, offset)[0])
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
    for current in range(0, content_size - TASK_HEADER_SIZE + 1, 0x100):
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
    # The engine treats td_size as the task word count. A hardcoded 0x274
    # over-fetched 124 bytes past a 0x1f8 task and decoded the CoreML weight
    # blob as register writes, so TM never went idle (-110).
    td_end = task_offsets[1] if task_offsets[1:] else text.size
    td_size = td_end - task_offsets[0]
    if td_offset + td_size > text_segment_size:
        raise ValueError("task descriptor exceeds the __TEXT payload")
    kernel_offset = kernel.file_offset - text_segment_offset
    if kernel_offset < 0 or kernel_offset + kernel.size > text_segment_size:
        raise ValueError("kernel section exceeds the __TEXT payload")
    # libane locates the kernel section at align16(tsk_size); a section that
    # sits anywhere else is read from the wrong bytes no matter what it holds.
    if kernel_offset != (text.size + 0xF) & -0x10:
        raise ValueError(
            f"kernel section at {kernel_offset:#x} is not at "
            f"align16(tsk_size) = {(text.size + 0xF) & -0x10:#x}"
        )
    if not input_size or not output_size:
        raise ValueError("empty input or output buffer span")
    kdma_offset = next(
        offset
        for offset in task_offsets
        if is_task_record(
            struct.unpack_from("<I", data, text_segment_offset + offset + 0x28)[0]
        )
    )
    td = data[
        text_segment_offset + kdma_offset:
        text_segment_offset + kdma_offset + td_size
    ]
    return HWXImage(
        sections=sections,
        content_offset=text_segment_offset,
        content_size=text_segment_size,
        task_stream_size=text.size,
        td_offset=td_offset,
        td_count=len(task_offsets),
        td_size=td_size,
        kernel_offset=kernel_offset,
        kernel_size=kernel.size,
        workspace_size=workspace_size,
        input_size=input_size,
        output_size=output_size,
        input_sections=tuple(input_sections),
        output_sections=tuple(output_sections),
        kdma=decode_kdma(td),
        tile_dma=decode_tile_dma(td),
        kernel_is_blob=is_weight_blob(data[
            text_segment_offset + kernel_offset:
            text_segment_offset + kernel_offset + BLOB_HEADER_SIZE + 4
        ]),
    )


def _shape_strides(height: int, width: int) -> tuple[int, int]:
    """The 64-byte-padded plane convention, used when the task is silent."""
    if height < 1 or width < 1:
        raise ValueError("tensor dimensions must be positive")
    row_stride = max(0x40, (width * 2 + 0x3F) & -0x40)
    return height * row_stride, row_stride


def derive_strides(
    shape: tuple[int, int, int, int], total: int, run: int
) -> tuple[int, int]:
    """Return (plane, row) bytes for one surface, from the task's byte counts.

    Geometry is per-program, and the task states it: `total` is the whole
    surface and `run` the contiguous stretch the engine moves, so total/run is
    the row count. One run per channel is the 64-byte-padded plane layout and
    the run stride is the plane stride; a single run is a dense surface whose
    plane stride is just the surface divided among its channels. Anything the
    task does not account for falls back to the padding convention rather than
    becoming a new guess.
    """
    n, channels, height, width = shape
    planes = n * channels
    fallback = _shape_strides(height, width)
    if total <= 0 or run <= 0 or planes <= 0 or height <= 0 or total % run:
        return fallback
    rows = total // run
    if rows == planes:
        plane = run
    elif rows == 1 and total % planes == 0:
        plane = total // planes
    else:
        return fallback
    if plane % height or plane < width * 2:
        return fallback
    return plane, plane // height


def _build_header(
    image: HWXImage,
    in_shape: tuple[int, int, int, int],
    out_shape: tuple[int, int, int, int],
    in_shape_list=None,
    out_shape_list=None,
) -> bytes:
    """Build the Linux anec header for one converted HWX.

    Tile counts are emitted in 512-B units: the macOS 26 container is
    consumed by libane built with tile_shift 9, and 0x4000-unit counts
    leave the command buffer 32x undersized so the engine fetches weights
    past the mapped BO and stalls with no completion event.
    """
    in_n, in_ch, in_h, in_w = in_shape
    out_n, out_ch, out_h, out_w = out_shape
    in_plane, in_row = derive_strides(
        in_shape, image.tile_dma.source_total, image.tile_dma.source_run
    )
    out_plane, out_row = derive_strides(
        out_shape, image.tile_dma.dest_total, image.tile_dma.dest_run
    )
    input_sections = image.input_sections or ((0, image.input_size),)
    output_sections = image.output_sections or ((0, image.output_size),)
    if len(input_sections) + len(output_sections) > 28:
        raise ValueError("ANEC supports at most 28 input and output ports")
    tiles = [0] * 32
    tiles[0] = (image.content_size + TILE_UNIT - 1) // TILE_UNIT
    tiles[3] = (image.workspace_size + TILE_UNIT - 1) // TILE_UNIT
    dst_count = len(output_sections)
    # per-surface shapes: broadcast the CLI geometry unless explicit lists are given
    in_shape_list = in_shape_list or ([(in_n, in_ch, in_h, in_w)] * len(input_sections))
    out_shape_list = out_shape_list or ([(out_n, out_ch, out_h, out_w)] * len(output_sections))
    if len(in_shape_list) != len(input_sections) or len(out_shape_list) != len(output_sections):
        raise ValueError(
            f"surface shape count mismatch: {len(in_shape_list)} in / {len(out_shape_list)} out "
            f"vs {len(input_sections)} / {len(output_sections)} sections")
    input_shapes = [tuple(x) for x in in_shape_list]
    output_shapes = [tuple(x) for x in out_shape_list]
    output_sizes = [size for _, size in output_sections]
    input_sizes = [size for _, size in input_sections]
    if len(output_sizes) == 1:
        output_sizes[0] = max(output_sizes[0], image.output_size)
    if len(input_sizes) == 1:
        input_sizes[0] = max(input_sizes[0], image.input_size)
    for index, size in enumerate(output_sizes):
        shape = output_shapes[index]
        shape_bytes = shape[0] * shape[1] * out_plane
        required = max(size, shape_bytes)
        tiles[4 + index] = max(1, (required + TILE_UNIT - 1) // TILE_UNIT)
    for index, size in enumerate(input_sizes):
        shape = input_shapes[index]
        shape_bytes = shape[0] * shape[1] * in_plane
        required = max(size, shape_bytes)
        tiles[4 + dst_count + index] = max(1, (required + TILE_UNIT - 1) // TILE_UNIT)
    nchw = [0] * (32 * 6)
    for index, shape in enumerate(output_shapes):
        plane, row = (shape[2] * shape[3], shape[3]) if out_shape_list else (out_plane, out_row)
        nchw[(4 + index) * 6:(4 + index) * 6 + 6] = [*shape, plane, row]
    for index, shape in enumerate(input_shapes):
        plane, row = (shape[2] * shape[3], shape[3]) if in_shape_list else (in_plane, in_row)
        nchw[(4 + dst_count + index) * 6:(4 + dst_count + index) * 6 + 6] = [*shape, plane, row]
    return struct.pack(
        "<QIIQQII32I192Q",
        image.content_size,
        # TQ_SIZE1 encodes (td_size >> 2) - 1 in a 7-bit field: anything
        # above 0x1f8 overflows into the neighbouring register field and
        # the firmware never dispatches the bootstrap task. The bootstrap
        # only needs the first 0x1f8 bytes of task 0; the firmware walks
        # the rest of the stream by the next pointers.
        min(image.td_size, 0x1F8),
        image.td_count,
        image.task_stream_size,
        image.kernel_size,
        len(input_sections),
        len(output_sections),
        *tiles,
        *nchw,
    )


def _write_content(
    output,
    data: bytes | mmap.mmap,
    image: HWXImage,
    payload: bytes | None,
) -> None:
    """Copy the __TEXT payload, substituting the kernel section when relocated."""
    spans = [(0, image.content_size)]
    if payload is not None:
        kernel_end = image.kernel_offset + image.kernel_size
        spans = [(0, image.kernel_offset), (kernel_end, image.content_size)]
    for index, (start, end) in enumerate(spans):
        if index == 1:
            output.write(payload)
        start += image.content_offset
        end += image.content_offset
        while start < end:
            chunk_end = min(start + 16 * 1024 * 1024, end)
            output.write(data[start:chunk_end])
            start = chunk_end


def patch_task_nid(content: bytearray, tsk_size: int, nid: int = 0x40) -> int:
    """Stamp the FIFO nid into every task header of one converted payload.

    Apple's macOS 26 streams carry nid bits (hdr0 16..23) = 0; the Linux
    task manager routes every task to the FIFO named by those bits and its
    finish event matches `nid << 16 | (td_count - 1)`, so a stream whose
    tasks name no FIFO is fetched, stalls, and never signals completion
    (tm completion failed: -110, finish lines=0). The island compiler
    writes nid 0x40 on every task; the low 16 counter bits and the
    first/last flag bits are Apple's own and are preserved.
    """
    patched = 0
    offset = 0
    seen = set()
    while offset + 0x20 <= tsk_size and offset not in seen:
        seen.add(offset)
        hdr0 = struct.unpack_from("<I", content, offset)[0]
        struct.pack_into("<I", content, offset, hdr0 | (nid << 16))
        patched += 1
        nxt = struct.unpack_from("<I", content, offset + 0x1C)[0]
        if not nxt or nxt + 0x20 > tsk_size:
            break
        offset = nxt
    return patched


def _rewire_channel(channel: int, dst_count: int) -> int:
    """Map a surface channel between Apple's and libane's role layouts.

    Apple binds surface channels by role where they fall in the stream:
    sources on the first surface channels, destinations after them. The
    Linux runtime's staging ordinals are the reverse: destinations at
    channels 4..4+dst_count-1, sources after those. A stream kept on
    Apple's wiring makes the engine DMA its inputs from buffers sized for
    outputs and written by nobody, which runs off the end of the bound BO
    and stalls with no completion event. Surfaces below channel 4
    (command/workspace) never move.
    """
    if 4 <= channel < 4 + dst_count:
        return channel + dst_count
    if 4 + dst_count <= channel < 4 + dst_count * 2:
        return channel - dst_count
    return channel


def rewire_surface_channels(content: bytearray, tsk_size: int, dst_count: int) -> int:
    """Rewrite each task's selector word to the runtime's role layout."""
    rewired = 0
    offset = 0
    seen = set()
    shifts = (0, 6, 12)
    while offset + 0x20 <= tsk_size and offset not in seen:
        seen.add(offset)
        sel = struct.unpack_from("<I", content, offset + 32)[0]
        new = sel
        for shift in shifts:
            channel = (sel >> shift) & 0x1F
            mapped = _rewire_channel(channel, dst_count)
            if mapped != channel:
                new = (new & ~(0x1F << shift)) | (mapped << shift)
        if new != sel:
            struct.pack_into("<I", content, offset + 32, new)
            rewired += 1
        nxt = struct.unpack_from("<I", content, offset + 0x1C)[0]
        if not nxt or nxt + 0x20 > tsk_size:
            break
        offset = nxt
    return rewired


def convert_hwx(
    data: bytes,
    in_ch: int,
    out_ch: int,
    in_shape: tuple[int, int, int, int] | None = None,
    out_shape: tuple[int, int, int, int] | None = None,
    blob: bytes | None = None,
) -> bytes:
    image = parse_hwx(data)
    in_shape = (1, in_ch, 1, 1) if in_shape is None else in_shape
    out_shape = (1, out_ch, 1, 1) if out_shape is None else out_shape
    header = _build_header(image, in_shape, out_shape)
    content = bytearray(
        data[image.content_offset:image.content_offset + image.content_size]
    )
    payload = kernel_payload(image, blob)
    if payload is not None:
        content[image.kernel_offset:image.kernel_offset + image.kernel_size] = payload
    patched = patch_task_nid(content, image.task_stream_size)
    rewire_surface_channels(content, image.task_stream_size,
                            len(image.output_sections or (1,)))
    return header + b"\0" * (ANEC_HEADER_SIZE - len(header)) + bytes(content)


def convert_hwx_file(
    src_path: str,
    dst_path: str,
    in_ch: int,
    out_ch: int,
    in_shape: tuple[int, int, int, int] | None = None,
    out_shape: tuple[int, int, int, int] | None = None,
    blob_path: str | None = None,
) -> HWXImage:
    blob = None
    if blob_path is not None:
        with open(blob_path, "rb") as weights:
            blob = weights.read()
    with open(src_path, "rb") as source, mmap.mmap(
        source.fileno(), 0, access=mmap.ACCESS_READ
    ) as data:
        image = parse_hwx(data)
        in_shape = (1, in_ch, 1, 1) if in_shape is None else in_shape
        out_shape = (1, out_ch, 1, 1) if out_shape is None else out_shape
        header = _build_header(image, in_shape, out_shape)
        payload = kernel_payload(image, blob)
        with open(dst_path, "wb") as output:
            output.write(header)
            output.write(b"\0" * (ANEC_HEADER_SIZE - len(header)))
            _write_content(output, data, image, payload)
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
    parser.add_argument(
        "--in-shapes", default=None,
        help="per-input-surface NCHW list, comma separated (e.g. 1x2048,6144x3); "
             "3 dims are padded with N=1; order = ANEC input-section order")
    parser.add_argument(
        "--out-shapes", default=None,
        help="per-output-surface NCHW list, comma separated; order = ANEC output-section order")
    parser.add_argument(
        "--weights",
        help="the bundle's weight blob file, required for a BLOBFILE constant",
    )
    args = parser.parse_args(argv[1:])
    def _shapes(spec):
        if not spec:
            return None
        out = []
        for part in spec.split(","):
            dims = part.replace("x", " ").split()
            while len(dims) < 4:
                dims.insert(0, "1")
            out.append(tuple(int(x) for x in dims))
        return out
    image = convert_hwx_file(
        args.src_path,
        args.dst_path,
        args.input_channels,
        args.output_channels,
        (1, args.input_channels, args.input_height, args.input_width),
        (1, args.output_channels, args.output_height, args.output_width),
        args.weights,
    )
    in_strides = derive_strides(
        (1, args.input_channels, args.input_height, args.input_width),
        image.tile_dma.source_total,
        image.tile_dma.source_run,
    )
    out_strides = derive_strides(
        (1, args.output_channels, args.output_height, args.output_width),
        image.tile_dma.dest_total,
        image.tile_dma.dest_run,
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
        f" tile-dma={image.tile_dma} kernel-blob={image.kernel_is_blob} "
        f"in-plane/row={in_strides} out-plane/row={out_strides}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
