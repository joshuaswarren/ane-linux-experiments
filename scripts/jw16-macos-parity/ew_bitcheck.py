#!/usr/bin/env python3
"""SHA-256 of raw output bits of elementwise ops 0-10 (add, mul, div, max, exp, sigmoid, square, sqrt,
rsqrt, sub, neg) across f32/f16/bf16, contiguous/scalar/row-broadcast operands, with special values.
Run in two venvs and diff the JSON: identical hashes == bitwise-identical kernels."""
import hashlib
import json

import mlx.core as mx
import numpy as np

mx.random.seed(1)
rows = {}
special = np.array([0.0, -0.0, 1.0, -1.0, np.inf, -np.inf, np.nan, 1e-30, 1e30, 65000.0, -65000.0, 3.14159, 0.5, 1e-8], np.float32)


def base(n, dt):
    a = mx.random.normal((n,)) * 3
    a = mx.concatenate([a[: n - len(special)], mx.array(special)])
    return a.astype(dt)


def bits(x):
    mx.eval(x)
    if x.dtype == mx.float32:
        v = np.array(x.view(mx.uint32))
    else:
        v = np.array(x.view(mx.uint16))
    return hashlib.sha256(v.tobytes()).hexdigest()[:16]


ops = {
    "add": lambda a, b: a + b, "mul": lambda a, b: a * b, "div": lambda a, b: a / b,
    "max": mx.maximum, "sub": lambda a, b: a - b,
    "exp": lambda a, b: mx.exp(a), "sigmoid": lambda a, b: mx.sigmoid(a), "square": lambda a, b: mx.square(a),
    "sqrt": lambda a, b: mx.sqrt(mx.abs(a)), "rsqrt": lambda a, b: mx.rsqrt(mx.abs(a) + 1e-3), "neg": lambda a, b: -a,
}
for dt in (mx.float32, mx.float16, mx.bfloat16):
    for n in (4096, 65536 + 3, 1 << 20):
        a = base(n, dt)
        b = base(n, dt)[::-1]
        b = mx.array(np.array(b.astype(mx.float32)), dtype=mx.float32).astype(dt)
        sc = mx.array(0.37).astype(dt)
        row = b[:64]
        for name, fn in ops.items():
            rows[f"{dt}.{n}.{name}.vv"] = bits(fn(a, b))
            rows[f"{dt}.{n}.{name}.scalar"] = bits(fn(a, sc))
            rows[f"{dt}.{n}.{name}.pyscalar"] = bits(fn(a, 0.37))
            if n % 64 == 0:
                rows[f"{dt}.{n}.{name}.row"] = bits(fn(a.reshape(-1, 64)[: n // 64], row))
# compiled (fused-chain interpreter) programs: silu, swiglu, gated/norm-like and g-gate style chains
from mlx import nn  # noqa: E402

chains = {
    "c_silu": mx.compile(lambda a, b: nn.silu(a)),
    "c_swiglu": mx.compile(lambda a, b: nn.silu(a) * b),
    "c_expmul": mx.compile(lambda a, b: mx.exp(-mx.abs(a)) * b - a),
    "c_gate": mx.compile(lambda a, b: mx.exp(-mx.exp(a * 0.1) * mx.sigmoid(b + 0.5))),
    "c_tanh": mx.compile(lambda a, b: mx.tanh(a) * mx.sigmoid(b) + mx.square(a)),
    "c_maxmin": mx.compile(lambda a, b: mx.minimum(mx.maximum(a, b), a * 2.0) / (mx.abs(b) + 1.0)),
}
for dt in (mx.float32, mx.float16, mx.bfloat16):
    for n in (4096, 65536 + 3, 1 << 20):
        a = base(n, dt)
        b = mx.array(np.array(base(n, dt)[::-1].astype(mx.float32)), dtype=mx.float32).astype(dt)
        for name, fn in chains.items():
            rows[f"{dt}.{n}.{name}.vv"] = bits(fn(a, b))
            if n % 64 == 0:
                rows[f"{dt}.{n}.{name}.row"] = bits(fn(a.reshape(-1, 64), b[:64]))
# depthwise conv1d (GatedDeltaNet prefill conv) plus non-depthwise / padded controls that must stay on conv.comp
for dt in (mx.float32, mx.float16, mx.bfloat16):
    for (nb, length, ch, taps) in ((1, 2051, 6144, 4), (2, 67, 250, 4), (1, 1, 96, 4), (1, 40, 130, 3), (1, 33, 64, 7)):
        xin = (mx.random.normal((nb, length + taps - 1, ch)) * 2).astype(dt)
        wgt = (mx.random.normal((ch, taps, 1))).astype(dt)
        rows[f"{dt}.conv_dw.{nb}.{length}.{ch}.{taps}"] = bits(mx.conv1d(xin, wgt, groups=ch))
        rows[f"{dt}.conv_dw_silu.{nb}.{length}.{ch}.{taps}"] = bits(nn.silu(mx.conv1d(xin, wgt, groups=ch)))
    xin = (mx.random.normal((1, 70, 64))).astype(dt)
    rows[f"{dt}.conv_pad"] = bits(mx.conv1d(xin, mx.random.normal((64, 4, 1)).astype(dt), padding=2, groups=64))
    rows[f"{dt}.conv_stride"] = bits(mx.conv1d(xin, mx.random.normal((64, 4, 1)).astype(dt), stride=2, groups=64))
    rows[f"{dt}.conv_dense"] = bits(mx.conv1d(xin, mx.random.normal((32, 4, 64)).astype(dt)))
print(json.dumps(rows, indent=0, sort_keys=True))
