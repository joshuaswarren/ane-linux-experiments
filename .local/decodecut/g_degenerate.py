import mlx.core as mx
import mlx.nn as nn
import numpy as np

mx.random.seed(2)
H, D = 16, 128
state0 = mx.ones((1, H, D, D), mx.float32)   # ones -> gk = st exactly
q = mx.ones((1, 1, H, D), mx.bfloat16)
k = mx.zeros((1, 1, H, D), mx.bfloat16)
v = mx.ones((1, 1, H, D), mx.bfloat16)
b = mx.zeros((1, 1, H), mx.bfloat16)
A_log = mx.random.normal((H,)).astype(mx.bfloat16)

for tag, a_vals, dt_vals in [
    ("a=0,dt=0", mx.zeros((1,1,H), mx.bfloat16), mx.zeros((H,), mx.float32)),
    ("a=1,dt=0", mx.ones((1,1,H), mx.bfloat16), mx.zeros((H,), mx.float32)),
    ("a=rand,dt=0", mx.random.normal((1,1,H)).astype(mx.bfloat16), mx.zeros((H,), mx.float32)),
    ("a=0,dt=rand", mx.zeros((1,1,H), mx.bfloat16), mx.random.normal((H,), mx.float32)),
]:
    out_r, st_r = mx.fast.gated_delta_update_raw(q, k, v, a_vals, b, A_log, dt_vals, state0, None)
    mx.eval(st_r)
    gk = np.array(mx.array(st_r)[0, :, 0, 0])
    x = (a_vals + dt_vals).astype(mx.float32)
    eA = mx.exp(A_log.astype(mx.float32))
    ge = np.array(mx.exp(-eA * nn.softplus(x)))
    d = mx.abs(gk - ge)
    print(f"{tag}: maxdiff {np.abs(gk-ge).max():.3e}  g[0] kernel {gk.ravel()[0]:.8f} eager {ge.ravel()[0]:.8f}")
