#!/usr/bin/env python3
"""ns/element of chained elementwise ops vs tensor size: general kernel (f32 mul, bf16 mul-by-scalar)
vs the 16-bit vec path (bf16 add). N=8 chained ops per eval; linear scaling in N was verified 2026-09-29."""
import json
import statistics as st
import time

import mlx.core as mx

N = 8


def run(fn, x):
    def f():
        y = x
        for _ in range(N):
            y = fn(y)
        return y
    for _ in range(2):
        mx.eval(f())
    ts = []
    for _ in range(7):
        t = time.perf_counter()
        mx.eval(f())
        ts.append(time.perf_counter() - t)
    return st.median(ts) / N


ops = {"f32.mul_scalar": (lambda y: y * 0.5, mx.float32), "f32.add_self": (lambda y: y + y, mx.float32),
       "bf16.mul_scalar": (lambda y: y * 0.5, mx.bfloat16), "bf16.add_self": (lambda y: y + y, mx.bfloat16),
       "f32.exp": (mx.exp, mx.float32)}
rows = {}
for elems in (1 << 16, 1 << 20, 1 << 22, 12582912, 1 << 25):
    for name, (fn, dt) in ops.items():
        x = (mx.random.normal((elems,)) * 0.001).astype(dt)
        mx.eval(x)
        t = run(fn, x)
        rows[f"{name}@{elems}"] = {"ms": round(t * 1000, 3), "ns_per_elem": round(t / elems * 1e9, 3),
                                   "GB_s": round(elems * mx.array(0, dtype=dt).itemsize * 2 / t / 1e9, 1)}
print(json.dumps(rows, indent=1))
