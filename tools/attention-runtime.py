#!/usr/bin/env python3
"""Keep full-attention keys and values in mutable Linux ANE GEMM programs."""

import importlib.util
import time
from fcntl import ioctl
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent


def load_runtime():
    path = ROOT / "ane-runtime.py"
    spec = importlib.util.spec_from_file_location("ane_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNTIME = load_runtime()
COMPLETION_ROW = 511


class MutableGemm:
    """Own one 512x256 GEMM whose packed weights can change in place."""

    def __init__(
        self,
        device,
        descriptor,
        output_rows,
        timeout=10.0,
        submit=ioctl,
    ):
        if not 1 <= output_rows <= COMPLETION_ROW:
            raise ValueError(f"output_rows must be in 1..{COMPLETION_ROW}")
        if len(descriptor) < RUNTIME.TD_SIZE:
            raise ValueError("descriptor is shorter than td_size")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.device = device
        self.output_rows = output_rows
        self.timeout = timeout
        self.submit = submit
        self.closed = False
        command_size = RUNTIME.WEIGHT_OFFSET + RUNTIME.WEIGHT_BYTES
        self.command = device.buffer(command_size)
        self.output = device.buffer(RUNTIME.OUT_BYTES)
        self.source = device.buffer(RUNTIME.SRC_BYTES)
        self.btsp = device.buffer(len(descriptor))
        command = bytearray(command_size)
        command[: len(descriptor)] = descriptor
        self.command.write(command)
        self.btsp.write(descriptor)
        self.weights = np.ndarray(
            (16, RUNTIME.WEIGHT_BYTES // 2 // 16),
            dtype=np.float16,
            buffer=self.command.map,
            offset=RUNTIME.WEIGHT_OFFSET,
        )
        self.request = RUNTIME.Submit(
            tsk_size=RUNTIME.TD_SIZE,
            td_count=1,
            td_size=RUNTIME.TD_SIZE,
            btsp_handle=self.btsp.bo.handle,
            pad=0 if device.qid is None else 0x80 | device.qid,
        )
        self.request.handles[0] = self.command.bo.handle
        self.request.handles[4] = self.output.bo.handle
        self.request.handles[5] = self.source.bo.handle
        self._source_values = np.zeros(RUNTIME.SRC_BYTES // 2, dtype=np.float16)

    def _ensure_open(self):
        if self.closed:
            raise RuntimeError("mutable GEMM is closed")

    def write_row(self, row, values):
        self._ensure_open()
        if not 0 <= row < self.output_rows:
            raise ValueError(f"row must be in 0..{self.output_rows - 1}")
        values = self._vector(values, 256, "row values")
        block, lane = divmod(row, 32)
        self.weights[block, 6 + lane : 6 + 256 * 32 + lane : 32] = values

    def write_column(self, column, values):
        self._ensure_open()
        if not 0 <= column < 256:
            raise ValueError("column must be in 0..255")
        values = self._vector(values, self.output_rows, "column values")
        rows = np.arange(self.output_rows)
        self.weights[rows // 32, 6 + column * 32 + rows % 32] = values

    def run(self, activation):
        self._ensure_open()
        activation = self._vector(activation, 256, "activation")
        self._source_values.fill(0)
        self._source_values[: 256 * 32 : 32] = activation
        self.source.write(memoryview(self._source_values).cast("B"))
        completion_offset = COMPLETION_ROW * 32 * 2
        sentinel = b"\x00\x7c"
        self.output.map[completion_offset : completion_offset + 2] = sentinel
        self.submit(self.device.fd, RUNTIME.IOCTL_SUBMIT, self.request)
        deadline = time.monotonic() + self.timeout
        while (
            self.output.map[completion_offset : completion_offset + 2] == sentinel
            and time.monotonic() < deadline
        ):
            time.sleep(0.001)
        if self.output.map[completion_offset : completion_offset + 2] == sentinel:
            raise TimeoutError("ANE mutable GEMM did not complete before timeout")
        values = np.frombuffer(
            self.output.map,
            dtype=np.float16,
            count=RUNTIME.OUT_BYTES // 2,
        )
        result = values[: self.output_rows * 32 : 32].copy()
        if not np.isfinite(result).all():
            raise RuntimeError("ANE mutable GEMM returned a non-finite output")
        return result

    @staticmethod
    def _vector(value, size, name):
        value = np.asarray(value)
        if value.dtype != np.float16 or value.shape != (size,):
            raise ValueError(
                f"{name} shape and dtype must be ({size},) float16, "
                f"got {value.shape} {value.dtype}"
            )
        return value

    def close(self):
        if self.closed:
            return
        del self.weights
        for buffer in (self.command, self.output, self.source, self.btsp):
            buffer.close()
        self.closed = True


class AttentionGemmState:
    """Update matching key rows and value columns without copying old state."""

    def __init__(self, score_program, value_program, context=128, dimension=256):
        if context < 1 or dimension != 256:
            raise ValueError("context must be positive and dimension must be 256")
        if score_program.output_rows < context:
            raise ValueError("score program output rows must cover the context")
        if value_program.output_rows != dimension:
            raise ValueError("value program output rows must equal the dimension")
        self.score_program = score_program
        self.value_program = value_program
        self.context = context
        self.dimension = dimension
        self.cursor = 0
        self.length = 0

    def append(self, key, value):
        key = MutableGemm._vector(key, self.dimension, "key")
        value = MutableGemm._vector(value, self.dimension, "value")
        self.score_program.write_row(self.cursor, key)
        self.value_program.write_column(self.cursor, value)
        self.cursor = (self.cursor + 1) % self.context
        self.length = min(self.length + 1, self.context)

    def scores(self, query):
        scores = self.score_program.run(query)[: self.context]
        if self.length < self.context:
            scores[self.length :] = np.finfo(np.float16).min
        return scores

    def attend(self, probabilities):
        probabilities = MutableGemm._vector(probabilities, self.context, "probabilities")
        activation = np.zeros(256, dtype=np.float16)
        activation[: self.context] = probabilities
        return self.value_program.run(activation)[: self.dimension]
