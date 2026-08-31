#!/usr/bin/env python3
"""Validate Qwen activation paths on Linux ANE hardware."""

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
    values = (rng.standard_normal(6144) * 2.0).astype(np.float16)
    multiplier = rng.standard_normal(6144).astype(np.float16)
    cases = []
    started = time.perf_counter()
    with runtime.Device(qid=args.qid) as device:
        backend = token_runtime.SOFTMAX.ElementwiseBackend(device, descriptors)
        try:
            activations = token_runtime.SOFTMAX.Activations(backend)
            for name, source, right in (
                ("sigmoid_beta", values[:16], None),
                ("silu_convolution", values, None),
                ("silu_mul_ffn", values, multiplier),
                ("sigmoid_mul_attention", values[:2048], multiplier[:2048]),
            ):
                source32 = source.astype(np.float32)
                sigmoid32 = 1.0 / (1.0 + np.exp(-source32))
                if name.startswith("sigmoid"):
                    actual = (
                        activations.sigmoid(source)
                        if right is None
                        else activations.sigmoid_mul(source, right)
                    )
                    expected = sigmoid32
                else:
                    actual = (
                        activations.silu(source)
                        if right is None
                        else activations.silu_mul(source, right)
                    )
                    expected = source32 * sigmoid32
                if right is not None:
                    expected *= right.astype(np.float32)
                max_error = float(
                    np.max(np.abs(actual.astype(np.float32) - expected))
                )
                limit = 0.04
                if not np.isfinite(actual).all() or max_error >= limit:
                    raise RuntimeError(
                        f"{name} failed: max_error={max_error:.6f} limit={limit}"
                    )
                cases.append(
                    {
                        "name": name,
                        "shape": list(source.shape),
                        "max_error": max_error,
                        "limit": limit,
                    }
                )
            alpha = values[:16]
            bias = np.linspace(-2.0, 2.0, 16, dtype=np.float16)
            a_log = -np.linspace(0.1, 8.0, 16, dtype=np.float16)
            actual = activations.decay_multiplier(alpha, bias, a_log)
            expected = np.exp(
                a_log.astype(np.float32)
                * np.logaddexp(
                    np.float32(0),
                    alpha.astype(np.float32) + bias.astype(np.float32),
                )
            )
            max_error = float(
                np.max(np.abs(actual.astype(np.float32) - expected))
            )
            limit = 0.04
            if not np.isfinite(actual).all() or max_error >= limit:
                raise RuntimeError(
                    "recurrent_decay failed: "
                    f"max_error={max_error:.6f} limit={limit}"
                )
            cases.append(
                {
                    "name": "recurrent_decay",
                    "shape": list(alpha.shape),
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
                "cases": cases,
            },
            sort_keys=True,
        )
    )
    print("ANE_QWEN_ACTIVATIONS_OK")


if __name__ == "__main__":
    main()
