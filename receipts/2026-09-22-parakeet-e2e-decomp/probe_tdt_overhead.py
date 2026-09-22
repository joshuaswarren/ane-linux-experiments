#!/usr/bin/env python3
"""Isolate fixed per-dispatch/eval cost: trivial metal kernel, K evals.
Usage: probe_tdt_overhead.py <iters>
"""
import sys, time, statistics
import numpy as np
import mlx.core as mx

iters = int(sys.argv[1])
k = mx.fast.metal_kernel(
    name="probe_tiny",
    input_names=["x"],
    output_names=["y"],
    source="""
        uint t = thread_index_in_threadgroup.x;
        y[t] = float(x[t]) + 1.0f;
    """,
)
x = mx.array(np.ones(64, np.float32))
mx.eval(x)
xs = []
for _ in range(iters):
    t = time.monotonic_ns()
    (y,) = k(inputs=[x], output_shapes=[(64,)], output_dtypes=[mx.float32],
            grid=(64, 1, 1), threadgroup=(64, 1, 1), stream=mx.gpu)
    d1 = (time.monotonic_ns() - t) / 1e6
    mx.eval(y)
    d2 = (time.monotonic_ns() - t) / 1e6
    xs.append((d1, d2))
med = lambda i: round(statistics.median([a[i] for a in xs]), 4)
print(f"dispatch_ms={med(0)} dispatch_plus_eval_ms={med(1)}")
# 5 dispatches then one eval (run_step shape)
xs5 = []
for _ in range(iters):
    t = time.monotonic_ns()
    ys = []
    for _ in range(5):
        (y,) = k(inputs=[x], output_shapes=[(64,)], output_dtypes=[mx.float32],
                grid=(64, 1, 1), threadgroup=(64, 1, 1), stream=mx.gpu)
        ys.append(y)
    mx.eval(*ys)
    xs5.append((time.monotonic_ns() - t) / 1e6)
print(f"five_dispatch_one_eval_ms={round(statistics.median(xs5),4)}")
