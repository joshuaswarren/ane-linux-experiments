#!/usr/bin/env python3
"""Validate Qwen depthwise causal convolution on Linux ANE hardware."""

import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
CHANNELS = 6144
KERNEL_SIZE = 4
STEPS = 4
ERROR_LIMIT = 0.04


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qid", type=int, default=None)
    args = parser.parse_args()

    runtime = load_module("ane_runtime", ROOT / "ane-runtime.py")
    token_runtime = load_module(
        "qwen_token_runtime", ROOT / "tools" / "qwen-token-runtime.py"
    )
    descriptors = token_runtime.harvest_elementwise_descriptors(
        ROOT / "ane-softmax.py"
    )
    rng = np.random.default_rng(20260831)
    weight = (rng.standard_normal((CHANNELS, KERNEL_SIZE)) * 0.2).astype(
        np.float16
    )
    history = np.zeros((CHANNELS, KERNEL_SIZE - 1), dtype=np.float16)
    cases = []
    started = time.perf_counter()
    with runtime.Device(qid=args.qid) as device:
        backend = token_runtime.SOFTMAX.ElementwiseBackend(device, descriptors)
        try:
            convolution = token_runtime.SOFTMAX.CausalConvolution(
                backend, channels=CHANNELS, kernel_size=KERNEL_SIZE
            )
            for step in range(STEPS):
                value = rng.standard_normal(CHANNELS).astype(np.float16)
                window = np.concatenate((history, value[:, None]), axis=1)
                expected = np.sum(
                    window.astype(np.float32) * weight.astype(np.float32),
                    axis=1,
                )
                actual = convolution(value, weight)
                max_error = float(
                    np.max(np.abs(actual.astype(np.float32) - expected))
                )
                if not np.isfinite(actual).all() or max_error >= ERROR_LIMIT:
                    raise RuntimeError(
                        f"step {step} failed: max_error={max_error:.6f} "
                        f"limit={ERROR_LIMIT}"
                    )
                cases.append(
                    {
                        "step": step,
                        "max_error": max_error,
                        "limit": ERROR_LIMIT,
                    }
                )
                history = window[:, 1:]
        finally:
            backend.close()

    print(
        json.dumps(
            {
                "qid": args.qid,
                "shape": [CHANNELS, KERNEL_SIZE],
                "elapsed_seconds": time.perf_counter() - started,
                "cases": cases,
            },
            sort_keys=True,
        )
    )
    print("ANE_QWEN_CONVOLUTION_OK")


if __name__ == "__main__":
    main()
