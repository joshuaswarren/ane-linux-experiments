#!/usr/bin/env python3
"""Bitwise check: mx.fast.rms_norm_gated / rms_norm_scaled vs the composed mlx-lm chains at prefill row counts.
Prints one JSON line with mismatch counts (0 == bit-identical)."""
import json

import mlx.core as mx
import numpy as np
from mlx import nn


@mx.compile
def precise_swiglu(gate, x):
    return (nn.silu(gate.astype(mx.float32)) * x.astype(mx.float32)).astype(mx.bfloat16)


def bits(a):
    mx.eval(a)
    return np.array(a.view(mx.uint16))


res = {}
mx.random.seed(3)
for rows in (16, 256, 2048 * 16 // 16, 2048 * 16 // 4, 2048 * 16):
    for scale_mag in (1.0, 6.0):
        h = (mx.random.normal((rows, 128)) * scale_mag).astype(mx.bfloat16)
        g = (mx.random.normal((rows, 128)) * scale_mag).astype(mx.bfloat16)
        w = mx.random.normal((128,)).astype(mx.bfloat16)
        composed = precise_swiglu(g, mx.fast.rms_norm(h, w, 1e-6))
        fused = mx.fast.rms_norm_gated(h, g, w, 1e-6)
        res[f"gated.{rows}.{scale_mag}"] = int((bits(composed) != bits(fused)).sum())
        inv = 128 ** -0.5
        for name, s in (("q", inv * inv), ("k", inv)):
            comp = s * mx.fast.rms_norm(h, None, 1e-6)
            fus = mx.fast.rms_norm_scaled(h, None, s, 1e-6)
            res[f"scaled_{name}.{rows}.{scale_mag}"] = int((bits(comp) != bits(fus)).sum())
print(json.dumps(res))
print("TOTAL_MISMATCH", sum(res.values()))
