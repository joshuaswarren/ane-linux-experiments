#!/usr/bin/env python3
"""Submit a converted fresh-format ANEC graph through the raw Linux path."""

import argparse
import importlib.util
import struct
from contextlib import ExitStack
from fcntl import ioctl
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
PLANE_STRIDE = 0x40
BO_SIZE = 0x4000


def load_runtime():
    spec = importlib.util.spec_from_file_location("ane_runtime", ROOT / "ane-runtime.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ane-runtime.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("anec", type=Path)
    parser.add_argument("--input-channels", type=int, required=True)
    parser.add_argument("--output-channels", type=int, required=True)
    parser.add_argument("--expect-output-channel", type=int, required=True)
    parser.add_argument("--expect-input-channel", type=int, required=True)
    parser.add_argument("--value-base", type=float, default=10.0)
    parser.add_argument("--tolerance", type=float, default=0.02)
    return parser.parse_args()


def main():
    args = parse_args()
    max_channels = BO_SIZE // PLANE_STRIDE
    if not 1 <= args.input_channels <= max_channels:
        raise ValueError(f"input channels must be in 1..{max_channels}")
    if not 1 <= args.output_channels <= max_channels:
        raise ValueError(f"output channels must be in 1..{max_channels}")
    if not 0 <= args.expect_input_channel < args.input_channels:
        raise ValueError("expected input channel is out of range")
    if not 0 <= args.expect_output_channel < args.output_channels:
        raise ValueError("expected output channel is out of range")
    if args.tolerance < 0:
        raise ValueError("tolerance must not be negative")

    runtime = load_runtime()
    full = args.anec.read_bytes()
    content_size, td_size, td_count, tsk_size, kernel_size, _, _ = struct.unpack_from(
        "<QIIQQII", full
    )
    content = full[0x1000 : 0x1000 + content_size]
    source = np.zeros(BO_SIZE // 2, dtype=np.float16)
    values = args.value_base + np.arange(args.input_channels, dtype=np.float16)
    for channel, value in enumerate(values):
        source[channel * PLANE_STRIDE // 2] = value
    output = np.full(BO_SIZE // 2, np.inf, dtype=np.float16)

    with ExitStack() as stack:
        device = stack.enter_context(runtime.Device(qid=None))
        command = stack.enter_context(device.buffer(len(content)))
        result = stack.enter_context(device.buffer(BO_SIZE))
        source_bo = stack.enter_context(device.buffer(BO_SIZE))
        btsp = stack.enter_context(device.buffer(BO_SIZE))
        command.write(content)
        source_bo.write(source.tobytes())
        result.write(output.tobytes())
        btsp.write(content[:td_size])
        first_word = struct.unpack_from("<I", btsp.read(4))[0]
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
        request.handles[2] = command.bo.handle
        request.handles[4] = source_bo.bo.handle
        request.handles[5] = result.bo.handle
        ioctl(device.fd, runtime.IOCTL_SUBMIT, request)

        values_out = np.frombuffer(result.read(BO_SIZE), dtype=np.float16).astype(np.float32)
        output_planes = values_out[np.arange(args.output_channels) * (PLANE_STRIDE // 2)]
        expected = float(values[args.expect_input_channel])
        observed = float(output_planes[args.expect_output_channel])
        error = abs(observed - expected)
        print(f"anec content={content_size:#x} td={td_size:#x} kernel={kernel_size:#x}")
        print(f"expected output[{args.expect_output_channel}]={expected:.4f}")
        print(f"observed output[{args.expect_output_channel}]={observed:.4f}")
        print(f"max_err={error:.4f} finite={bool(np.isfinite(output_planes).all())}")
        print("FRESH_ANEC_PARITY_OK" if error <= args.tolerance else "FRESH_ANEC_PARITY_FAIL")
        if error > args.tolerance:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
