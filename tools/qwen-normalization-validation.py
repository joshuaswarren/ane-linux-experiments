#!/usr/bin/env python3
"""Validate Qwen RMS and L2 normalization on Linux ANE hardware."""

import argparse
import importlib.util
import json
import time
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
    rng = np.random.default_rng(20260830)
    cases = [
        ("rms_hidden", (2048,), "rms", 1.0),
        ("rms_attention", (8, 256), "rms", 1.0),
        ("rms_recurrent", (16, 128), "rms", 1.0),
        ("l2_recurrent_query", (16, 128), "l2", 1.0 / np.sqrt(128.0)),
    ]
    results = []
    started = time.perf_counter()
    with runtime.Device(qid=args.qid) as device:
        backend = token_runtime.SOFTMAX.ElementwiseBackend(device, descriptors)
        try:
            normalization = token_runtime.SOFTMAX.Normalization(backend)
            for name, shape, mode, scale in cases:
                values = (rng.standard_normal(shape) * 0.5).astype(np.float16)
                values32 = values.astype(np.float32)
                if mode == "rms":
                    weight = rng.uniform(0.75, 1.25, shape[-1]).astype(np.float16)
                    actual = normalization.rms_norm(values, weight)
                    expected = values32 / np.sqrt(
                        np.mean(values32 * values32, axis=-1, keepdims=True)
                        + 1e-6
                    )
                    expected *= weight.astype(np.float32)
                    limit = 0.04
                else:
                    actual = normalization.l2_norm(values, scale)
                    expected = scale * values32 / np.sqrt(
                        np.sum(values32 * values32, axis=-1, keepdims=True)
                        + 1e-6
                    )
                    limit = 0.004
                max_error = float(
                    np.max(np.abs(actual.astype(np.float32) - expected))
                )
                if not np.isfinite(actual).all() or max_error >= limit:
                    raise RuntimeError(
                        f"{name} failed: max_error={max_error:.6f} limit={limit}"
                    )
                results.append(
                    {
                        "name": name,
                        "shape": list(shape),
                        "max_error": max_error,
                        "limit": limit,
                    }
                )
        finally:
            backend.close()

    print(
        json.dumps(
            {
                "qid": args.qid,
                "elapsed_seconds": time.perf_counter() - started,
                "cases": results,
            },
            sort_keys=True,
        )
    )
    print("ANE_QWEN_NORMALIZATION_OK")


if __name__ == "__main__":
    main()
