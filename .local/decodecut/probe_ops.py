import sys
import mlx.core as mx
from mlx_lm.models.gated_delta import compute_g

mode = sys.argv[1]
q = mx.random.normal((1, 1, 16, 128)).astype(mx.bfloat16)
k = mx.random.normal((1, 1, 16, 128)).astype(mx.bfloat16)
v = mx.random.normal((1, 1, 16, 128)).astype(mx.bfloat16)
state = mx.zeros((1, 16, 128, 128), mx.float32)
b = mx.random.normal((1, 1, 16)).astype(mx.bfloat16)
a = mx.random.normal((1, 1, 16)).astype(mx.bfloat16)
A_log = mx.ones(16)
dt_bias = mx.ones(16)
inv = 128 ** -0.5

if mode == "rms":
    out = (inv ** 2) * mx.fast.rms_norm(q, None, 1e-6)
    out2 = inv * mx.fast.rms_norm(k, None, 1e-6)
elif mode == "rmsw":
    wq = mx.full((128,), inv ** 2, mx.bfloat16)
    wk = mx.full((128,), inv, mx.bfloat16)
    out = mx.fast.rms_norm(q, wq, 1e-6)
    out2 = mx.fast.rms_norm(k, wk, 1e-6)
elif mode == "gates":
    beta = mx.sigmoid(b)
    g = compute_g(A_log, a, dt_bias)
    out = (beta, g)
elif mode == "gdu":
    beta = mx.sigmoid(b)
    g = compute_g(A_log, a, dt_bias)
    out, st = mx.fast.gated_delta_update(q, k, v, g, beta, state, None)
mx.eval(out)
if mode == "rms":
    mx.eval(out2)
