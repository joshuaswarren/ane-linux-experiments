#!/usr/bin/env python3
"""Dominant Qwen3.8-2B prefill QMM shapes (from the pinned bf16-hybrid
snapshot, per-layer linear weights): m=512, per-layer 3x gate/up/qkv
(6144,2048), 2x z/out (2048,2048), 1x down (2048,6144). Times native
mx.quantized_matmul (bf16 x / bf16 scales / bf16 out) and reports
effective GFLOPS. Greedy-token identity is covered by qwen38-mlx-bench.
"""
import json
import sys
import time

import mlx.core as mx

M = 512
REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
SHAPES = (
    [("gate/up/qkv", 6144, 2048)] * 3
    + [("z/out", 2048, 2048)] * 2
    + [("down", 2048, 6144)]
)

results = []
for name, n, k in SHAPES:
    x = (mx.random.normal((M, k)) * 0.1).astype(mx.bfloat16)
    wq = mx.quantize((mx.random.normal((n, k)) * 0.05).astype(mx.bfloat16),
                     bits=4, group_size=64)
    w, scales, biases = wq
    assert str(scales.dtype) == "mlx.core.bfloat16", scales.dtype
    for _ in range(3):
        out = mx.quantized_matmul(x, w, scales, biases, transpose=True,
                                  group_size=64)
    mx.eval(out)
    t0 = time.perf_counter()
    for _ in range(REPS):
        out = mx.quantized_matmul(x, w, scales, biases, transpose=True,
                                  group_size=64)
        mx.eval(out)
    dt = (time.perf_counter() - t0) / REPS
    gf = 2.0 * M * n * k / dt / 1e9
    results.append({"shape": name, "n": n, "k": k, "ms": dt * 1e3,
                    "gflops": round(gf, 1)})
    print(f"{name:10s} n={n} k={k} {dt*1e3:8.2f} ms {gf:8.1f} GFLOP/s",
          flush=True)

per_layer = sum(r["ms"] for r in results)
print(json.dumps({"m": M, "per_layer_ms": round(per_layer, 3),
                  "per_layer_gflops_total": results, "results": results}))
