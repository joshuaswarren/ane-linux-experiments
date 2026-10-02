#!/usr/bin/env python3
"""norm_bitcheck.py — randomized RMSNorm row table for candidate-vs-serving bit equality.

Builds deterministic random cases across dtypes x row lengths x weight modes x seeds,
runs mx.fast.rms_norm on each, and prints one JSON object: {"rows": ["<sha16>:<meta>", ...],
"table_sha256": "..."} where each row hash covers the full output bytes. The serving venv
is the oracle; candidate arms must reproduce the identical table.
"""
import hashlib
import json

import mlx.core as mx
import numpy as np

bf16 = mx.bfloat16
mx.random.seed(1234)
rng = np.random.default_rng(1234)

DTYPES = [("float32", mx.float32), ("float16", mx.float16), ("bfloat16", bf16)]
LENGTHS = [128, 1024, 2048]
WEIGHT_MODES = ["full", "scalar"]
ROWS = []

case_id = 0
for dtype_name, dtype in DTYPES:
    for length in LENGTHS:
        for wmode in WEIGHT_MODES:
            for seed in range(5):
                case_id += 1
                np_x = (rng.standard_normal((2, length)) * 0.7).astype(np.float32)
                if wmode == "scalar":
                    np_w = np.array([1.3], dtype=np.float32)
                else:
                    np_w = (rng.standard_normal((length,)) * 0.1 + 1.0).astype(np.float32)
                x = mx.array(np_x).astype(dtype)
                w = mx.array(np_w).astype(dtype if wmode == "full" else mx.float32)
                for eps in (1e-6, 1e-5):
                    try:
                        y = mx.fast.rms_norm(x, w, eps)
                        mx.eval(y)
                        # f32 widening is lossless for f32/f16/bf16, so the widened
                        # bytes are a faithful row identity for every dtype.
                        digest = hashlib.sha256(
                            np.asarray(y.astype(mx.float32), dtype=np.float32).tobytes()
                        ).hexdigest()[:16]
                    except Exception as e:  # both sides must agree on the failure too
                        digest = "ERR:" + type(e).__name__
                    ROWS.append(
                        "%s:case%d:%s:%d:%s:eps%g" % (digest, case_id, dtype_name, length, wmode, eps)
                    )

table = hashlib.sha256("\n".join(ROWS).encode()).hexdigest()
print(json.dumps({"rows": ROWS, "n_rows": len(ROWS), "table_sha256": table}))
