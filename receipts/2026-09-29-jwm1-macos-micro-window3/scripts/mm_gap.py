import json
import statistics as st
import time

import mlx.core as mx

A = mx.random.normal((1024, 1024))
B = mx.random.normal((1024, 1024))
mx.eval(A, B)
for _ in range(30):
    mx.eval(mx.matmul(A, B))
out = {}
for gap_ms in (0, 0.2, 0.5, 1, 2, 5, 10, 20, 50):
    rows = []
    for i in range(25):
        if gap_ms:
            time.sleep(gap_ms / 1e3)
        t = time.perf_counter()
        mx.eval([mx.matmul(A, B) for _ in range(2)])
        rows.append((time.perf_counter() - t) / 2 * 1e3)
    out[f"gap{gap_ms}ms"] = round(st.median(rows[3:]), 2)
print("MMGAP", json.dumps(out))
