#!/usr/bin/env python3
"""Submit a streamed production ANEC graph through the Linux ANE KMD."""

import argparse
import hashlib
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
WORKSPACE_BDX = 3
SRC_BDX = 5
DST_BDX = 4
TEN_WORD_ENVELOPE_SIZE = 0x28
TD_SIZE = 0x274
NEXT_POINTER_OFFSET = 0x1C
TASK_ID_MASK = 0xFFFF


def load_runtime():
    runtime_path = Path(os.environ.get("ANE_RUNTIME_PATH", ROOT / "ane-runtime.py"))
    spec = importlib.util.spec_from_file_location("ane_runtime", runtime_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ane-runtime.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


def load_artifact_parser():
    parser_path = Path(__file__).with_name("hwxv2-to-anec.py")
    spec = importlib.util.spec_from_file_location("hwxv2_to_anec", parser_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load hwxv2-to-anec.py")
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    return parser


def parse_int(value):
    return int(value, 0)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("anec", type=Path)
    parser.add_argument("--input-value", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--qid", type=int, choices=range(8))
    parser.add_argument("--td-count", type=int)
    parser.add_argument("--td-size", type=parse_int)
    parser.add_argument("--td-start", type=int, default=0)
    parser.add_argument("--dump-output", type=Path)
    parser.add_argument("--expect-sha256", metavar="SHA256")
    splice_group = parser.add_mutually_exclusive_group()
    splice_group.add_argument(
        "--task-zero-envelope",
        type=Path,
        metavar="CONTROL_ANEC",
        help=(
            "replace task zero's ten-word envelope with CONTROL_ANEC's "
            "before submit"
        ),
    )
    splice_group.add_argument(
        "--task-zero-descriptor",
        type=Path,
        metavar="CONTROL_ANEC",
        help=(
            "replace task zero's whole 0x274-byte descriptor with "
            "CONTROL_ANEC's before submit"
        ),
    )
    return parser.parse_args()


def load_anec_header(path):
    with path.open("rb") as stream:
        header = stream.read(ANEC_HEADER.size)
    if len(header) != ANEC_HEADER.size:
        raise ValueError("ANEC header is truncated")
    return ANEC_HEADER.unpack(header)

def read_control_stream(path, task_stream_size):
    with Path(path).open("rb") as stream:
        stream.seek(HEADER_SIZE)
        data = stream.read(task_stream_size)
    if len(data) != task_stream_size:
        raise ValueError("control artifact task stream is truncated")
    return data

def stage_geometry(header):
    """Decode the production buffer roles from one ANEC header."""
    (
        content_size,
        td_size,
        td_count,
        task_stream_size,
        kernel_size,
        src_count,
        dst_count,
    ) = header[:7]
    tiles = header[7:39]
    nchw = header[39:]
    return {
        "content_size": content_size,
        "td_size": td_size,
        "td_count": td_count,
        "task_stream_size": task_stream_size,
        "kernel_size": kernel_size,
        "src_count": src_count,
        "dst_count": dst_count,
        "workspace_size": tiles[WORKSPACE_BDX] * TILE_SIZE,
        "source_size": tiles[SRC_BDX] * TILE_SIZE,
        "output_size": tiles[DST_BDX] * TILE_SIZE,
        "source_nchw": tuple(nchw[SRC_BDX * 6:SRC_BDX * 6 + 6]),
        "output_nchw": tuple(nchw[DST_BDX * 6:DST_BDX * 6 + 6]),
    }


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_expected_hash(path, expected):
    """Raise before submission when the artifact digest misses the manifest."""
    actual = file_sha256(path)
    if expected is not None and actual != expected:
        raise ValueError(
            f"{path} sha256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def validate_handoff(head, tail):
    """Require the tail input contract to match the saved head output."""
    if head["output_nchw"] != tail["source_nchw"]:
        raise ValueError(
            f"handoff shape mismatch: head output {head['output_nchw']} "
            f"!= tail source {tail['source_nchw']}"
        )
    if tail["source_size"] > head["output_size"]:
        raise ValueError(
            f"tail source buffer {tail['source_size']:#x} exceeds saved "
            f"head output {head['output_size']:#x}"
        )
    if head["workspace_size"] == 0 or tail["workspace_size"] == 0:
        raise ValueError("chain stages must declare a workspace")

def validate_splice_geometry(
    target_stage, target_size, control_stage, control_size, min_td=TEN_WORD_ENVELOPE_SIZE
):
    """Reject malformed splice inputs before any device opens."""
    for name, stage, size in (
        ("target", target_stage, target_size),
        ("control", control_stage, control_size),
    ):
        if size < HEADER_SIZE + stage["task_stream_size"]:
            raise ValueError(f"{name} artifact is truncated")
        if stage["td_size"] < min_td:
            raise ValueError(
                f"{name} td {stage['td_size']:#x} is smaller than required {min_td:#x}"
            )
        if stage["task_stream_size"] < stage["td_size"]:
            raise ValueError(
                f"{name} task stream is smaller than its descriptor"
            )

def copy_content(data, offset, size, destination):
    destination.seek(0)
    copied = 0
    while copied < size:
        chunk_size = min(16 * 1024 * 1024, size - copied)
        destination.write(data[offset + copied:offset + copied + chunk_size])
        copied += chunk_size

def copy_task_stream(data, content_start, task_stream_size):
    content_end = content_start + task_stream_size
    if content_start < 0 or task_stream_size < 1 or content_end > len(data):
        raise ValueError("task stream exceeds the artifact")
    return bytes(data[content_start:content_end])

def splice_task_zero_envelope(target, control, target_base=0, control_base=0):
    """Replace task zero's ten-word envelope with the control's.

    The first ten words of a task descriptor carry the submission protocol.
    Word 0's low half is the task id and NEXT_POINTER_OFFSET holds the
    NextPointer; both route the target's own chain, so they survive the
    copy. Every other envelope word is the control's; every byte past the
    envelope stays the target's.
    """
    for name, data, base in (
        ("target", target, target_base),
        ("control", control, control_base),
    ):
        if base < 0 or base + TEN_WORD_ENVELOPE_SIZE > len(data):
            raise ValueError(
                f"{name} artifact is truncated below one ten-word envelope"
            )
    patched = bytearray(target)
    source = control[control_base:control_base + TEN_WORD_ENVELOPE_SIZE]
    patched[target_base:target_base + TEN_WORD_ENVELOPE_SIZE] = source
    control_word = struct.unpack_from("<I", control, control_base)[0]
    target_word = struct.unpack_from("<I", target, target_base)[0]
    struct.pack_into(
        "<I",
        patched,
        target_base,
        (control_word & ~TASK_ID_MASK) | (target_word & TASK_ID_MASK),
    )
    next_pointer = struct.unpack_from(
        "<I", target, target_base + NEXT_POINTER_OFFSET
    )[0]
    struct.pack_into(
        "<I", patched, target_base + NEXT_POINTER_OFFSET, next_pointer
    )
    return bytes(patched)

def splice_task_zero_descriptor(target, control, target_base=0, control_base=0):
    """Replace task zero's whole descriptor with the control's.

    TD_SIZE bytes carry the full task-zero body: envelope, kernel
    bindings, and weights references. Word 0's low half is the task id
    and NEXT_POINTER_OFFSET holds the NextPointer; both route the
    target's own chain, so they survive the copy. Every byte past the
    descriptor stays the target's.
    """
    for name, data, base in (
        ("target", target, target_base),
        ("control", control, control_base),
    ):
        if base < 0 or base + TD_SIZE > len(data):
            raise ValueError(
                f"{name} artifact is truncated below one descriptor"
            )
    patched = bytearray(target)
    source = control[control_base:control_base + TD_SIZE]
    patched[target_base:target_base + TD_SIZE] = source
    control_word = struct.unpack_from("<I", control, control_base)[0]
    target_word = struct.unpack_from("<I", target, target_base)[0]
    struct.pack_into(
        "<I",
        patched,
        target_base,
        (control_word & ~TASK_ID_MASK) | (target_word & TASK_ID_MASK),
    )
    next_pointer = struct.unpack_from(
        "<I", target, target_base + NEXT_POINTER_OFFSET
    )[0]
    struct.pack_into(
        "<I", patched, target_base + NEXT_POINTER_OFFSET, next_pointer
    )
    return bytes(patched)

def submission_pad(qid):
    return 0 if qid is None else 0x80 | qid

def task_bases(data, start, size):
    return load_artifact_parser().find_task_offsets(data, start, size)

def terminate_task(task_stream, task_start):
    if task_start < 0 or task_start + 0x20 > len(task_stream):
        raise ValueError("terminal task header exceeds the task stream")
    terminal_header = struct.unpack_from("<I", task_stream, task_start)[0]
    struct.pack_into(
        "<I", task_stream, task_start, terminal_header | 0x03000000
    )
    terminal_next_size = struct.unpack_from("<H", task_stream, task_start + 6)[0]
    struct.pack_into(
        "<H", task_stream, task_start + 6, terminal_next_size & ~0x1FF
    )
    struct.pack_into("<I", task_stream, task_start + 0x1C, 0)


def build_original_prefix(data, content_start, task_stream_size, bases, td_count):
    if td_count < 1 or len(bases) < td_count:
        raise ValueError(f"ANEC has {len(bases)} task descriptors, needs {td_count}")
    bootstrap = bytearray(copy_task_stream(data, content_start, task_stream_size))
    terminate_task(bootstrap, bases[td_count - 1])
    return bytes(bootstrap)


def build_bootstrap(
    data, content_start, task_stream_size, bases, td_size, td_count
):
    if len(bases) < td_count:
        raise ValueError(f"ANEC has {len(bases)} task descriptors, needs {td_count}")
    selected_bases = bases[:td_count]
    source_to_destination = {
        base: index * 0x300 for index, base in enumerate(selected_bases)
    }
    bootstrap = bytearray((td_count - 1) * 0x300 + td_size)
    for index, base in enumerate(selected_bases):
        available = task_stream_size - base
        if available < 0x20:
            raise ValueError(f"task {index} header exceeds the task stream")
        source_start = content_start + base
        destination_start = index * 0x300
        copy_size = min(td_size, available)
        bootstrap[destination_start:destination_start + copy_size] = data[
            source_start:source_start + copy_size
        ]
        task_header = struct.unpack_from("<I", bootstrap, destination_start)[0]
        struct.pack_into(
            "<I",
            bootstrap,
            destination_start,
            (task_header & ~0xFFFF) | index,
        )
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
    terminate_task(bootstrap, (td_count - 1) * 0x300)
    return bytes(bootstrap)


def main():
    args = parse_args()
    if args.timeout <= 0:
        raise ValueError("timeout must be positive")
    stage = stage_geometry(load_anec_header(args.anec))
    if args.expect_sha256 is not None:
        validate_expected_hash(args.anec, args.expect_sha256)
    content_size = stage["content_size"]
    tsk_size = stage["task_stream_size"]
    td_size = stage["td_size"] if args.td_size is None else args.td_size
    td_count = stage["td_count"] if args.td_count is None else args.td_count
    source_meta = stage["source_nchw"]
    output_meta = stage["output_nchw"]
    workspace_size = stage["workspace_size"]
    source_size = stage["source_size"]
    output_size = stage["output_size"]
    if stage["src_count"] != 1 or stage["dst_count"] != 1:
        raise ValueError(
            f"expected one input and output, got "
            f"{stage['src_count']}/{stage['dst_count']}"
        )
    if td_count < 1 or td_size < 1 or tsk_size < td_size:
        raise ValueError("invalid task geometry")
    splice_control = args.task_zero_envelope
    min_td = TEN_WORD_ENVELOPE_SIZE
    if args.task_zero_descriptor is not None:
        splice_control = args.task_zero_descriptor
        min_td = TD_SIZE
    if splice_control is not None:
        control_stage = stage_geometry(load_anec_header(splice_control))
        validate_splice_geometry(
            stage,
            args.anec.stat().st_size,
            control_stage,
            splice_control.stat().st_size,
            min_td=min_td,
        )
        control_stream = read_control_stream(
            splice_control, control_stage["task_stream_size"]
        )
        control_bases = task_bases(control_stream, 0, len(control_stream))
        if len(control_bases) != control_stage["td_count"]:
            raise ValueError(
                f"control header has {control_stage['td_count']} tasks, "
                f"found {len(control_bases)}"
            )
    original_task_layout = args.td_start == 0
    print(
        f"content={content_size:#x} task-stream={tsk_size:#x} td={td_size:#x} "
        f"td-count={td_count} task-layout={'original' if original_task_layout else 'packed'} "
        f"qid={args.qid if args.qid is not None else 'default'} "
        f"kernel={stage['kernel_size']:#x} workspace={workspace_size:#x} "
        f"source={source_size:#x} output={output_size:#x} "
        f"source-nchw={tuple(source_meta)} output-nchw={tuple(output_meta)}"
    )
    runtime = load_runtime()

    with args.anec.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as data, ExitStack() as stack:
        bases = task_bases(data, HEADER_SIZE, tsk_size)
        if len(bases) != stage["td_count"]:
            raise ValueError(
                f"header has {stage['td_count']} tasks, found {len(bases)}"
            )
        if args.td_start < 0 or args.td_start + td_count > stage["td_count"]:
            raise ValueError("td range is out of range")
        selected_bases = bases[args.td_start:]
        patched_stream = None
        if args.task_zero_envelope is not None:
            patched_stream = splice_task_zero_envelope(
                copy_task_stream(data, HEADER_SIZE, tsk_size),
                control_stream,
                target_base=bases[0],
                control_base=control_bases[0],
            )
            print(
                f"task-zero-envelope={args.task_zero_envelope} "
                f"sha256={file_sha256(args.task_zero_envelope)}"
            )
        elif args.task_zero_descriptor is not None:
            patched_stream = splice_task_zero_descriptor(
                copy_task_stream(data, HEADER_SIZE, tsk_size),
                control_stream,
                target_base=bases[0],
                control_base=control_bases[0],
            )
            print(
                f"task-zero-descriptor={args.task_zero_descriptor} "
                f"sha256={file_sha256(args.task_zero_descriptor)}"
            )
        device = stack.enter_context(runtime.Device(qid=args.qid))
        command = stack.enter_context(device.buffer(content_size))
        copy_content(data, HEADER_SIZE, content_size, command.map)
        if patched_stream is not None:
            command.map.seek(0)
            command.map.write(patched_stream)
        source = stack.enter_context(device.buffer(source_size))
        output = stack.enter_context(device.buffer(output_size))
        workspace = (
            stack.enter_context(device.buffer(workspace_size))
            if workspace_size
            else None
        )
        if workspace is not None:
            workspace.write(b"\0" * workspace_size)
        btsp_size = (
            tsk_size
            if original_task_layout
            else (td_count - 1) * 0x300 + td_size
        )
        btsp = stack.enter_context(device.buffer(btsp_size))
        source_fill = np.full(source_size // 2, args.input_value, dtype=np.float16)
        source.write(source_fill.tobytes())
        del source_fill
        source_sentinel = np.float16(args.input_value)
        output_fill = np.full(output_size // 2, np.inf, dtype=np.float16)
        output.write(output_fill.tobytes())
        del output_fill
        td_source = patched_stream if patched_stream is not None else data
        td_start = 0 if patched_stream is not None else HEADER_SIZE
        bootstrap = (
            build_original_prefix(
                td_source, td_start, tsk_size, bases, td_count
            )
            if original_task_layout
            else build_bootstrap(
                td_source, td_start, tsk_size, selected_bases, td_size, td_count
            )
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
            pad=submission_pad(args.qid),
        )
        request.handles[0] = command.bo.handle
        if workspace is not None:
            request.handles[WORKSPACE_BDX] = workspace.bo.handle
        request.handles[4] = source.bo.handle
        request.handles[5] = output.bo.handle
        ioctl(device.fd, runtime.IOCTL_SUBMIT, request)
        poll_values = np.frombuffer(
            output.map, dtype=np.float16, count=output_size // 2
        )
        deadline = time.monotonic() + args.timeout
        while (
            not np.any(poll_values != np.float16(np.inf))
            and time.monotonic() < deadline
        ):
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
        stats_values = (
            finite_values.astype(np.float32) if changed_indices.size else finite_values
        )
        stats = (
            tuple(
                float(getattr(stats_values, name)())
                for name in ("min", "max", "mean", "std")
            )
            if changed_indices.size
            else (float("nan"),) * 4
        )
        del stats_values
        print(
            f"output-head={result.tolist()} changed={changed_indices.size} "
            f"input-head={source_result.tolist()} input-changed={source_changed_indices.size} "
            f"range=({stats[0]:.6f},{stats[1]:.6f}) mean={stats[2]:.6f} "
            f"std={stats[3]:.6f} finite={finite} completed={completed} "
            f"wrote-output={wrote_output}"
        )
        del source_values, output_values
        if not completed or not wrote_output or not finite:
            raise SystemExit(1)
        print("PRODUCTION_ANEC_EXECUTION_OK")


if __name__ == "__main__":
    main()
