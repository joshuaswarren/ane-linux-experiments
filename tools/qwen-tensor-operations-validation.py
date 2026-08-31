#!/usr/bin/env python3
"""Validate Qwen RoPE and residual arithmetic on Linux ANE hardware."""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import runpy
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
ERROR_LIMIT = 0.04


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def harvest_elementwise_descriptors(path):
    with contextlib.redirect_stdout(io.StringIO()):
        namespace = runpy.run_path(path, run_name="qwen_elementwise_harvest")
    os.close(namespace["fd"])
    return namespace["_descriptors"]


def rope_reference(value, position):
    expected = value.astype(np.float32).copy()
    inverse = 10_000_000.0 ** (-np.arange(0, 64, 2, dtype=np.float32) / 64)
    frequencies = position * inverse
    
    cosine = np.cos(frequencies)
    sine = np.sin(frequencies)
    left = expected[:, :32].copy()
    right = expected[:, 32:64].copy()
    expected[:, :32] = left * cosine - right * sine
    expected[:, 32:64] = right * cosine + left * sine
    return expected


def case(name, actual, expected):
    max_error = float(np.max(np.abs(actual.astype(np.float32) - expected)))
    if not np.isfinite(actual).all() or max_error >= ERROR_LIMIT:
        raise RuntimeError(
            f"{name} failed: max_error={max_error:.6f} limit={ERROR_LIMIT}"
        )
    return {
        "name": name,
        "shape": list(actual.shape),
        "max_error": max_error,
        "limit": ERROR_LIMIT,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qid", type=int, default=None)
    args = parser.parse_args()

    runtime = load_module("ane_runtime", ROOT / "ane-runtime.py")
    softmax = load_module("softmax_runtime", ROOT / "tools" / "softmax-runtime.py")
    descriptors = harvest_elementwise_descriptors(ROOT / "ane-softmax.py")
    rng = np.random.default_rng(20260901)
    started = time.perf_counter()
    cases = []
    with runtime.Device(qid=args.qid) as device:
        backend = softmax.ElementwiseBackend(device, descriptors)
        try:
            operations = softmax.TensorOperations(backend)
            left = rng.standard_normal(2048).astype(np.float16)
            right = rng.standard_normal(2048).astype(np.float16)
            cases.append(
                case(
                    "residual_add",
                    operations.add(left, right),
                    left.astype(np.float32) + right.astype(np.float32),
                )
            )
            for name, heads in (("query_rope", 8), ("key_rope", 2)):
                value = rng.standard_normal((heads, 256)).astype(np.float16)
                cases.append(
                    case(name, operations.rope(value, 37), rope_reference(value, 37))
                )
        finally:
            backend.close()

    print(
        json.dumps(
            {
                "qid": args.qid,
                "elapsed_seconds": time.perf_counter() - started,
                "cases": cases,
            },
            sort_keys=True,
        )
    )
    print("ANE_QWEN_TENSOR_OPERATIONS_OK")


if __name__ == "__main__":
    main()
