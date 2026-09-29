#!/usr/bin/env python3
"""Which elementwise primitive makes silu 6x slower than add? Same [1,T,6144] tensor, ops chained N=8 times
inside one eval so the ~0.15 ms eval-sync floor amortizes. Rows: ms per op (total/N).
usage: transcendental_micro.py [T]"""
import json
import statistics as st
import sys
import time

import mlx.core as mx
from mlx import nn

T = int(sys.argv[1]) if len(sys.argv) > 1 else 2048
N = 8
mx.random.seed(0)
x16 = mx.random.normal((1, T, 6144)).astype(mx.bfloat16)
x32 = x16.astype(mx.float32)
mx.eval(x16, x32)


def chain(fn, x):
    def run():
        y = x
        for _ in range(N):
            y = fn(y)
        return y
    return run


def timeit(fn):
    for _ in range(2):
        mx.eval(fn())
    ts = []
    for _ in range(7):
        t0 = time.perf_counter()
        mx.eval(fn())
        ts.append(time.perf_counter() - t0)
    return round(st.median(ts) * 1000 / N, 3)


ops = {
    "add(y+y)": lambda y: y + y,
    "mul(y*0.5)": lambda y: y * 0.5,
    "exp": lambda y: mx.exp(y * 0.001),
    "sigmoid": lambda y: mx.sigmoid(y),
    "silu": lambda y: nn.silu(y),
    "divide(1/(1+y*y))": lambda y: 1.0 / (1.0 + y * y * 1e-6),
    "rsqrt": lambda y: mx.rsqrt(y * y + 1.0),
    "tanh": lambda y: mx.tanh(y),
    "erf(gelu-ish)": lambda y: mx.erf(y),
}
rows = {"T": T, "elems": T * 6144}
for name, fn in ops.items():
    rows[f"bf16.{name}"] = timeit(chain(fn, x16))
    rows[f"f32.{name}"] = timeit(chain(fn, x32))
print(json.dumps(rows, indent=1))
