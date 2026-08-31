#!/usr/bin/env python3
"""Execute production ANEC graphs as diagnostics or a chained head-tail pair."""

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
    parser.add_argument("--tail-anec", type=Path)
    parser.add_argument("--td-start", type=int, default=0)
    parser.add_argument("--td-count", type=int)
    parser.add_argument("--input-value", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--qid", type=int, choices=range(8))
    parser.add_argument("--expect-sha256", action="append", metavar="SHA256")
    parser.add_argument("--save-state", type=Path)
    parser.add_argument("--dump-output", type=Path)
    return parser.parse_args()


def validate_chain(probe, args):
    """Run every artifact and handoff check before any device opens."""
    stages = [args.anec, args.tail_anec]
    expected = args.expect_sha256 or []
    if len(expected) > len(stages):
        raise ValueError("more hashes than chain stages")
    for path, digest in zip(stages, expected):
        probe.validate_expected_hash(path, digest)
    head = probe.stage_geometry(probe.load_anec_header(args.anec))
    tail = probe.stage_geometry(probe.load_anec_header(args.tail_anec))
    for stage in (head, tail):
        if stage["src_count"] != 1 or stage["dst_count"] != 1:
            raise ValueError(
                f"expected one input and output, got "
                f"{stage['src_count']}/{stage['dst_count']}"
            )
        if stage["td_count"] < 1 or stage["td_size"] < 1:
            raise ValueError("invalid task geometry")
        if stage["task_stream_size"] < stage["td_size"]:
            raise ValueError("invalid task geometry")
        if stage["workspace_size"] == 0:
            raise ValueError("chain stage declares no workspace")
    probe.validate_handoff(head, tail)
    return head, tail


def run_chain_stage(device, runtime, probe, args, path, stage, source_fill):
    """Submit one full graph in original layout and return its output bytes."""
    with path.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as artifact, ExitStack() as buffers:
        bases = probe.task_bases(
            artifact, probe.HEADER_SIZE, stage["task_stream_size"]
        )
        if len(bases) != stage["td_count"]:
            raise ValueError(
                f"header has {stage['td_count']} tasks, found {len(bases)}"
            )
        command = buffers.enter_context(device.buffer(stage["content_size"]))
        probe.copy_content(
            artifact, probe.HEADER_SIZE, stage["content_size"], command.map
        )
        workspace = buffers.enter_context(
            device.buffer(stage["workspace_size"])
        )
        workspace.write(b"\0" * stage["workspace_size"])
        source = buffers.enter_context(device.buffer(stage["source_size"]))
        source.write(source_fill)
        output = buffers.enter_context(device.buffer(stage["output_size"]))
        output.write(
            np.full(stage["output_size"] // 2, np.inf, dtype=np.float16).tobytes()
        )
        bootstrap = probe.build_original_prefix(
            artifact,
            probe.HEADER_SIZE,
            stage["task_stream_size"],
            bases,
            stage["td_count"],
        )
        btsp = buffers.enter_context(device.buffer(stage["task_stream_size"]))
        btsp.write(bootstrap)
        first_word = struct.unpack_from("<I", btsp.map)[0]
        btsp.map.seek(0)
        btsp.map.write(
            struct.pack("<I", (first_word & 0xF00FFFF) | (0x40 << 16))
        )
        request = runtime.Submit(
            tsk_size=stage["task_stream_size"],
            td_count=stage["td_count"],
            td_size=stage["td_size"],
            btsp_handle=btsp.bo.handle,
            pad=probe.submission_pad(args.qid),
        )
        request.handles[0] = command.bo.handle
        request.handles[probe.WORKSPACE_BDX] = workspace.bo.handle
        request.handles[4] = source.bo.handle
        request.handles[5] = output.bo.handle
        ioctl(device.fd, runtime.IOCTL_SUBMIT, request)
        poll_values = np.frombuffer(
            output.map, dtype=np.float16, count=stage["output_size"] // 2
        )
        deadline = time.monotonic() + args.timeout
        while (
            not np.any(poll_values != np.float16(np.inf))
            and time.monotonic() < deadline
        ):
            time.sleep(0.001)
        completed = bool(np.any(poll_values != np.float16(np.inf)))
        del poll_values
        output_bytes = output.read(stage["output_size"])
        values = np.frombuffer(output_bytes, dtype=np.float16)
        changed = values != np.float16(np.inf)
        finite = bool(np.isfinite(values[changed]).all()) if changed.any() else False
        head = values[changed][:4].astype(np.float32).tolist()
        del values
        print(
            f"stage={path.name} changed={int(changed.sum())} finite={finite} "
            f"completed={completed} head={head}"
        )
        if not completed or not changed.any() or not finite:
            raise SystemExit(1)
        return output_bytes


def run_chain(args, probe, runtime):
    """Run the head graph, save its output state, then run the tail graph."""
    head_stage, tail_stage = validate_chain(probe, args)
    head_fill = np.full(
        head_stage["source_size"] // 2, args.input_value, dtype=np.float16
    ).tobytes()
    with ExitStack() as stack:
        device = stack.enter_context(runtime.Device(qid=args.qid))
        head_output = run_chain_stage(
            device, runtime, probe, args, args.anec, head_stage, head_fill
        )
        del head_fill
        if args.save_state is not None:
            args.save_state.write_bytes(head_output)
        tail_fill = head_output[: tail_stage["source_size"]]
        del head_output
        tail_output = run_chain_stage(
            device, runtime, probe, args, args.tail_anec, tail_stage, tail_fill
        )
        del tail_fill
        if args.dump_output is not None:
            args.dump_output.write_bytes(tail_output)
    print("PRODUCTION_ANEC_CHAIN_OK")


def main():
    args = parse_args()
    if args.timeout <= 0:
        raise ValueError("timeout must be positive")
    probe = load_module("production_anec_probe", PROBE_PATH)
    runtime = load_module("ane_runtime", Path(os.environ.get("ANE_RUNTIME_PATH", RUNTIME_PATH)))
    if args.tail_anec is not None:
        run_chain(args, probe, runtime)
        return
    header = probe.load_anec_header(args.anec)
    content_size, td_size, header_count, task_stream_size, _, _, _ = header[:7]
    count = header_count - args.td_start if args.td_count is None else args.td_count
    if args.td_start < 0 or count < 1 or args.td_start + count > header_count:
        raise ValueError("task range is out of bounds")
    tiles = header[7:39]
    source_size = tiles[probe.SRC_BDX] * probe.TILE_SIZE
    output_size = tiles[probe.DST_BDX] * probe.TILE_SIZE
    workspace_size = tiles[probe.WORKSPACE_BDX] * probe.TILE_SIZE
    with args.anec.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as data, ExitStack() as stack:
        bases = probe.task_bases(data, probe.HEADER_SIZE, task_stream_size)
        device = stack.enter_context(runtime.Device(qid=None))
        command = stack.enter_context(device.buffer(content_size))
        probe.copy_content(data, probe.HEADER_SIZE, content_size, command.map)
        source = stack.enter_context(device.buffer(source_size))
        output = stack.enter_context(device.buffer(output_size))
        workspace = (
            stack.enter_context(device.buffer(workspace_size))
            if workspace_size
            else None
        )
        if workspace is not None:
            workspace.write(b"\0" * workspace_size)
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
            if workspace is not None:
                request.handles[probe.WORKSPACE_BDX] = workspace.bo.handle
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
