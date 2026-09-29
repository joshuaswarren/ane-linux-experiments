import statistics as st
import time

import mlx.core as mx
import mlx.nn as nn

N = 128
D = 2048
H = 6144
w = mx.random.normal((D,)).astype(mx.bfloat16)
x0 = mx.random.normal((1, D)).astype(mx.bfloat16)
u = mx.random.normal((1, H)).astype(mx.bfloat16)
z0 = mx.random.normal((1, H)).astype(mx.bfloat16)
r = mx.random.normal((1, D)).astype(mx.bfloat16)
wq = mx.random.normal((D, D)).astype(mx.bfloat16)
qw, qs, qb = mx.quantize(wq, group_size=64, bits=4)
mx.eval(w, x0, u, z0, r, qw, qs, qb)


def chain(name, fn, x, reps=7):
    def run():
        y = x
        for _ in range(N):
            y = fn(y)
        mx.eval(y)

    run()
    run()
    ts = []
    for _ in range(reps):
        t = time.perf_counter()
        run()
        ts.append((time.perf_counter() - t) / N * 1e6)
    print(f"{name}: {st.median(ts):.1f} us/op (min {min(ts):.1f})", flush=True)


chain("rms_norm 2048", lambda y: mx.fast.rms_norm(y, w, 1e-6), x0)
chain("add 2048", lambda y: y + r, x0)
chain("silu*u 6144", lambda z: nn.silu(z) * u, z0)
chain("qmm M1 2048x2048", lambda y: mx.quantized_matmul(y, qw, qs, qb, transpose=True, group_size=64, bits=4), x0)
chain("qmm+rms", lambda y: mx.fast.rms_norm(mx.quantized_matmul(y, qw, qs, qb, transpose=True, group_size=64, bits=4), w, 1e-6), x0)
