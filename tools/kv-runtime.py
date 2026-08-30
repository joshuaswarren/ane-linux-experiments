#!/usr/bin/env python3
"""Keep Qwen grouped-query attention caches in alternating Linux ANE buffers."""

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


class KvStateRunner(BASE.ProjectionRunner):
    """Update a fixed-window K/V cache without a host state round trip."""

    def __init__(self, *args, kv_heads=2, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self._validate_kv_layout(kv_heads)
        except BaseException:
            self.close()
            raise

    def _validate_kv_layout(self, kv_heads):
        if self.source_shape != self.output_shape:
            raise ValueError("KV tensor layout requires matching input and output")
        batch, heads, rows, dimension = self.source_shape
        context, remainder = divmod(rows - 3, 2)
        if batch != 1 or heads < 1 or context < 1 or dimension < 1 or remainder:
            raise ValueError(
                "KV tensor layout must be (1, heads, 2 * context + 3, dimension)"
            )
        if kv_heads < 1 or heads % kv_heads:
            raise ValueError("query heads must be divisible by KV heads")
        if self.source.bo.handle == self.output.bo.handle:
            raise ValueError("KV state requires distinct input and output buffers")
        self.heads = heads
        self.kv_heads = kv_heads
        self.group_size = heads // kv_heads
        self.context = context
        self.dimension = dimension
        self.key_rows = slice(2, 2 + context)
        self.value_rows = slice(2 + context, 2 + 2 * context)
        self.completion_row = rows - 1

    def initialize(self):
        source = BASE.tensor_view(self.source, self.stage["source_nchw"])
        source[...] = np.float16(0)

    def step(self, key, value):
        key = self._require(key, (self.kv_heads, self.dimension), "key")
        value = self._require(value, (self.kv_heads, self.dimension), "value")
        source = BASE.tensor_view(self.source, self.stage["source_nchw"])
        source[0, :, 0, :] = np.repeat(key, self.group_size, axis=0)
        source[0, :, 1, :] = np.repeat(value, self.group_size, axis=0)

        output = BASE.tensor_view(self.output, self.stage["output_nchw"])
        output[0, :, self.completion_row, :] = np.float16(np.inf)
        self.submit(self.device.fd, BASE.RUNTIME.IOCTL_SUBMIT, self.request)
        deadline = time.monotonic() + self.timeout
        while np.isinf(output[0, :, self.completion_row, :]).any():
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"ANE KV state update did not complete within {self.timeout} seconds"
                )
            time.sleep(0.001)
        if not np.isfinite(output[0, :, self.completion_row, :]).all():
            raise RuntimeError("ANE KV state update returned a non-finite completion row")
        self.source, self.output = self.output, self.source
        self.request.handles[4] = self.output.bo.handle
        self.request.handles[5] = self.source.bo.handle

    def snapshot_cache(self):
        source = BASE.tensor_view(self.source, self.stage["source_nchw"])
        return (
            source[0, :, self.key_rows, :].copy(),
            source[0, :, self.value_rows, :].copy(),
        )

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
    raise SystemExit("import KvStateRunner from this file")
