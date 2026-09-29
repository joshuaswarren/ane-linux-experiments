import json
import statistics as st
import sys
import time

import mlx.core as mx

A = mx.random.normal((1024, 1024))
B = mx.random.normal((1024, 1024))
Ah = A.astype(mx.bfloat16)
Bh = B.astype(mx.bfloat16)
mx.eval(A, B, Ah, Bh)
for _ in range(20):
    mx.eval(mx.matmul(A, B), mx.matmul(Ah, Bh))
out = {}
for dt, (a, b) in (("f32", (A, B)), ("bf16", (Ah, Bh))):
    # sustained per-matmul time (back-to-back, 16 independent matmuls per eval)
    ts = []
    for _ in range(9):
        t = time.perf_counter()
        mx.eval([mx.matmul(a, b) for _ in range(16)])
        ts.append((time.perf_counter() - t) / 16 * 1e3)
    out[f"{dt}_sustained_ms"] = round(st.median(ts), 3)
    for gap in (0.0, 0.05, 0.5):
        rows = []
        for i in range(11):
            time.sleep(gap)
            t = time.perf_counter()
            mx.eval([mx.matmul(a, b) for _ in range(4)])
            rows.append((time.perf_counter() - t) / 4 * 1e3)
        out[f"{dt}_gap{gap}_first_ms"] = round(rows[1], 3)
        out[f"{dt}_gap{gap}_median2_10_ms"] = round(st.median(rows[2:]), 3)
print("MMIDLE", json.dumps(out))
