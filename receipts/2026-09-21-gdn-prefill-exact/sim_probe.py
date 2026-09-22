#!/usr/bin/env python3
"""Simulate ops (separate rounding) vs fma variants in strict f32 numpy;
compare against the actual ops and fused results elementwise."""
import sys
sys.path.insert(0, "/var/tmp/gdn-exact-probe")
import numpy as np
import mlx.core as mx
from gdn_bisect import make  # reuses make(); bisect main already ran? no—import safe
from gated_delta_ref import gated_delta_ops

q, k, v, g, beta = make(2)
qn = np.asarray(q.astype(mx.float32))
kn = np.asarray(k.astype(mx.float32))
vn = np.asarray(v.astype(mx.float32))
bn = np.asarray(beta.astype(mx.float32))
gn = np.asarray(g)  # f32 already
Hv, Dv, Dk = 16, 128, 128

def np_f32(x):
    return x.astype(np.float32)

def run_sim(mode):
    S = np.zeros((Hv, Dv, Dk), np.float32)
    for t in range(2):
        A = np_f32(S * gn[0, t, :, None, None])
        kv = np.zeros((Hv, Dv), np.float32)
        for i in range(Dk):
            if mode == "sep_kv" or mode == "sep":
                kv += np_f32(A[:, :, i] * kn[0, t, :, :])
            else:  # fma kv
                kv = np_f32(kv + A[:, :, i] * kn[0, t, :, :])  # same in np
        delta = np_f32((vn[0, t] - kv) * bn[0, t, :, None])
        if mode in ("sep", "sep_kv"):
            S = np_f32(A + np_f32(kn[0, t, :, None, :] * delta[:, :, None]))
        else:
            S = np_f32(A + np_f32(kn[0, t, :, None, :] * delta[:, :, None]))
    return S

S_sep = run_sim("sep")
y_ops, s_ops = gated_delta_ops(q, k, v, g, beta, None, None)
y_f, s_f = mx.fast.gated_delta_update(q, k, v, g, beta, None, None)
mx.eval(y_ops, s_ops, y_f, s_f)
s_ops_np = np.asarray(s_ops.astype(mx.float32))[0]
s_f_np = np.asarray(s_f.astype(mx.float32))[0]
print("ops    vs sim-sep:", np.abs(s_ops_np - S_sep).max())
print("fused  vs sim-sep:", np.abs(s_f_np - S_sep).max())
# where do ops and fused differ? first element
d = np.abs(s_f_np - s_ops_np)
idx = np.unravel_index(np.argmax(d), d.shape)
print("max diff at (head,dv,dk) =", idx, "diff", d[idx])
h, r, c = idx
# recompute that row by hand under both rounding styles
print("ops   state row:", s_ops_np[h, r, max(0, c - 2):c + 3])
print("fused state row:", s_f_np[h, r, max(0, c - 2):c + 3])
