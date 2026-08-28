#!/usr/bin/env python3
"""Small resource-safe userspace runtime for the experimental ANE KMD.

This is the layer the earlier scripts were missing. It owns the DRM fd and
the persistent BO workspace, submits a real task descriptor, waits for output
DMA, and frees every BO when the device closes. It does not generate model
descriptors; the caller supplies a descriptor template from an operation
builder.

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
WEIGHT_BYTES_512 = 0x100000
CMD_BYTES = 0x8000
SRC_BYTES = 0x4000
SRC_BYTES_512 = 0x8000
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


def _pack_buffer(size, out):
    if out is None:
        return np.zeros(size, dtype=np.float16)
    if out.shape != (size,) or out.dtype != np.float16:
        raise ValueError(f"output buffer must be float16 with {size} elements")
    out.fill(0)
    return out


def pack_weights(matrix, out=None):
    """Pack a canonical (512, 256) fp16 matrix into the ANE DMA blob."""
    matrix = np.asarray(matrix, dtype=np.float16)
    if matrix.shape != (512, 256):
        raise ValueError(f"weights must have shape (512, 256), got {matrix.shape}")
    blob = _pack_buffer(WEIGHT_BYTES // 2, out)
    for tile in range(16):
        base = tile * 16384 + 6
        blob[base:base + 256 * 32] = matrix[tile * 32:(tile + 1) * 32].T.reshape(-1)
    return blob


def pack_weights_512(matrix, out=None):
    """Pack a canonical (512, 512) fp16 matrix into the ANE DMA blob."""
    matrix = np.asarray(matrix, dtype=np.float16)
    if matrix.shape != (512, 512):
        raise ValueError(f"weights must have shape (512, 512), got {matrix.shape}")
    blob = _pack_buffer(WEIGHT_BYTES_512 // 2, out)
    for tile in range(16):
        base = tile * 16384
        blob[base:base + 512 * 32] = matrix[tile * 32:(tile + 1) * 32].T.reshape(-1)
    return blob


class Device:
    """Own the ANE fd and submit operation descriptors safely."""

    def __init__(self, path="/dev/accel/accel0", qid=None):
        self.fd = os.open(path, os.O_RDWR)
        self.qid = qid
        self._workspaces = {}
        self._tile_cache = {}
        self._blob_swap_cache = {}
        if qid is not None and not 0 <= qid < 8:
            os.close(self.fd)
            raise ValueError("qid must be in 0..7")

    def buffer(self, size):
        return Buffer(self.fd, size)

    def _workspace_for(self, command_size, source_size, output_size, btsp_size):
        """Cache one workspace per size key: alternating tile shapes used to
        tear down and rebuild four buffer objects on every call."""
        key = (command_size, source_size, output_size, btsp_size)
        cached = self._workspaces.get(key)
        if cached is None:
            cached = (
                self.buffer(command_size),
                self.buffer(output_size),
                self.buffer(source_size),
                self.buffer(btsp_size),
            )
            self._workspaces[key] = cached
        return cached

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
        cmd, out, src, btsp = self._workspace_for(
            len(command), len(source), output_size, btsp_size
        )
        out.write(sentinel * (output_size // 2))
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
        """Run one canonical 512x256 fp16 matrix-vector product."""
        activation = np.asarray(activation, dtype=np.float16)
        if activation.shape != (256,):
            raise ValueError(f"activation must have shape (256,), got {activation.shape}")
        packed = pack_weights(weights)
        command = bytearray(CMD_BYTES)
        command[:len(descriptor)] = descriptor
        command[WEIGHT_OFFSET:WEIGHT_OFFSET + WEIGHT_BYTES] = packed.tobytes()
        source = np.zeros(SRC_BYTES // 2, dtype=np.float16)
        source[:256 * 32:32] = activation
        raw = self.submit(bytes(command), source.tobytes(), OUT_BYTES, descriptor)
        return np.frombuffer(raw, dtype=np.float16)[:512 * 32:32].copy()


    def gemm512(self, weights, activation, descriptor):
        """Run one canonical 512x512 fp16 matrix-vector product."""
        activation = np.asarray(activation, dtype=np.float16)
        if activation.shape != (512,):
            raise ValueError(f"activation must have shape (512,), got {activation.shape}")
        packed = pack_weights_512(weights)
        command_size = ((TD_SIZE + 15) & ~15) + WEIGHT_BYTES_512
        command = bytearray(command_size)
        command[:len(descriptor)] = descriptor
        command[((TD_SIZE + 15) & ~15):] = packed.tobytes()
        source = np.zeros(SRC_BYTES_512 // 2, dtype=np.float16)
        source[:512 * 32:32] = activation
        raw = self.submit(bytes(command), source.tobytes(), OUT_BYTES, descriptor)
        return np.frombuffer(raw, dtype=np.float16)[:512 * 32:32].copy()

    def tile_gemm(self, cache_key, weights, activation, descriptor, in_cols):
        """Persistent cached tile matvec: the weight blob is programmed once
        for a cache key and later calls only rewrite the source vector,
        submit, and poll. Bit-identical to gemm/gemm512 for the same tile
        weights because the blob bytes come from the first call's tile."""
        program = self._tile_cache.get(cache_key)
        if program is None:
            _, _, row0, col0 = cache_key
            rows = min(512, weights.shape[0] - row0)
            cols = min(in_cols, weights.shape[1] - col0)
            padded = np.zeros((512, in_cols), dtype=np.float16)
            padded[:rows, :cols] = weights[row0:row0 + rows, col0:col0 + cols]
            weights = padded
            if in_cols == 256:
                packed = pack_weights(weights)
                src_slots, src_bytes = 256, SRC_BYTES
            else:
                # 512-in tiles need 1 MB blobs; the 256-in tile pack is
                # valid for a 512-wide matrix too (column-major halves),
                # but keep the verified 512 packing and share one blob BO
                # per key instead. here: keep 512 packing.
                packed = pack_weights_512(weights)
                src_slots, src_bytes = 512, SRC_BYTES_512
            # Geometry must match the packer: the 256-in blob sits 12 bytes
            # before the kernel bar (pack_weights shifts each channel +6
            # fp16); the 512-in blob sits exactly on it.
            blob_off = WEIGHT_OFFSET if in_cols == 256 else (TD_SIZE + 15) & ~15
            command = bytearray(blob_off + packed.nbytes)
            command[:len(descriptor)] = descriptor
            command[blob_off:] = packed.tobytes()
            cmd = self.buffer(len(command))
            out = self.buffer(OUT_BYTES)
            src = self.buffer(src_bytes)
            btsp = self.buffer(len(descriptor))
            cmd.write(bytes(command))
            btsp.write(bytes(descriptor))
            request = Submit(
                tsk_size=TD_SIZE,
                td_count=1,
                td_size=TD_SIZE,
                btsp_handle=btsp.bo.handle,
                pad=0 if self.qid is None else 0x80 | self.qid,
            )
            request.handles[0] = cmd.bo.handle
            request.handles[4] = out.bo.handle
            request.handles[5] = src.bo.handle
            program = (cmd, out, src, request, src_slots, src_bytes)
            self._tile_cache[cache_key] = program
        cmd, out, src, request, src_slots, src_bytes = program
        source = np.zeros(src_bytes // 2, dtype=np.float16)
        source[:src_slots * 32:32] = activation
        src.write(source.tobytes())
        out.map.seek(0)
        out.map.write(b"\x00\x7c" * (OUT_BYTES // 2))
        ioctl(self.fd, IOCTL_SUBMIT, request)
        deadline = time.monotonic() + WAIT_S
        while out.map[:2] == b"\x00\x7c" and time.monotonic() < deadline:
            pass
        raw = out.read(OUT_BYTES)
        if raw[:2] == b"\x00\x7c":
            raise TimeoutError("ANE output was not written before timeout")
        return np.frombuffer(raw, dtype=np.float16)[:512 * 32:32].copy()


    def blob_swap_gemm(self, cache_key, weights, activation, descriptor, in_cols):
        """Rewrite one persistent tile program's weight blob per call."""
        program = self._blob_swap_cache.get(in_cols)
        if program is None:
            _, _, row0, col0 = cache_key
            rows = min(512, weights.shape[0] - row0)
            cols = min(in_cols, weights.shape[1] - col0)
            padded = np.zeros((512, in_cols), dtype=np.float16)
            packed_size = WEIGHT_BYTES if in_cols == 256 else WEIGHT_BYTES_512
            packed = np.empty(packed_size // 2, dtype=np.float16)
            padded[:rows, :cols] = weights[row0:row0 + rows, col0:col0 + cols]
            if in_cols == 256:
                pack_weights(padded, packed)
                blob_off = WEIGHT_OFFSET
                src_slots, src_bytes = 256, SRC_BYTES
            else:
                pack_weights_512(padded, packed)
                blob_off = (TD_SIZE + 15) & ~15
                src_slots, src_bytes = 512, SRC_BYTES_512
            command = bytearray(blob_off + packed.nbytes)
            command[:len(descriptor)] = descriptor
            command[blob_off:] = packed.tobytes()
            cmd = self.buffer(len(command))
            out = self.buffer(OUT_BYTES)
            src = self.buffer(src_bytes)
            btsp = self.buffer(len(descriptor))
            cmd.write(bytes(command))
            btsp.write(bytes(descriptor))
            request = Submit(
                tsk_size=TD_SIZE,
                td_count=1,
                td_size=TD_SIZE,
                btsp_handle=btsp.bo.handle,
                pad=0 if self.qid is None else 0x80 | self.qid,
            )
            request.handles[0] = cmd.bo.handle
            request.handles[4] = out.bo.handle
            request.handles[5] = src.bo.handle
            source = np.zeros(src_bytes // 2, dtype=np.float16)
            program = (
                cmd, out, src, request, src_slots, src_bytes, blob_off, padded, packed, source
            )
            self._blob_swap_cache[in_cols] = program
        cmd, out, src, request, src_slots, src_bytes, blob_off, padded, packed, source = program
        _, _, row0, col0 = cache_key
        rows = min(512, weights.shape[0] - row0)
        cols = min(in_cols, weights.shape[1] - col0)
        padded.fill(0)
        padded[:rows, :cols] = weights[row0:row0 + rows, col0:col0 + cols]
        if in_cols == 256:
            pack_weights(padded, packed)
        else:
            pack_weights_512(padded, packed)
        cmd.map.seek(blob_off)
        cmd.map.write(memoryview(packed).cast("B"))
        source.fill(0)
        source[:src_slots * 32:32] = activation
        src.map.seek(0)
        src.map.write(memoryview(source).cast("B"))
        ioctl(self.fd, IOCTL_SUBMIT, request)
        deadline = time.monotonic() + WAIT_S
        while out.map[:2] == b"\x00\x7c" and time.monotonic() < deadline:
            pass
        raw = out.read(OUT_BYTES)
        if raw[:2] == b"\x00\x7c":
            raise TimeoutError("ANE output was not written before timeout")
        return np.frombuffer(raw, dtype=np.float16)[:512 * 32:32].copy()

    def close(self):
        for cache in (self._tile_cache, self._blob_swap_cache):
            if cache:
                for program in cache.values():
                    for buffer in program[:3]:
                        buffer.close()
                cache.clear()
        for cached in self._workspaces.values():
            for buffer in cached:
                buffer.close()
        self._workspaces = {}
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def load_descriptor(path, dimensions=None):
    """Load an operation builder without running its main function."""
    spec = importlib.util.spec_from_file_location("ane_operation", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    saved_argv = sys.argv
    saved_descriptor_only = os.environ.get("ANE_DESCRIPTOR_ONLY")
    sys.argv = [path]
    os.environ["ANE_DESCRIPTOR_ONLY"] = "1"
    try:
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink):
            spec.loader.exec_module(module)
        if dimensions is not None:
            module.__dict__.update({"C_GEMM": dimensions[0], "K_GEMM": dimensions[1]})
        return module.gemm_btsp()
    finally:
        sys.argv = saved_argv
        if saved_descriptor_only is None:
            os.environ.pop("ANE_DESCRIPTOR_ONLY", None)
        else:
            os.environ["ANE_DESCRIPTOR_ONLY"] = saved_descriptor_only
        if hasattr(module, "fd"):
            os.close(module.fd)
def self_test(qid=None):
    descriptor_path = os.path.join(os.path.dirname(__file__), "ane-network.py")
    descriptor = load_descriptor(descriptor_path)
    weights = np.full((512, 256), np.float16(0.5))
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
