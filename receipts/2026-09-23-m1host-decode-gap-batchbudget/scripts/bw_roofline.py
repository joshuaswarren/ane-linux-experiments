#!/usr/bin/env python3
"""Achievable-bandwidth roofline on the m1-host GPU: large d2d copy
(read+write) and a sum reduce (read-only), the two access patterns the
decode kernels are made of. 3 warmups + 10 reps, median."""
import time
import mlx.core as mx

N = 1 << 28  # 512 MiB of bf16

src = mx.ones((N,), dtype=mx.bfloat16)
mx.eval(src)

def bench(fn, reps=10, warm=3):
    for _ in range(warm):
        mx.eval(fn())
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        mx.eval(fn())
        ts.append(time.perf_counter() - t0)
    ts.sort()
    return ts[len(ts) // 2]

med = bench(lambda: mx.abs(src))
print(f"abs   512MiB bf16 (r+w 1.0GiB): {2 * N * 2 / med / 1e9:6.1f} GB/s  median {med * 1e3:.2f} ms")

med = bench(lambda: mx.sum(src, keepdims=True))
print(f"sum   512MiB bf16 (read only): {N * 2 / med / 1e9:6.1f} GB/s  median {med * 1e3:.2f} ms")

big = mx.ones((N,), dtype=mx.float32)
mx.eval(big)
med = bench(lambda: mx.abs(big))
print(f"abs   1GiB f32   (r+w 2.0GiB): {8 * N / med / 1e9:6.1f} GB/s  median {med * 1e3:.2f} ms")
