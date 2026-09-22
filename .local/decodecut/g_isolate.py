import mlx.core as mx
import mlx.nn as nn
import numpy as np

mx.random.seed(1)
H, D = 16, 128
state0 = mx.random.normal((1, H, D, D)).astype(mx.float32)
A_log = mx.random.normal((H,)).astype(mx.bfloat16)
dt_bias = mx.random.normal((H,)).astype(mx.float32)
a = mx.random.normal((1, 1, H)).astype(mx.bfloat16)
q = mx.random.normal((1, 1, H, D)).astype(mx.bfloat16)
k = mx.zeros((1, 1, H, D), mx.bfloat16)   # k=0 -> state_new = state0 * g exactly
v = mx.random.normal((1, 1, H, D)).astype(mx.bfloat16)
b = mx.zeros((1, 1, H), mx.bfloat16)      # beta = 0.5 exact

x = (a + dt_bias).astype(mx.float32)      # (1,1,H)
eA = mx.exp(A_log.astype(mx.float32))

g_eager = mx.exp(-eA * nn.softplus(a + dt_bias))
g_logaddexp = mx.exp(-eA * mx.logaddexp(0, x))
g_log1p = mx.exp(-eA * mx.log1p(mx.exp(x)))
print("softplus vs logaddexp bits equal:", mx.array_equal(nn.softplus(x), mx.logaddexp(0, x)))
print("g eager vs logaddexp bits equal :", mx.array_equal(g_eager, g_logaddexp))
print("g logaddexp vs log1p bits equal :", mx.array_equal(g_logaddexp, g_log1p))
d = mx.abs(g_logaddexp - g_log1p)
print("g logaddexp vs log1p maxdiff    :", float(d.max()))

out_r, st_r = mx.fast.gated_delta_update_raw(q, k, v, a, b, A_log, dt_bias, state0, None)
mx.eval(st_r)
# beta=0.5 exact; k=0 -> delta*k contributes 0 -> st = state0 * g
gk = st_r[0] / state0[0]                  # (H, D, D) implied kernel g per head
gk_h = gk.mean(axis=(1, 2))
ge_h = mx.array(g_eager)[0, 0]
print("kernel-implied g:", [f"{float(v):.6f}" for v in gk_h])
print("eager g         :", [f"{float(v):.6f}" for v in ge_h])
print("implied vs eager maxdiff:", float(mx.abs(gk_h - ge_h).max()))
print("implied vs log1p  maxdiff:", float(mx.abs(gk_h - mx.array(g_log1p)[0,0]).max()))
