#!/usr/bin/env python3
"""norm_bitcheck_ext.py — high-seed model-shaped rms_norm comparison table.

500 bf16 cases at the model's exact signature ((1,1,2048), bf16 weight, eps 1e-6)
plus f32 controls, with varied magnitude regimes. Prints the same table format as
norm_bitcheck.py.
"""
import hashlib
import json

import mlx.core as mx
import numpy as np

bf16 = mx.bfloat16
rng = np.random.default_rng(777)
ROWS = []

def row(y):
    return hashlib.sha256(
        np.asarray(y.astype(mx.float32), dtype=np.float32).tobytes()
    ).hexdigest()[:16]

# 500 bf16 model-signature cases
for i in range(500):
    scale = [0.1, 0.7, 1.0, 3.0, 30.0][i % 5]
    np_x = (rng.standard_normal((1, 1, 2048)) * scale).astype(np.float32)
    np_w = (rng.standard_normal((2048,)) * 0.1 + 1.0).astype(np.float32)
    x = mx.array(np_x).astype(bf16)
    w = mx.array(np_w).astype(bf16)
    y = mx.fast.rms_norm(x, w, 1e-6)
    mx.eval(y)
    ROWS.append("%s:bf16-3d:%d:s%g" % (row(y), i, scale))

# 200 f32 controls (strictest: any fp difference in the pipeline shows here)
for i in range(200):
    scale = [0.1, 1.0, 10.0][i % 3]
    np_x = (rng.standard_normal((1, 1, 2048)) * scale).astype(np.float32)
    np_w = (rng.standard_normal((2048,)) * 0.1 + 1.0).astype(np.float32)
    x = mx.array(np_x).astype(mx.float32)
    w = mx.array(np_w).astype(mx.float32)
    y = mx.fast.rms_norm(x, w, 1e-6)
    mx.eval(y)
    ROWS.append("%s:f32-3d:%d:s%g" % (row(y), i, scale))

# 100 2-row bf16 batches
for i in range(100):
    np_x = (rng.standard_normal((2, 2048)) * 0.7).astype(np.float32)
    np_w = (rng.standard_normal((2048,)) * 0.1 + 1.0).astype(np.float32)
    x = mx.array(np_x).astype(bf16)
    w = mx.array(np_w).astype(bf16)
    y = mx.fast.rms_norm(x, w, 1e-6)
    mx.eval(y)
    ROWS.append("%s:bf16-2row:%d" % (row(y), i))

table = hashlib.sha256("\n".join(ROWS).encode()).hexdigest()
print(json.dumps({"n_rows": len(ROWS), "rows": ROWS, "table_sha256": table}))
