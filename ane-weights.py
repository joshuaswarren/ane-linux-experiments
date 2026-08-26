#!/usr/bin/env python3
"""Load real GGUF tensors and emit fp16 tiles for the ANE runtime.

The ANE gemm accepts 512 output rows by 256 input columns. GGUF models store
quantized tensors such as Q4_K and Q6_K, so this loader uses llama.cpp's
bundled ``gguf-py`` reader and dequantizer, then yields canonical fp16 tiles.
The loader never invents weights and never sends quantized bytes to an fp16
ANE descriptor.

Set ``GGUF_PY`` to the llama.cpp ``gguf-py`` directory, or pass ``--gguf-py``.
The cached llama.cpp checkout is the default only when it exists under ``~/src``.

  python3 ane-weights.py -m model.gguf -t blk.0.attn_q.weight
  python3 ane-weights.py -m model.gguf -t blk.0.attn_q.weight --tile 0 0
"""
import argparse
import importlib
import os
import sys

import numpy as np


class GGUFWeights:
    """Read and dequantize named GGUF tensors on demand."""

    def __init__(self, model, gguf_py=None):
        gguf_py = gguf_py or os.environ.get("GGUF_PY")
        if gguf_py is None:
            default = os.path.expanduser("~/src/llama.cpp/gguf-py")
            if os.path.isdir(default):
                gguf_py = default
        if gguf_py is None or not os.path.isdir(gguf_py):
            raise FileNotFoundError("set GGUF_PY to llama.cpp/gguf-py")
        sys.path.insert(0, gguf_py)
        self.reader = importlib.import_module("gguf").GGUFReader(model)
        self.dequantize = importlib.import_module("gguf.quants").dequantize

    def _tensor_record(self, name):
        try:
            return next(t for t in self.reader.tensors if t.name == name)
        except StopIteration as exc:
            raise KeyError(name) from exc

    def names(self):
        return tuple(t.name for t in self.reader.tensors)

    def tensor32(self, name):
        """Return one named tensor in dequantized float32 form."""
        tensor = self._tensor_record(name)
        return self.dequantize(tensor.data, tensor.tensor_type).astype(np.float32, copy=False)

    def tensor(self, name):
        """Return one named tensor in dequantized output-by-input fp16 layout."""
        tensor = self._tensor_record(name)
        value = self.dequantize(tensor.data, tensor.tensor_type)
        return value.astype(np.float16, copy=False)

    def row32(self, name, index):
        """Dequantize one row as float32 without expanding the tensor."""
        tensor = self._tensor_record(name)
        if tensor.data.ndim != 2 or not 0 <= index < tensor.data.shape[0]:
            raise ValueError(f"{name} is not row-addressable at {index}")
        value = self.dequantize(tensor.data[index:index + 1], tensor.tensor_type)
        return value.reshape(-1).astype(np.float32, copy=False)

    def row(self, name, index):
        """Dequantize one row as fp16 without expanding the tensor."""
        tensor = self._tensor_record(name)
        if tensor.data.ndim != 2 or not 0 <= index < tensor.data.shape[0]:
            raise ValueError(f"{name} is not row-addressable at {index}")
        value = self.dequantize(tensor.data[index:index + 1], tensor.tensor_type)
        return value.reshape(-1).astype(np.float16, copy=False)

    def tiles(self, name, out_rows=512, in_cols=256):
        """Yield ``(row0, col0, tile)`` zero-padded fp16 tiles."""
        matrix = self.tensor(name)
        if matrix.ndim != 2:
            raise ValueError(f"{name} is {matrix.ndim}D, expected a matrix")
        rows, cols = matrix.shape
        for row0 in range(0, rows, out_rows):
            for col0 in range(0, cols, in_cols):
                tile = np.zeros((out_rows, in_cols), dtype=np.float16)
                tile[:min(out_rows, rows - row0), :min(in_cols, cols - col0)] = \
                    matrix[row0:row0 + out_rows, col0:col0 + in_cols]
                yield row0, col0, tile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", required=True)
    parser.add_argument("-t", "--tensor", required=True)
    parser.add_argument("--gguf-py")
    parser.add_argument("--tile", nargs=2, type=int, metavar=("ROW", "COL"))
    args = parser.parse_args()

    weights = GGUFWeights(args.model, args.gguf_py)
    matrix = weights.tensor(args.tensor)
    print(f"tensor={args.tensor} dtype={matrix.dtype} shape={matrix.shape} "
          f"min={matrix.min():.6g} max={matrix.max():.6g}")
    if args.tile:
        wanted = tuple(args.tile)
        for row0, col0, tile in weights.tiles(args.tensor):
            if (row0, col0) == wanted:
                print(f"tile=({row0},{col0}) shape={tile.shape} "
                      f"finite={np.isfinite(tile).all()} nonzero={np.count_nonzero(tile)}")
                return
        raise SystemExit(f"tile {wanted} not found")


if __name__ == "__main__":
    main()
