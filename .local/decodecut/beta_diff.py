import mlx.core as mx
import mlx.nn as nn
import numpy as np

mx.random.seed(0)
H = 16
q = mx.random.normal((1, 1, H, 128)).astype(mx.bfloat16)
k = mx.random.normal((1, 1, H, 128)).astype(mx.bfloat16)
v = mx.random.normal((1, 1, H, 128)).astype(mx.bfloat16)
state0 = mx.random.normal((1, H, 128, 128)).astype(mx.float32)
A_log = mx.random.normal((H,)).astype(mx.bfloat16)
dt_bias = mx.random.normal((H,)).astype(mx.float32)
a = mx.random.normal((1, 1, H)).astype(mx.bfloat16)
b = mx.random.normal((1, 1, H)).astype(mx.bfloat16)

def compute_g(A_log, a, dt_bias):
    return mx.exp(-mx.exp(A_log.astype(mx.float32)) * nn.softplus(a + dt_bias))

a2 = mx.full((1,1,H), -20.0, mx.bfloat16)
g2 = compute_g(A_log, a2, dt_bias).astype(mx.bfloat16)
out_r2, st_r2 = mx.fast.gated_delta_update_raw(q, k, v, a2, b, A_log, dt_bias, state0, None)
out_e2, st_e2 = mx.fast.gated_delta_update(q, k, v, g2, mx.sigmoid(b), state0, None)
mx.eval(st_r2); mx.eval(st_e2)
sr2, se2 = mx.array(st_r2), mx.array(st_e2)
d = mx.abs(sr2 - se2)
print("beta-only equal:", mx.array_equal(sr2, se2), "maxdiff:", float(d.max()), "relmean:", float((d/mx.abs(se2)).mean()))
# where differ
idx = np.argwhere(np.asarray(d) > 0)
print("n diff cells:", len(idx), "of", d.size)
print("first cells:", idx[:5].tolist())

# try shifting eager beta by +1 element (offset bug hypothesis)
bs = b.reshape(-1)
for shift in (-1, 1):
    bshift = mx.concatenate([bs[shift:], mx.zeros((abs(shift)), mx.bfloat16)]) if shift > 0 else mx.concatenate([mx.zeros((-shift), mx.bfloat16), bs[:shift]])
    _, st_s = mx.fast.gated_delta_update(q, k, v, g2, mx.sigmoid(bshift.reshape(1,1,H)), state0, None)
    mx.eval(st_s)
    print("shift", shift, "maxdiff:", float(mx.abs(mx.array(st_s) - sr2).max()))
