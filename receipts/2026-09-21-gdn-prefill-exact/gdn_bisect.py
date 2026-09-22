#!/usr/bin/env python3
"""Bisect the fused-vs-ops mismatch: isolate decay / kv / update / output."""
import sys
sys.path.insert(0, "/var/tmp/gdn-exact-probe")
import numpy as np
import mlx.core as mx
from gated_delta_ref import gated_delta_ops


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

q, k, v, g, beta = make(2)

def run(qq, kk, vv, gg, bb, label):
    y_ops, s_ops = gated_delta_ops(qq, kk, vv, gg, bb, None, None)
    y_f, s_f = mx.fast.gated_delta_update(qq, kk, vv, gg, bb, None, None)
    mx.eval(y_ops, s_ops, y_f, s_f)
    sd = mx.abs(s_f - s_ops).max().item()
    yd = mx.abs(y_f[:, 0].astype(mx.float32) - y_ops[:, 0].astype(mx.float32)).max().item()
    yd1 = mx.abs(y_f[:, 1].astype(mx.float32) - y_ops[:, 1].astype(mx.float32)).max().item()
    print(f"{label:24s} state_diff={sd:.3e} y0_diff={yd:.3e} y1_diff={yd1:.3e}", flush=True)

run(q, k, v, g, beta, "full")
ones = mx.ones_like(g)
zeros_b = mx.zeros_like(beta)
run(q, k, v, mx.ones_like(g), beta, "g=1")
run(q, k, v, g, zeros_b, "beta=0")
run(q, k, v, mx.ones_like(g), zeros_b, "g=1,beta=0")
# zero v: delta = (0 - kv)*beta -> pure kv/delta path
run(q, k, v * 0, g, beta, "v=0")
