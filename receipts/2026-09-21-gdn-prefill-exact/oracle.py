#!/usr/bin/env python3
"""Numpy f32 oracle for 2 tokens on one (head,row): who deviates?"""
import sys
sys.path.insert(0, "/var/tmp/gdn-exact-probe")
import numpy as np
import mlx.core as mx
from nan_hunt import make
from gated_delta_ref import gated_delta_ops

q, k, v, g, beta = make(2)  # [B,T,Hk,Dk] etc, bf16; g f32 [B,T,H]
B, T, Hk, Dk = q.shape
Hv, Dv = v.shape[2], v.shape[3]

qn, kn, vn = (np.asarray(x.astype(mx.float32), np.float32) for x in (q, k, v))
bn = np.asarray(beta.astype(mx.float32), np.float32)
gn = np.asarray(g, np.float32)

S = np.zeros((Hv, Dv, Dk), np.float32)
for t in range(T):
    S = S * gn[0, t, :, None, None]
    P = S * kn[0, t, 0, None, :]           # head0 of k (Hk==Hv case 1:1)
    kv = np.zeros((Hv, Dv), np.float32)
    for i in range(Dk):
        kv += P[:, :, i]                   # sequential ascending sum
    delta = (vn[0, t, :, :] - kv) * bn[0, t, :, None]
    S = S + kn[0, t, 0, None, :] * delta[:, :, None]
    if t == 1:
        y_exact = S.copy()

y_ops, s_ops = gated_delta_ops(q, k, v, g, beta, None, None)
y_f, s_f = mx.fast.gated_delta_update(q, k, v, g, beta, None, None)
mx.eval(y_ops, s_ops, y_f, s_f)

s_ops_np = s_ops[0].astype(mx.float32)
s_f_np = s_f[0].astype(mx.float32)
print("oracle vs ops  state maxdiff", np.abs(y_exact - s_ops_np).max())
print("oracle vs fused state maxdiff", np.abs(y_exact - s_f_np).max())
print("ops   vs fused state maxdiff", np.abs(s_f_np - s_ops_np).max())
# bf16-rounded comparison of state (kernel loads/states are f32; check if
# the fused path's state equals the oracle after bf16-quantizing inputs)
def b16(x):
    u = x.view(np.uint32)
    r = ((u + 0x7FFF + ((u >> 16) & 1)) >> 16).astype(np.uint16)
    return (r << 16).view(np.float32)
print("oracle-bf16inputs vs fused:", np.abs(
    y_exact - s_f_np).max(), "(f32 oracle)")
