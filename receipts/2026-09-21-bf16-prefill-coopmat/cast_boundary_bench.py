#!/usr/bin/env python3
"""Cast-to-f16 boundary vs native bf16 coopmat, dominant prefill shape.

Native: bf16 x + bf16 scales -> (backend routes to QmmPrefillCoopmatBF16).
Cast boundary: x bf16->f16 each call, qmm f16 (f16 scales, cast once),
out f16->bf16 each call. Times full per-call chains at m=512.
"""
import time

import mlx.core as mx

M, N, K = 512, 6144, 2048
REPS = 20

x = (mx.random.normal((M, K)) * 0.1).astype(mx.bfloat16)
wq16 = mx.quantize((mx.random.normal((N, K)) * 0.05).astype(mx.float16),
                   bits=4, group_size=64)
w16, s16, b16 = wq16


def native():
    out = mx.quantized_matmul(x, x, x, x)  # placeholder replaced below
    return out


def bench(fn, label):
    for _ in range(3):
        mx.eval(fn())
    t0 = time.perf_counter()
    for _ in range(REPS):
        mx.eval(fn())
    dt = (time.perf_counter() - t0) / REPS
    gf = 2.0 * M * N * K / dt / 1e9
    print(f"{label:28s} {dt*1e3:8.2f} ms {gf:8.1f} GFLOP/s", flush=True)
    return dt


def chain_cast():
    xh = x.astype(mx.float16)
    out = mx.quantized_matmul(xh, w16, s16, b16, transpose=True, group_size=64)
    return out.astype(mx.bfloat16)


def native_bf16():
    return mx.quantized_matmul(x, w16.astype(mx.bfloat16), s16.astype(mx.bfloat16), b16.astype(mx.bfloat16), transpose=True, group_size=64)


bench(native_bf16, "native bf16 qmm")
bench(chain_cast, "cast->f16 qmm ->cast bf16")
