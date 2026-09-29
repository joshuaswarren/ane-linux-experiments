#!/usr/bin/env python3
"""Why is standalone nn.silu (2.1 ms for [1,2048,6144] bf16) 8x slower than a compiled swiglu (0.28 ms)?"""
import statistics as st
import time

import mlx.core as mx
from mlx import nn

N = 8
x = mx.random.normal((1, 2048, 6144)).astype(mx.bfloat16)
mx.eval(x)


def bench(name, fn):
    for _ in range(2):
        mx.eval([fn() for _ in range(N)])
    ts = []
    for _ in range(5):
        t0 = time.perf_counter()
        mx.eval([fn() for _ in range(N)])
        ts.append((time.perf_counter() - t0) / N)
    print(f"{name:40s} {st.median(ts) * 1000:.3f} ms")


bench("mx.sigmoid(x)", lambda: mx.sigmoid(x))
bench("x * mx.sigmoid(x) eager", lambda: x * mx.sigmoid(x))
bench("nn.silu(x) (shapeless compile)", lambda: nn.silu(x))
bench("mx.compile(x*sigmoid(x))", mx.compile(lambda: x * mx.sigmoid(x)))
c2 = mx.compile(lambda a: a * mx.sigmoid(a))
bench("compiled silu, arg", lambda: c2(x))
c3 = mx.compile(lambda a: a * mx.sigmoid(a), shapeless=True)
bench("compiled silu shapeless", lambda: c3(x))
c4 = mx.compile(lambda a, b: nn.silu(a) * b)
bench("compiled silu(a)*b", lambda: c4(x, x))
