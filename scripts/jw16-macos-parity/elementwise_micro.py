#!/usr/bin/env python3
"""Isolate the slow small ops found in GDN prefill (T tokens, conv_dim 6144, 16x128 heads).
Each row: eval-synced median ms of one op. Same script for Linux/macOS. usage: elementwise_micro.py [T]"""
import json
import statistics as st
import sys
import time

import mlx.core as mx
from mlx import nn

T = int(sys.argv[1]) if len(sys.argv) > 1 else 2048
REPS = 7
C, HK, HV, D = 6144, 16, 16, 128
bf = mx.bfloat16


def timeit(fn):
    for _ in range(2):
        mx.eval(fn())
    ts = []
    for _ in range(REPS):
        t0 = time.perf_counter()
        mx.eval(fn())
        ts.append(time.perf_counter() - t0)
    return round(st.median(ts) * 1000, 3)


mx.random.seed(0)
qkv = mx.random.normal((1, T, C)).astype(bf)
state = mx.zeros((1, 3, C), dtype=bf)
w = mx.random.normal((C, 4, 1)).astype(bf)
q = mx.random.normal((1, T, HK, D)).astype(bf)
z = mx.random.normal((1, T, HV, D)).astype(bf)
wn = mx.random.normal((D,)).astype(bf)
mx.eval(qkv, state, w, q, z, wn)
cin = mx.concatenate([state, qkv], axis=1)
mx.eval(cin)
rows = {"T": T}
rows["concat[state,qkv]"] = timeit(lambda: mx.concatenate([state, qkv], axis=1))
rows["conv1d_depthwise_k4"] = timeit(lambda: mx.conv1d(cin, w, groups=C))
co = mx.conv1d(cin, w, groups=C)
mx.eval(co)
rows["silu"] = timeit(lambda: nn.silu(co))
rows["copy_contiguous_slice"] = timeit(lambda: mx.contiguous(cin[:, -3:, :]))
rows["rms_norm_noweight_[T,16,128]"] = timeit(lambda: mx.fast.rms_norm(q, None, 1e-6))
rows["rms_norm_weight_[T,16,128]"] = timeit(lambda: mx.fast.rms_norm(q, wn, 1e-6))
rows["scale_mul(rms*const)"] = timeit(lambda: 0.0883883 * mx.fast.rms_norm(q, None, 1e-6))
rows["rms_norm_gated(silu(z)*rms(q)*w)"] = timeit(lambda: mx.fast.rms_norm(q, wn, 1e-6) * nn.silu(z))
rows["elementwise_add_[T,6144]"] = timeit(lambda: qkv + qkv)
rows["copy_transpose_[T,16,128]"] = timeit(lambda: mx.contiguous(q.transpose(0, 2, 1, 3)))
print(json.dumps(rows, indent=1))
