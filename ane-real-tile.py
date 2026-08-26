#!/usr/bin/env python3
"""Run one dequantized real-model weight tile through the ANE runtime.

This is not a language-model forward pass. It is the first real-weight
boundary: load one Q4_K tensor from a real Llama GGUF, dequantize it, select
its first 512x256 tile, run that tile through the ANE gemm, and compare with
the same fp16 tile multiplied by a known activation vector in numpy.

  python3 ane-real-tile.py -m model.gguf -p /path/to/gguf-py
"""
import argparse
import importlib.util
import os

import numpy as np



def load(name):
    path = os.path.join(os.path.dirname(__file__), name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", required=True)
    parser.add_argument("-p", "--gguf-py")
    parser.add_argument("-t", "--tensor", default="blk.0.attn_q.weight")
    parser.add_argument("--qid", type=int, default=None)
    args = parser.parse_args()

    weights_module = load("ane-weights.py")
    runtime = load("ane-runtime.py")
    weights = weights_module.GGUFWeights(args.model, args.gguf_py).tensor(args.tensor)
    tile = weights[:512, :256]
    descriptor = runtime.load_descriptor(os.path.join(os.path.dirname(__file__), "ane-network.py"))
    activation = np.ones(256, dtype=np.float16)
    reference = tile.astype(np.float32) @ activation.astype(np.float32)

    with runtime.Device(qid=args.qid) as device:
        got = device.gemm(tile, activation, descriptor).astype(np.float32)
    error = np.abs(got - reference)
    print(f"tensor={args.tensor} source_shape={weights.shape} tile={tile.shape}")
    print(f"max_abs_err={error.max():.6f} mean_abs_err={error.mean():.6f} "
          f"finite={np.isfinite(got).all()}")
    print("ANE_REAL_WEIGHT_TILE_OK")


if __name__ == "__main__":
    main()
