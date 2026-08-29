#!/usr/bin/env python3
"""Compile and run a Qwen-shaped SwiGLU block through ANEForge."""

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np


HIDDEN = 2048
INTERMEDIATE = 6144
VOCAB = 256
SEED = 20260829
EPSILON = 1e-6


def load_aneforge():
    root = Path(os.environ.get("ANEFORGE_ROOT", "~/src/ANEForge")).expanduser()
    if not (root / "aneforge").is_dir():
        raise FileNotFoundError(f"ANEForge checkout not found: {root}")
    sys.path.insert(0, str(root))
    import aneforge as af

    return af


def fp16_reference(x, weights):
    norm_weight, gate_weight, up_weight, down_weight, head_weight = weights
    x16 = np.asarray(x, dtype=np.float16)
    norm = x16.astype(np.float32)
    norm = norm / np.sqrt(np.mean(norm * norm, axis=-1, keepdims=True) + EPSILON)
    norm = (norm * norm_weight.astype(np.float32)).astype(np.float16)
    gate = (norm.astype(np.float32) @ gate_weight.astype(np.float32).T).astype(np.float16)
    up = (norm.astype(np.float32) @ up_weight.astype(np.float32).T).astype(np.float16)
    gate32 = gate.astype(np.float32)
    act = (gate32 / (1.0 + np.exp(-gate32)) * up.astype(np.float32)).astype(np.float16)
    down = (act.astype(np.float32) @ down_weight.astype(np.float32).T).astype(np.float16)
    hidden = (x16.astype(np.float32) + down.astype(np.float32)).astype(np.float16)
    return (hidden.astype(np.float32) @ head_weight.astype(np.float32).T).astype(np.float16)


def build_graph(af, weights):
    norm_weight, gate_weight, up_weight, down_weight, head_weight = weights
    inp = af.input((1, HIDDEN))
    norm = inp.rms_norm(norm_weight, EPSILON)
    gate = norm.linear(gate_weight)
    up = norm.linear(up_weight)
    hidden = inp + (gate.silu() * up).linear(down_weight)
    return hidden.linear(head_weight), inp


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, default=Path("/tmp/aneforge-qwen-graph"))
    return parser.parse_args()


def main():
    args = parse_args()
    af = load_aneforge()
    rng = np.random.default_rng(SEED)
    weights = (
        np.ones(HIDDEN, dtype=np.float32),
        (rng.standard_normal((INTERMEDIATE, HIDDEN), dtype=np.float32) * 0.02),
        (rng.standard_normal((INTERMEDIATE, HIDDEN), dtype=np.float32) * 0.02),
        (rng.standard_normal((HIDDEN, INTERMEDIATE), dtype=np.float32) * 0.02),
        (rng.standard_normal((VOCAB, HIDDEN), dtype=np.float32) * 0.02),
    )
    x = (rng.standard_normal((1, HIDDEN), dtype=np.float32) * 0.5).astype(np.float16)
    reference = fp16_reference(x, weights)
    graph, _ = build_graph(af, weights)
    compile_start = time.perf_counter()
    model = af.compile(graph, build_dir=args.build_dir)
    compile_seconds = time.perf_counter() - compile_start
    try:
        run_start = time.perf_counter()
        output = np.asarray(model(x))
        run_seconds = time.perf_counter() - run_start
        error = np.abs(output.astype(np.float32) - reference.astype(np.float32))
        argmax_expected = int(np.argmax(reference))
        argmax_observed = int(np.argmax(output))
        print(
            f"shape=input(1,{HIDDEN}) intermediate={INTERMEDIATE} vocab={VOCAB} "
            f"ops={model.n_ops} compile_seconds={compile_seconds:.3f} run_seconds={run_seconds:.3f}"
        )
        print(
            f"max_err={float(error.max()):.6f} mean_err={float(error.mean()):.6f} "
            f"argmax_expected={argmax_expected} argmax_observed={argmax_observed} "
            f"finite={bool(np.isfinite(output).all())}"
        )
        if not np.isfinite(output).all() or argmax_expected != argmax_observed or float(error.max()) > 0.1:
            raise SystemExit("QWEN_GRAPH_REFERENCE_MISMATCH")
        print("ANEFORGE_QWEN_GRAPH_OK")
    finally:
        model.release()


if __name__ == "__main__":
    main()
