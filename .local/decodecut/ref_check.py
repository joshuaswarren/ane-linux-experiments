import mlx.core as mx
import mlx.nn as nn
import numpy as np

mx.random.seed(0)
H, D = 16, 128
q = mx.random.normal((1, 1, H, D)).astype(mx.bfloat16)
k = mx.random.normal((1, 1, H, D)).astype(mx.bfloat16)
v = mx.random.normal((1, 1, H, D)).astype(mx.bfloat16)
state0 = mx.random.normal((1, H, D, D)).astype(mx.float32)
A_log = mx.random.normal((H,)).astype(mx.bfloat16)
dt_bias = mx.random.normal((H,)).astype(mx.float32)
a = mx.random.normal((1, 1, H)).astype(mx.bfloat16)
b = mx.random.normal((1, 1, H)).astype(mx.bfloat16)

g = mx.exp(-mx.exp(A_log.astype(mx.float32)) * nn.softplus(a + dt_bias)).astype(mx.bfloat16)  # (1,1,H)
beta = mx.sigmoid(b)  # (1,1,H)

# pure-python decode reference (f32 math, bf16 gate rounding already applied)
qf = q.astype(mx.float32); kf = k.astype(mx.float32); vf = v.astype(mx.float32)
st_ref = mx.empty((1, H, D, D), mx.float32)
for h in range(H):
    kv = (state0[0, h] * g[0, 0, h]) @ kf[0, 0, h]          # (Dv, Dk) @ (Dk,) -> (Dv,)
    delta = (vf[0, 0, h] - kv) * beta[0, 0, h]
    st_ref[0, h] = state0[0, h] * g[0, 0, h] + mx.outer(delta, kf[0, 0, h])
mx.eval(st_ref)
print("ref stats: min", float(st_ref.min()), "max", float(st_ref.max()),
      "nan", int(mx.isnan(st_ref).sum()))

out_e, st_e = mx.fast.gated_delta_update(q, k, v, g, beta, state0, None)
mx.eval(st_e)
print("eager stats: min", float(st_e.min()), "max", float(st_e.max()),
      "nan", int(mx.isnan(st_e).sum()))
print("eager vs ref maxdiff:", float(mx.abs(st_e - st_ref).max()))

out_r, st_r = mx.fast.gated_delta_update_raw(q, k, v, a, b, A_log, dt_bias, state0, None)
mx.eval(st_r)
print("raw stats: min", float(st_r.min()), "max", float(st_r.max()),
      "nan", int(mx.isnan(st_r).sum()))
print("raw vs ref maxdiff:", float(mx.abs(st_r - st_ref).max()))
print("raw vs eager maxdiff:", float(mx.abs(st_r - st_e).max()))
