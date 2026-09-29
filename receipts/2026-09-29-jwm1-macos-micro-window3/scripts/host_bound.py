import statistics as st
import time

import mlx.core as mx

N = 128
D = 2048
w = mx.random.normal((D,)).astype(mx.bfloat16)
x0 = mx.random.normal((1, D)).astype(mx.bfloat16)
r = mx.random.normal((1, D)).astype(mx.bfloat16)
wq = mx.random.normal((D, D)).astype(mx.bfloat16)
qw, qs, qb = mx.quantize(wq, group_size=64, bits=4)
mx.eval(w, x0, r, qw, qs, qb)


def probe(name, fn, reps=9):
    rows = []
    for i in range(reps + 2):
        t0 = time.perf_counter()
        y = x0
        for _ in range(N):
            y = fn(y)
        t1 = time.perf_counter()
        mx.async_eval(y)
        t2 = time.perf_counter()
        mx.eval(y)
        t3 = time.perf_counter()
        if i >= 2:
            rows.append(((t1 - t0) / N * 1e6, (t2 - t1) / N * 1e6, (t3 - t2) / N * 1e6))
    m = [st.median(c) for c in zip(*rows)]
    print(f"{name}: build {m[0]:.1f} us/op, async_eval-return {m[1]:.1f} us/op, wait-after {m[2]:.1f} us/op, total {m[1] + m[2]:.1f}", flush=True)


probe("add 2048", lambda y: y + r)
probe("rms_norm 2048", lambda y: mx.fast.rms_norm(y, w, 1e-6))
probe("qmm 2048x2048", lambda y: mx.quantized_matmul(y, qw, qs, qb, transpose=True, group_size=64, bits=4))
