#!/usr/bin/env python3
"""Keep DeltaNet recurrent state in alternating Linux ANE buffers."""

import importlib.util
import time
from pathlib import Path

import numpy as np


def load_base():
    path = Path(__file__).with_name("projection-runtime.py")
    spec = importlib.util.spec_from_file_location("projection_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_base()


class RecurrentRunner(BASE.ProjectionRunner):
    """Run one DeltaNet update while recurrent state stays in ANE buffers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self._validate_recurrent_layout()
        except BaseException:
            self.close()
            raise

    def _validate_recurrent_layout(self):
        if self.source_shape != self.output_shape:
            raise ValueError("recurrent tensor layout requires matching input and output")
        batch, heads, rows, dimension = self.source_shape
        if batch != 1 or heads < 1 or dimension < 2 or rows != dimension + 5:
            raise ValueError(
                "recurrent tensor layout must be (1, heads, dimension + 5, dimension)"
            )
        self.heads = heads
        self.dimension = dimension
        self.state_rows = slice(4, 4 + dimension)
        self.output_row = 4 + dimension

    def initialize(self, state):
        state = self._require(state, (self.heads, self.dimension, self.dimension), "state")
        source = BASE.tensor_view(self.source, self.stage["source_nchw"])
        source[...] = np.float16(0)
        source[0, :, self.state_rows, :] = state

    def step(self, q, k, v, beta, decay):
        vector_shape = (self.heads, self.dimension)
        gate_shape = (self.heads,)
        q = self._require(q, vector_shape, "q")
        k = self._require(k, vector_shape, "k")
        v = self._require(v, vector_shape, "v")
        beta = self._require(beta, gate_shape, "beta")
        decay = self._require(decay, gate_shape, "decay")
        source = BASE.tensor_view(self.source, self.stage["source_nchw"])
        source[0, :, 0, :] = q
        source[0, :, 1, :] = k
        source[0, :, 2, :] = v
        source[0, :, 3, 0] = beta
        source[0, :, 3, 1] = decay
        output = BASE.tensor_view(self.output, self.stage["output_nchw"])
        output[0, :, self.output_row, :] = np.float16(np.inf)
        self.submit(self.device.fd, BASE.RUNTIME.IOCTL_SUBMIT, self.request)
        deadline = time.monotonic() + self.timeout
        while np.isinf(output[0, :, self.output_row, :]).any():
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"ANE recurrent update did not complete within {self.timeout} seconds"
                )
            time.sleep(0.001)
        result = output[0, :, self.output_row, :].copy()
        if not np.isfinite(result).all():
            raise RuntimeError("ANE recurrent update returned a non-finite output")
        self.source, self.output = self.output, self.source
        self.request.handles[4] = self.output.bo.handle
        self.request.handles[5] = self.source.bo.handle
        return result

    def snapshot_state(self):
        source = BASE.tensor_view(self.source, self.stage["source_nchw"])
        return source[0, :, self.state_rows, :].copy()

    @staticmethod
    def _require(value, shape, name):
        value = np.asarray(value)
        if value.dtype != np.float16 or value.shape != shape:
            raise ValueError(
                f"{name} shape and dtype must be {shape} float16, "
                f"got {value.shape} {value.dtype}"
            )
        return value


if __name__ == "__main__":
    raise SystemExit("import RecurrentRunner from this file")
