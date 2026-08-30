#!/usr/bin/env python3
"""Run one converted Monterey Espresso projection through the Linux ANE KMD."""

import importlib.util
import mmap
import struct
import time
from contextlib import ExitStack
from fcntl import ioctl
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROBE = load_module(
    "production_anec_probe", Path(__file__).with_name("production-anec-probe.py")
)
RUNTIME = load_module("ane_runtime", ROOT / "ane-runtime.py")


def tensor_view(buffer, nchw):
    n, channels, height, width, plane_stride, row_stride = map(int, nchw)
    return np.ndarray(
        (n, channels, height, width),
        dtype=np.float16,
        buffer=buffer.map,
        strides=(channels * plane_stride, plane_stride, row_stride, 2),
    )


class ProjectionRunner:
    """Own reusable buffers for one converted fp16 projection."""

    def __init__(self, path, qid=None, timeout=10.0, device=None, submit=ioctl):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.path = Path(path)
        self.timeout = timeout
        self.submit = submit
        self.stack = ExitStack()
        try:
            self.device = device or self.stack.enter_context(RUNTIME.Device(qid=qid))
            stream = self.stack.enter_context(self.path.open("rb"))
            self.artifact = self.stack.enter_context(
                mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
            )
            self.stage = PROBE.stage_geometry(PROBE.load_anec_header(self.path))
            self._validate_stage()
            if len(self.artifact) < PROBE.HEADER_SIZE + self.stage["content_size"]:
                raise ValueError(
                    f"truncated artifact: {self.path.name} is {len(self.artifact)} bytes,"
                    f" needs {PROBE.HEADER_SIZE + self.stage['content_size']}"
                )
            self.source_shape = tuple(self.stage["source_nchw"][:4])
            self.output_shape = tuple(self.stage["output_nchw"][:4])
            self.command = self.stack.enter_context(
                self.device.buffer(self.stage["content_size"])
            )
            PROBE.copy_content(
                self.artifact,
                PROBE.HEADER_SIZE,
                self.stage["content_size"],
                self.command.map,
            )
            self.workspace = (
                self.stack.enter_context(
                    self.device.buffer(self.stage["workspace_size"])
                )
                if self.stage["workspace_size"]
                else None
            )
            if self.workspace is not None:
                self.workspace.write(b"\0" * self.stage["workspace_size"])
            self.source = self.stack.enter_context(
                self.device.buffer(self.stage["source_size"])
            )
            self.source.write(b"\0" * self.stage["source_size"])
            self.output = self.stack.enter_context(
                self.device.buffer(self.stage["output_size"])
            )
            bases = PROBE.task_bases(
                self.artifact, PROBE.HEADER_SIZE, self.stage["task_stream_size"]
            )
            if len(bases) != self.stage["td_count"]:
                raise ValueError(
                    f"header has {self.stage['td_count']} tasks, found {len(bases)}"
                )
            bootstrap = PROBE.build_original_prefix(
                self.artifact,
                PROBE.HEADER_SIZE,
                self.stage["task_stream_size"],
                bases,
                self.stage["td_count"],
            )
            self.btsp = self.stack.enter_context(
                self.device.buffer(self.stage["task_stream_size"])
            )
            self.btsp.write(bootstrap)
            first_word = struct.unpack_from("<I", self.btsp.map)[0]
            self.btsp.map.seek(0)
            self.btsp.map.write(
                struct.pack("<I", (first_word & 0x0F00FFFF) | (0x40 << 16))
            )
            self.request = RUNTIME.Submit(
                tsk_size=self.stage["task_stream_size"],
                td_count=self.stage["td_count"],
                td_size=self.stage["td_size"],
                btsp_handle=self.btsp.bo.handle,
                pad=PROBE.submission_pad(qid),
            )
            self.request.handles[0] = self.command.bo.handle
            if self.workspace is not None:
                self.request.handles[PROBE.WORKSPACE_BDX] = self.workspace.bo.handle
            self.request.handles[4] = self.source.bo.handle
            self.request.handles[5] = self.output.bo.handle
            self.sentinel = np.full(
                self.stage["output_size"] // 2, np.inf, dtype=np.float16
            ).tobytes()
        except BaseException:
            self.stack.close()
            raise

    def _validate_stage(self):
        if self.stage["src_count"] != 1 or self.stage["dst_count"] != 1:
            raise ValueError("projection must have one input and one output")
        if self.stage["td_count"] < 1 or self.stage["td_size"] < 1:
            raise ValueError("invalid task geometry")
        if self.stage["task_stream_size"] < self.stage["td_size"]:
            raise ValueError("invalid task geometry")

    def run(self, source):
        source = np.asarray(source)
        if source.dtype != np.float16 or source.shape != self.source_shape:
            raise ValueError(
                f"input shape and dtype must be {self.source_shape} float16, "
                f"got {source.shape} {source.dtype}"
            )
        tensor_view(self.source, self.stage["source_nchw"])[...] = source
        self.output.write(self.sentinel)
        self.submit(self.device.fd, RUNTIME.IOCTL_SUBMIT, self.request)
        deadline = time.monotonic() + self.timeout
        while True:
            values = tensor_view(self.output, self.stage["output_nchw"])
            completed = bool(np.all(values != np.float16(np.inf)))
            del values
            if completed:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"ANE projection did not complete within {self.timeout} seconds"
                )
            time.sleep(0.001)
        result = tensor_view(self.output, self.stage["output_nchw"]).copy()
        if not np.isfinite(result).all():
            raise RuntimeError("ANE projection returned a non-finite output")
        return result.reshape(self.output_shape)

    def close(self):
        self.stack.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


if __name__ == "__main__":
    raise SystemExit("import ProjectionRunner from this file")
