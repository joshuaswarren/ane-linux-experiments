#!/usr/bin/env python3
"""Leg-level check: mx.fast.gated_delta_update (fused) vs gated_delta_ops.

T=512, B=1, Hk=Hv=16, Dk=Dv=128, bf16 q/k/v/beta, f32 gates (compute_g
shape), f32 state. Reports max abs diff of output and state, plus timings.
"""
import json
import sys
import time

import mlx.core as mx
import mlx.nn as nn
from functools import partial

sys.path.insert(0, "/var/tmp/gdn-exact-probe")
from gated_delta_ref import gated_delta_ops, compute_g  # noqa: E402


def make_inputs(T=512, B=1, Hk=16, Dk=128, Dv=128, mask=None, seed=0):
    rng = mx.random.state  # deterministic via numpy instead
    import numpy as np
    rs = np.random.RandomState(seed)
    q = mx.array((0.25 * rs.randn(B, T, Hk, Dk)).astype("float16")).astype(mx.bfloat16)
    k = mx.array((0.25 * rs.randn(B, T, Hk, Dk)).astype("float16")).astype(mx.bfloat16)
    v = mx.array((0.25 * rs.randn(B, T, Hk, Dv)).astype("float16")).astype(mx.bfloat16)
    beta = mx.sigmoid(mx.array((0.25 * rs.randn(B, T, Hk)).astype("float16")).astype(mx.bfloat16))
    A_log = mx.array((0.5 * rs.randn(Hk)).astype("float32"))
    a = mx.array((0.25 * rs.randn(B, T, Hk)).astype("float16")).astype(mx.bfloat16)
    dt_bias = mx.array((0.5 * rs.randn(Hk)).astype("float32"))
    g = compute_g(A_log, a, dt_bias)
    m = None
    if mask == "all":
        m = mx.ones((B, T), mx.bool_)
    elif mask == "pad":
        m = mx.ones((B, T), mx.bool_)
        m[:, T // 2:] = False
    return q, k, v, g, beta, m


def timeit(fn, reps=20, warm=3):
    for _ in range(warm):
        mx.eval(fn())
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        out = fn()
        mx.eval(out)
        ts.append((time.perf_counter() - t0) * 1e3)
    ts.sort()
    return ts[len(ts) // 2]


def main():
    results = {}
    for mask in [None, "all", "pad"]:
        q, k, v, g, beta, m = make_inputs(mask=mask)
        # ops reference
        y_ops, s_ops = gated_delta_ops(q, k, v, g, beta, None, m)
        mx.eval(y_ops, s_ops)
        # fused primitive (routed by the patched mlx-lm or direct fast call)
        y_f, s_f = mx.fast.gated_delta_update(q, k, v, g, beta, None, m)
        mx.eval(y_f, s_f)
        dy = mx.abs(y_f.astype(mx.float32) - y_ops.astype(mx.float32)).max().item()
        import mlx.core as _mx
        ybit = mx.array_equal(y_f, y_ops).item()
        ds = mx.abs(s_f - s_ops).max().item()
        t_fused = timeit(lambda: mx.eval(*mx.fast.gated_delta_update(q, k, v, g, beta, None, m)))
        t_ops = timeit(lambda: mx.eval(*gated_delta_ops(q, k, v, g, beta, None, m)))
        # bit-identity check
        y_same = mx.array_equal(y_f, y_ops).item()
        s_same = mx.array_equal(s_f, s_ops).item()
        results[str(mask)] = {
            "out_max_abs_diff": dy,
            "state_max_abs_diff": ds,
            "out_bit_identical": y_same,
            "state_bit_identical": s_same,
            "fused_ms": t_fused,
            "ops_ms": t_ops,
        }
        print(mask, results[str(mask)], flush=True)
    with open("/var/tmp/gdn-exact-probe/leg_results.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
