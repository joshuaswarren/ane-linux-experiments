#!/usr/bin/env python3
"""Roofline efficiency of the small-op kernels used by Qwen3.8 prefill (T tokens). Each row: ms per op
(N=8 independent ops evaluated together, sync floor amortized), bytes moved (in+out) and GB/s vs a 300 GB/s
roof. usage: kernel_efficiency.py [T]"""
import json
import statistics as st
import sys
import time

import mlx.core as mx
from mlx import nn

T = int(sys.argv[1]) if len(sys.argv) > 1 else 2048
N = 8
C, HK, D = 6144, 16, 128
bf, f32 = mx.bfloat16, mx.float32
mx.random.seed(0)
qkv = mx.random.normal((1, T, C)).astype(bf)
state = mx.zeros((1, 3, C), dtype=bf)
w = mx.random.normal((C, 4, 1)).astype(bf)
q = mx.random.normal((1, T, HK, D)).astype(bf)
z = mx.random.normal((1, T, HK, D)).astype(bf)
wn = mx.random.normal((D,)).astype(bf)
cin = mx.concatenate([state, qkv], axis=1)
gate = mx.random.normal((1, T, 6144)).astype(bf)
up = mx.random.normal((1, T, 6144)).astype(bf)
mx.eval(qkv, state, w, q, z, wn, cin, gate, up)


def bench(fn, nbytes):
    for _ in range(2):
        mx.eval([fn() for _ in range(N)])
    ts = []
    for _ in range(5):
        t0 = time.perf_counter()
        mx.eval([fn() for _ in range(N)])
        ts.append((time.perf_counter() - t0) / N)
    t = st.median(ts)
    return {"ms": round(t * 1000, 3), "MB": round(nbytes / 1e6, 1), "GB_s": round(nbytes / t / 1e9, 1),
            "roof_eff_pct": round(nbytes / t / 3e9, 1)}


def swiglu(g, u):
    return nn.silu(g) * u


sw = mx.compile(swiglu)
E = T * C
rows = {"T": T}
rows["conv1d_dw_k4 bf16"] = bench(lambda: mx.conv1d(cin, w, groups=C), (E + E) * 2)
rows["astype bf16->f32"] = bench(lambda: qkv.astype(f32), E * 6)
rows["astype f32->bf16"] = bench(lambda: qkv.astype(f32).astype(bf), E * 8)
rows["transpose copy [T,16,128]"] = bench(lambda: mx.contiguous(q.transpose(0, 2, 1, 3)), T * HK * D * 4)
rows["concat state+qkv"] = bench(lambda: mx.concatenate([state, qkv], axis=1), E * 4)
rows["silu bf16"] = bench(lambda: nn.silu(qkv), E * 4)
rows["swiglu compiled bf16"] = bench(lambda: sw(gate, up), E * 6)
rows["silu(gate)*up uncompiled"] = bench(lambda: nn.silu(gate) * up, E * 6)
rows["rms_norm w [T*16,128]"] = bench(lambda: mx.fast.rms_norm(q, wn, 1e-6), T * HK * D * 4)
rows["rms_norm none [T*16,128]"] = bench(lambda: mx.fast.rms_norm(q, None, 1e-6), T * HK * D * 4)
rows["q*scalar bf16"] = bench(lambda: q * 0.0883883, T * HK * D * 4)
rows["add bf16 vv (vec path)"] = bench(lambda: qkv + qkv, E * 6)
rows["mul f32 vv"] = bench(lambda: qkv.astype(f32) * 2.0, E * 8)
print(json.dumps(rows, indent=1))
