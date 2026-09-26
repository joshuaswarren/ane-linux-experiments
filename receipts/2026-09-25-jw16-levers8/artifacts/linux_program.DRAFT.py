#!/usr/bin/env python3
"""LinuxProgram: drop-in ANEForge Program.eval replacement for the Linux
KMD path (T6001, omarchy-ane). Reuses production-anec-probe's proven
submit flow. No CPU tensor fallback: every eval is an ANE_SUBMIT."""
import importlib.util
import mmap
import struct
from contextlib import ExitStack
from pathlib import Path

import numpy as np

TILE_SIZE = 0x4000
WORKSPACE_BDX = 3


def load_runtime(runtime_path):
    spec = importlib.util.spec_from_file_location("ane_runtime", runtime_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LinuxProgram:
    """One converted ANEC artifact, submitted per eval() like ANEForge's
    e5rt Program: write input surfaces (dict port->fp16 array), ioctl,
    read output surfaces (dict port->fp16 array)."""

    def __init__(self, anec_path, runtime, fd, input_banks, output_banks):
        self.path = Path(anec_path)
        self.runtime = runtime
        self.fd = fd
        self.input_banks = input_banks    # {port: bdx}
        self.output_banks = output_banks  # {port: bdx}
        with self.path.open("rb") as fh, mmap.mmap(
            fh.fileno(), 0, access=mmap.ACCESS_READ
        ) as mm:
            self.stage = runtime_stage(mm)
            self.content = bytes(
                mm[probe_header_size(): probe_header_size() + self.stage["content_size"]]
            )
        self._stack = ExitStack()
        self.fd_device = None
        self.command = None
        self.btsp = None
        self.workspace = None
        self.src_bufs = {}   # bdx -> buffer
        self.dst_bufs = {}   # bdx -> buffer

    def open(self):
        self.fd_device = self._stack.enter_context(
            runtime_device(self.runtime)
        )
        self.command = self._stack.enter_context(
            device_buffer(self.fd_device, self.stage["content_size"])
        )
        self.command.write(self.content)
        if self.stage["workspace_size"]:
            self.workspace = self._stack.enter_context(
                device_buffer(self.fd_device, self.stage["workspace_size"])
            )
            self.workspace.write(b"\0" * self.stage["workspace_size"])
        btsp_size = max(self.stage["td_count"] * 0x300, 0x1000)
        self.btsp = self._stack.enter_context(
            device_buffer(self.fd_device, btsp_size)
        )
        for spec in self.stage["input_surfaces"]:
            self.src_bufs[spec["bdx"]] = self._stack.enter_context(
                device_buffer(self.fd_device, spec["bytes"])
            )
        for spec in self.stage["output_surfaces"]:
            self.dst_bufs[spec["bdx"]] = self._stack.enter_context(
                device_buffer(self.fd_device, spec["bytes"])
            )
        return self

    def close(self):
        self._stack.close()

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()

    def eval(self, inputs):
        for port, array in inputs.items():
            bdx = self.input_banks[port]
            raw = np.ascontiguousarray(array, dtype=np.float16).tobytes()
            buf = self.src_bufs[bdx]
            if len(raw) > len(buf.map):
                raise ValueError(
                    f"input {port}: {len(raw)} B exceeds surface {len(buf.map)} B"
                )
            buf.map.seek(0)
            buf.map.write(raw.ljust(len(buf.map), b"\0"))
        for spec in self.stage["output_surfaces"]:
            buf = self.dst_bufs[spec["bdx"]]
            buf.map.seek(0)
            buf.map.write(b"\xff" * len(buf.map))
        request = self.runtime.Submit(
            tsk_size=self.stage["task_stream_size"],
            td_count=self.stage["td_count"],
            td_size=self.stage["td_size"],
            btsp_handle=self.btsp.bo.handle,
        )
        import fcntl

        request.handles[0] = self.command.bo.handle
        if self.workspace is not None:
            request.handles[WORKSPACE_BDX] = self.workspace.bo.handle
        for port, bdx in self.input_banks.items():
            request.handles[bdx] = self.src_bufs[bdx].bo.handle
        for port, bdx in self.output_banks.items():
            request.handles[bdx] = self.dst_bufs[bdx].bo.handle
        import io

        fcntl.ioctl(self.fd_device, self.runtime.IOCTL_SUBMIT, request)
        outputs = {}
        for port, bdx in self.output_banks.items():
            buf = self.dst_bufs[bdx]
            n = spec_bytes_for(self.stage, bdx, output=True)
            values = np.frombuffer(buf.read(n), dtype=np.float16).copy()
            outputs[port] = values
        return outputs


def spec_bytes_for(stage, bdx, output=True):
    surfaces = stage["output_surfaces"] if output else stage["input_surfaces"]
    for spec in surfaces:
        if spec["bdx"] == bdx:
            return spec["bytes"]
    raise KeyError(bdx)


def runtime_device(runtime):
    return runtime.Device()


def device_buffer(fd_device, size):
    return fd_device.buffer(size)


def runtime_stage(mm):
    """Minimal stage geometry from an ANEC header mmap (probe-compatible)."""
    import production_anec_probe as probe  # lazy; same dir

    return probe.stage_geometry(probe.load_anec_header_bytes(mm))


def probe_header_size():
    return 0x1000


WORKSPACE_BDX = 3
