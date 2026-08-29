#!/usr/bin/env python3
"""Execute production ANEC descriptors as separate stateful submits."""

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
PROBE_PATH = Path(__file__).with_name("production-anec-probe.py")
RUNTIME_PATH = ROOT / "ane-runtime.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("anec", type=Path)
    parser.add_argument("--td-start", type=int, default=0)
    parser.add_argument("--td-count", type=int)
    parser.add_argument("--input-value", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.timeout <= 0:
        raise ValueError("timeout must be positive")
    probe = load_module("production_anec_probe", PROBE_PATH)
    runtime = load_module("ane_runtime", Path(os.environ.get("ANE_RUNTIME_PATH", RUNTIME_PATH)))
    header = probe.load_anec_header(args.anec)
    content_size, td_size, header_count, task_stream_size, _, _, _ = header[:7]
    count = header_count - args.td_start if args.td_count is None else args.td_count
    if args.td_start < 0 or count < 1 or args.td_start + count > header_count:
        raise ValueError("task range is out of bounds")
    tiles = header[7:39]
    source_size = tiles[probe.SRC_BDX] * probe.TILE_SIZE
    output_size = tiles[probe.DST_BDX] * probe.TILE_SIZE
    with args.anec.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as data, ExitStack() as stack:
        bases = probe.task_bases(data, probe.HEADER_SIZE, task_stream_size)
        device = stack.enter_context(runtime.Device(qid=None))
        command = stack.enter_context(device.buffer(content_size))
        probe.copy_content(data, probe.HEADER_SIZE, content_size, command.map)
        source = stack.enter_context(device.buffer(source_size))
        output = stack.enter_context(device.buffer(output_size))
        btsp = stack.enter_context(device.buffer(td_size))
        source.write(
            np.full(source_size // 2, args.input_value, dtype=np.float16).tobytes()
        )
        sentinel = np.full(output_size // 2, np.inf, dtype=np.float16).tobytes()
        output.write(sentinel)
        for index in range(args.td_start, args.td_start + count):
            bootstrap = probe.build_bootstrap(
                data, probe.HEADER_SIZE, task_stream_size, bases[index:], td_size, 1
            )
            btsp.write(bootstrap)
            first_word = struct.unpack_from("<I", bootstrap)[0]
            btsp.map.seek(0)
            btsp.map.write(struct.pack("<I", (first_word & 0xF00FFFF) | (0x40 << 16)))
            request = runtime.Submit(
                tsk_size=task_stream_size,
                td_count=1,
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
            result = np.frombuffer(output.read(output_size), dtype=np.float16)
            changed = result != np.float16(np.inf)
            values = result[changed]
            finite = bool(np.isfinite(values).all()) if values.size else False
            print(
                f"task={index} changed={int(changed.sum())} finite={finite} "
                f"completed={completed} head={values[:4].astype(np.float32).tolist()}"
            )
            if not completed or not changed.any() or not finite:
                raise SystemExit(1)
            source.write(result.tobytes()[:source_size])
            output.write(sentinel)


if __name__ == "__main__":
    main()
