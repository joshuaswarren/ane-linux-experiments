#!/usr/bin/env python3
"""Submit a streamed production ANEC graph through the Linux ANE KMD."""

import argparse
import importlib.util
import mmap
import os
import struct
import time
from contextlib import ExitStack
from fcntl import ioctl
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
ANEC_HEADER = struct.Struct("<QIIQQII32I192Q")
HEADER_SIZE = 0x1000
TILE_SIZE = 0x4000
SRC_BDX = 5
DST_BDX = 4


def load_runtime():
    runtime_path = Path(os.environ.get("ANE_RUNTIME_PATH", ROOT / "ane-runtime.py"))
    spec = importlib.util.spec_from_file_location("ane_runtime", runtime_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ane-runtime.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("anec", type=Path)
    parser.add_argument("--input-value", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--td-count", type=int)
    parser.add_argument("--td-start", type=int, default=0)
    parser.add_argument("--dump-output", type=Path)
    return parser.parse_args()


def load_anec_header(path):
    with path.open("rb") as stream:
        header = stream.read(ANEC_HEADER.size)
    if len(header) != ANEC_HEADER.size:
        raise ValueError("ANEC header is truncated")
    return ANEC_HEADER.unpack(header)


def copy_content(data, offset, size, destination):
    destination.seek(0)
    copied = 0
    while copied < size:
        chunk_size = min(16 * 1024 * 1024, size - copied)
        destination.write(data[offset + copied:offset + copied + chunk_size])
        copied += chunk_size

def task_bases(data, start, size):
    marker = struct.pack("<I", 0xF401F800)
    end = start + size
    bases = []
    position = data.find(marker, start, end)
    while position >= 0:
        relative = position - start
        if relative < 0x28 or relative % 4:
            raise ValueError(f"invalid task marker at content+{relative:#x}")
        bases.append(relative - 0x28)
        position = data.find(marker, position + 4, end)
    return tuple(bases)


def build_bootstrap(data, content_start, bases, td_size, td_count):
    if len(bases) < td_count:
        raise ValueError(f"ANEC has {len(bases)} task descriptors, needs {td_count}")
    selected_bases = bases[:td_count]
    source_to_destination = {
        base: index * 0x300 for index, base in enumerate(selected_bases)
    }
    bootstrap = bytearray((td_count - 1) * 0x300 + td_size)
    for index, base in enumerate(selected_bases):
        source_start = content_start + base
        destination_start = index * 0x300
        bootstrap[destination_start:destination_start + td_size] = data[
            source_start:source_start + td_size
        ]
        next_pointer = struct.unpack_from("<I", bootstrap, destination_start + 0x1C)[0]
        if next_pointer:
            mapped_pointer = source_to_destination.get(next_pointer)
            if mapped_pointer is None:
                if index != td_count - 1:
                    raise ValueError(
                        f"task {index} points outside selected descriptors: {next_pointer:#x}"
                    )
                mapped_pointer = 0
            struct.pack_into(
                "<I", bootstrap, destination_start + 0x1C, mapped_pointer
            )
    return bytes(bootstrap)


def main():
    args = parse_args()
    if args.timeout <= 0:
        raise ValueError("timeout must be positive")
    header = load_anec_header(args.anec)
    content_size, td_size, header_td_count, tsk_size, kernel_size, src_count, dst_count = header[:7]
    td_count = header_td_count if args.td_count is None else args.td_count
    tiles = header[7:39]
    nchw = header[39:]
    source_meta = nchw[SRC_BDX * 6:SRC_BDX * 6 + 6]
    output_meta = nchw[DST_BDX * 6:DST_BDX * 6 + 6]
    source_size = tiles[SRC_BDX] * TILE_SIZE
    output_size = tiles[DST_BDX] * TILE_SIZE
    if src_count != 1 or dst_count != 1:
        raise ValueError(f"expected one input and output, got {src_count}/{dst_count}")
    if td_count < 1 or td_size < 1 or tsk_size < td_size:
        raise ValueError("invalid task geometry")
    print(
        f"content={content_size:#x} task-stream={tsk_size:#x} td={td_size:#x} "
        f"td-count={td_count} kernel={kernel_size:#x} source={source_size:#x} "
        f"output={output_size:#x} source-nchw={tuple(source_meta)} "
        f"output-nchw={tuple(output_meta)}"
    )
    runtime = load_runtime()

    with args.anec.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as data, ExitStack() as stack:
        bases = task_bases(data, HEADER_SIZE, tsk_size)
        if len(bases) != header_td_count:
            raise ValueError(f"header has {header_td_count} tasks, found {len(bases)}")
        if args.td_start < 0 or args.td_start + td_count > header_td_count:
            raise ValueError("td range is out of range")
        selected_bases = bases[args.td_start:]
        device = stack.enter_context(runtime.Device(qid=None))
        command = stack.enter_context(device.buffer(content_size))
        copy_content(data, HEADER_SIZE, content_size, command.map)
        source = stack.enter_context(device.buffer(source_size))
        output = stack.enter_context(device.buffer(output_size))
        btsp = stack.enter_context(device.buffer((td_count - 1) * 0x300 + td_size))
        source_fill = np.full(source_size // 2, args.input_value, dtype=np.float16)
        source.write(source_fill.tobytes())
        del source_fill
        source_sentinel = np.float16(args.input_value)
        output_fill = np.full(output_size // 2, np.inf, dtype=np.float16)
        output.write(output_fill.tobytes())
        del output_fill
        bootstrap = build_bootstrap(
            data, HEADER_SIZE, selected_bases, td_size, td_count
        )
        btsp.write(bootstrap)
        del bootstrap
        first_word = struct.unpack_from("<I", btsp.map)[0]
        btsp.map.seek(0)
        btsp.map.write(struct.pack("<I", (first_word & 0xF00FFFF) | (0x40 << 16)))

        request = runtime.Submit(
            tsk_size=tsk_size,
            td_count=td_count,
            td_size=td_size,
            btsp_handle=btsp.bo.handle,
            pad=0x81,
        )
        request.handles[0] = command.bo.handle
        request.handles[4] = source.bo.handle
        request.handles[5] = output.bo.handle
        ioctl(device.fd, runtime.IOCTL_SUBMIT, request)
        poll_values = np.frombuffer(output.map, dtype=np.float16, count=output_size // 2)
        deadline = time.monotonic() + args.timeout
        while not np.any(poll_values != np.float16(np.inf)) and time.monotonic() < deadline:
            time.sleep(0.001)
        completed = bool(np.any(poll_values != np.float16(np.inf)))
        del poll_values
        output_bytes = output.read(output_size)
        if args.dump_output is not None:
            args.dump_output.write_bytes(output_bytes)
        output_values = np.frombuffer(output_bytes, dtype=np.float16)
        source_values = np.frombuffer(source.read(source_size), dtype=np.float16)
        changed_mask = output_values != np.float16(np.inf)
        changed_indices = np.flatnonzero(changed_mask)
        source_changed_indices = np.flatnonzero(source_values != source_sentinel)
        result = output_values[changed_indices[:16]].astype(np.float32)
        source_result = source_values[source_changed_indices[:16]].astype(np.float32)
        finite_values = output_values[changed_mask]
        finite = bool(np.isfinite(finite_values).all()) if changed_indices.size else False
        wrote_output = bool(changed_indices.size)
        stats_values = finite_values.astype(np.float32) if changed_indices.size else finite_values
        stats = (
            tuple(float(getattr(stats_values, name)()) for name in ("min", "max", "mean", "std"))
            if changed_indices.size
            else (float("nan"),) * 4
        )
        del stats_values
        print(
            f"output-head={result.tolist()} changed={changed_indices.size} "
            f"input-head={source_result.tolist()} input-changed={source_changed_indices.size} "
            f"range=({stats[0]:.6f},{stats[1]:.6f}) mean={stats[2]:.6f} std={stats[3]:.6f} "
            f"finite={finite} completed={completed} wrote-output={wrote_output}"
        )
        del source_values, output_values
        if not completed or not wrote_output or not finite:
            raise SystemExit(1)
        print("PRODUCTION_ANEC_EXECUTION_OK")


if __name__ == "__main__":
    main()
