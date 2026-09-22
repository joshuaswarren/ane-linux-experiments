#!/usr/bin/env python3
"""NaN hunt: direct fast call vs ops at increasing T; find first bad token."""
import numpy as np
import mlx.core as mx
from gated_delta_ref import gated_delta_ops, compute_g


def make(T, seed=0):
    rs = np.random.RandomState(seed)
    B, Hk, Dk, Dv, Hv = 1, 16, 128, 128, 16
    q = mx.array((0.25 * rs.randn(B, T, Hk, Dk)).astype("float16")).astype(mx.bfloat16)
    k = mx.array((0.25 * rs.randn(B, T, Hk, Dk)).astype("float16")).astype(mx.bfloat16)
    v = mx.array((0.25 * rs.randn(B, T, Hk, Dv)).astype("float16")).astype(mx.bfloat16)
    beta = mx.sigmoid(mx.array((0.25 * rs.randn(B, T, Hk)).astype("float16")).astype(mx.bfloat16))
    A_log = mx.array((0.5 * rs.randn(Hk)).astype("float32"))
    a = mx.array((0.25 * rs.randn(B, T, Hk)).astype("float16")).astype(mx.bfloat16)
    dt_bias = mx.array((0.5 * rs.randn(Hk)).astype("float32"))
    g = compute_g(A_log, a, dt_bias)
    return q, k, v, g, beta


def nans(a):
    return mx.isnan(a).sum().item()


for T in [2, 8, 63, 64, 65, 128, 130, 512]:
    q, k, v, g, beta = make(T)
    y_ops, s_ops = gated_delta_ops(q, k, v, g, beta, None, None)
    y_f, s_f = mx.fast.gated_delta_update(q, k, v, g, beta, None, None)
    mx.eval(y_ops, s_ops, y_f, s_f)
    out_diff = mx.abs(y_f.astype(mx.float32) - y_ops.astype(mx.float32)).max().item()
    state_diff = mx.abs(s_f - s_ops).max().item()
    bit = mx.array_equal(y_f, y_ops).item()
    print(
        f"T={T} ops_nan={nans(y_ops)} fused_nan={nans(y_f)} "
        f"out_diff={out_diff:.3e} state_diff={state_diff:.3e} bit={bit}",
        flush=True,
    )
