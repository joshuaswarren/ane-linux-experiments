import mlx.core as mx
import mlx.nn as nn

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

# raw path
out_r, st_r = mx.fast.gated_delta_update_raw(q, k, v, a, b, A_log, dt_bias, state0, None)
# eager gates path
beta = mx.sigmoid(b)
g = compute_g(A_log, a, dt_bias)
out_e, st_e = mx.fast.gated_delta_update(q, k, v, g, beta, state0, None)
mx.eval(st_r); mx.eval(st_e)

sr = mx.array(st_r); se = mx.array(st_e)
print("state equal:", mx.array_equal(sr, se), "maxdiff:", float(mx.abs(sr - se).max()))
print("g[0,:4]:", g[0,0,:4])
print("beta[0,:4]:", beta[0,0,:4])
print("out equal:", mx.array_equal(out_r, out_e), "maxdiff:", float(mx.abs(out_r.astype(mx.float32) - out_e.astype(mx.float32)).max()))

print("nan raw:", int(mx.isnan(sr).sum()), "nan eager:", int(mx.isnan(se).sum()))
print("min/max raw:", float(sr.min()), float(sr.max()))
print("min/max eager:", float(se.min()), float(se.max()))
# isolate beta: a=-20 => softplus ~0 => g = exp(0)=1 => state pure beta effect
a2 = mx.full((1,1,H), -20.0, mx.bfloat16)
g2 = compute_g(A_log, a2, dt_bias)  # ~1
out_r2, st_r2 = mx.fast.gated_delta_update_raw(q, k, v, a2, b, A_log, dt_bias, state0, None)
out_e2, st_e2 = mx.fast.gated_delta_update(q, k, v, g2.astype(mx.bfloat16), mx.sigmoid(b), state0, None)
mx.eval(st_r2); mx.eval(st_e2)
print("beta-only equal:", mx.array_equal(st_r2, st_e2))
# isolate g: b=0 => beta=0.5 exact
b0 = mx.zeros((1,1,H), mx.bfloat16)
out_r3, st_r3 = mx.fast.gated_delta_update_raw(q, k, v, a, b0, A_log, dt_bias, state0, None)
out_e3, st_e3 = mx.fast.gated_delta_update(q, k, v, g, mx.sigmoid(b0), state0, None)
mx.eval(st_r3); mx.eval(st_e3)
print("g-only equal:", mx.array_equal(st_r3, st_e3), "maxdiff:", float(mx.abs(mx.array(st_r3)-mx.array(st_e3)).max()))
