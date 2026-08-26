#!/usr/bin/env python3
"""Small resource-safe userspace runtime for the experimental ANE KMD.

This is the layer the earlier scripts were missing. It owns the DRM fd and
all BO lifetimes, submits a real task descriptor, waits for the output DMA,
and frees every BO before returning. It does not generate model descriptors;
the caller supplies a descriptor template from an operation builder.

The included self-test loads the sibling ``ane-network.py`` descriptor
builder, runs one real 512x256 gemm, and checks the result against numpy:

    python3 ane-runtime.py
    python3 ane-runtime.py --qid 0

``--qid`` needs the qid-enabled KMD patch. Omit it for the original KMD.
"""
import argparse
import contextlib
import ctypes
import importlib.util
import mmap
import os
import sys
import time
from fcntl import ioctl

import numpy as np

ANE_TILE_COUNT = 0x20
DRM_ANE_BO_INIT = 0x41
DRM_ANE_BO_FREE = 0x42
DRM_ANE_SUBMIT = 0x43
TD_SIZE = 0x274
TD_SPACING = 0x300
WEIGHT_OFFSET = 0x274
WEIGHT_BYTES = 0x80000
CMD_BYTES = 0x8000
SRC_BYTES = 0x4000
OUT_BYTES = 0x8000
WAIT_S = 1.0


class BoInit(ctypes.Structure):
    _fields_ = [
        ("handle", ctypes.c_uint32),
        ("pad", ctypes.c_uint32),
        ("size", ctypes.c_uint64),
        ("offset", ctypes.c_uint64),
    ]


class BoFree(ctypes.Structure):
    _fields_ = [("handle", ctypes.c_uint32), ("pad", ctypes.c_uint32)]


class Submit(ctypes.Structure):
    _fields_ = [
        ("tsk_size", ctypes.c_uint64),
        ("td_count", ctypes.c_uint32),
        ("td_size", ctypes.c_uint32),
        ("handles", ctypes.c_uint32 * ANE_TILE_COUNT),
        ("btsp_handle", ctypes.c_uint32),
        ("pad", ctypes.c_uint32),
    ]


def _iowr(nr, size):
    return (3 << 30) | (0x64 << 8) | (size << 16) | nr


IOCTL_BO_INIT = _iowr(DRM_ANE_BO_INIT, ctypes.sizeof(BoInit))
IOCTL_BO_FREE = _iowr(DRM_ANE_BO_FREE, ctypes.sizeof(BoFree))
IOCTL_SUBMIT = _iowr(DRM_ANE_SUBMIT, ctypes.sizeof(Submit))


class Buffer:
    """One mmap-backed ANE BO. Closes the map, then frees the kernel BO."""

    def __init__(self, fd, size):
        self.fd = fd
        self.size = size
        self.bo = BoInit(size=size)
        ioctl(fd, IOCTL_BO_INIT, self.bo)
        self.map = mmap.mmap(
            fd, size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE,
            offset=self.bo.offset,
        )
        self.closed = False

    def write(self, data):
        if len(data) > self.size:
            raise ValueError(f"buffer overflow: {len(data)} > {self.size}")
        self.map.seek(0)
        self.map.write(data)

    def read(self, size=None):
        size = self.size if size is None else size
        self.map.seek(0)
        return self.map.read(size)

    def close(self):
        if self.closed:
            return
        self.map.close()
        ioctl(self.fd, IOCTL_BO_FREE, BoFree(handle=self.bo.handle))
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class Device:
    """Own the ANE fd and submit operation descriptors safely."""

    def __init__(self, path="/dev/accel/accel0", qid=None):
        self.fd = os.open(path, os.O_RDWR)
        self.qid = qid
        if qid is not None and not 0 <= qid < 8:
            os.close(self.fd)
            raise ValueError("qid must be in 0..7")

    def buffer(self, size):
        return Buffer(self.fd, size)

    def submit(self, command, source, output_size, descriptor, td_count=1):
        """Run one operation and return its fp16 output bytes.

        ``command`` contains the TD template plus its kernel weights.
        ``source`` is the TileDMA source BO. ``descriptor`` is the BTSP
        template. ``td_count`` descriptors are placed 0x300 apart.
        """
        if len(descriptor) < TD_SIZE:
            raise ValueError("descriptor is shorter than td_size")
        if td_count < 1:
            raise ValueError("td_count must be positive")
        tsk_size = (td_count - 1) * TD_SPACING + TD_SIZE
        if len(command) <= tsk_size:
            raise ValueError("command buffer has no KRN region")

        sentinel = b"\x00\x7c"
        btsp_size = (td_count - 1) * TD_SPACING + len(descriptor)
        with self.buffer(len(command)) as cmd, self.buffer(output_size) as out:
            out.write(sentinel * (output_size // 2))
            with self.buffer(len(source)) as src, self.buffer(btsp_size) as btsp:
                cmd.write(command)
                src.write(source)
                btsp_bytes = bytearray(btsp_size)
                for i in range(td_count):
                    start = i * TD_SPACING
                    btsp_bytes[start:start + len(descriptor)] = descriptor
                btsp.write(bytes(btsp_bytes))

                request = Submit(
                    tsk_size=tsk_size,
                    td_count=td_count,
                    td_size=TD_SIZE,
                    btsp_handle=btsp.bo.handle,
                    pad=0 if self.qid is None else 0x80 | self.qid,
                )
                request.handles[0] = cmd.bo.handle
                request.handles[4] = out.bo.handle
                request.handles[5] = src.bo.handle

                deadline = time.monotonic() + WAIT_S
                ioctl(self.fd, IOCTL_SUBMIT, request)
                while out.map[:2] == sentinel and time.monotonic() < deadline:
                    pass
                result = out.read(output_size)
                if result[:2] == sentinel:
                    raise TimeoutError("ANE output was not written before timeout")
                return result

    def gemm(self, weights, activation, descriptor):
        """Run one 512x256 fp16 gemm using a supplied descriptor template."""
        weights = np.asarray(weights, dtype=np.float16)
        activation = np.asarray(activation, dtype=np.float16)
        if weights.nbytes != WEIGHT_BYTES:
            raise ValueError(f"weights must be {WEIGHT_BYTES} bytes")
        if activation.size != 256:
            raise ValueError("activation must contain 256 fp16 values")
        command = bytearray(CMD_BYTES)
        command[:len(descriptor)] = descriptor
        command[WEIGHT_OFFSET:WEIGHT_OFFSET + WEIGHT_BYTES] = weights.tobytes()
        source = np.zeros(SRC_BYTES // 2, dtype=np.float16)
        source[:256 * 32:32] = activation
        raw = self.submit(bytes(command), source.tobytes(), OUT_BYTES, descriptor)
        return np.frombuffer(raw, dtype=np.float16)[:512 * 32:32].copy()

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def load_descriptor(path):
    """Load an operation builder without running its main function."""
    spec = importlib.util.spec_from_file_location("ane_operation", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    saved_argv = sys.argv
    sys.argv = [path]
    try:
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink):
            spec.loader.exec_module(module)
        return module.gemm_btsp()
    finally:
        sys.argv = saved_argv
        os.close(module.fd)
def self_test(qid=None):
    descriptor_path = os.path.join(os.path.dirname(__file__), "ane-network.py")
    descriptor = load_descriptor(descriptor_path)
    weights = np.full(WEIGHT_BYTES // 2, np.float16(0.5))
    activation = np.ones(256, dtype=np.float16)
    with Device(qid=qid) as device:
        got = device.gemm(weights, activation, descriptor)
    expected = np.full(512, np.float16(128.0))
    max_err = np.abs(got.astype(np.float32) - expected).max()
    ok = bool(np.array_equal(got, expected))
    print(f"runtime_gemm max_err={max_err:.4f} output_ok={ok} qid={qid if qid is not None else 4}")
    if not ok:
        raise SystemExit(1)
    print("ANE_RUNTIME_OK")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qid", type=int, default=None,
                        help="explicit queue for qid-enabled KMD")
    args = parser.parse_args()
    self_test(args.qid)


if __name__ == "__main__":
    main()
