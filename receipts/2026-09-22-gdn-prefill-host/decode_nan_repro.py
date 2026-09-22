import mlx.core as mx
import numpy as np

rng = np.random.default_rng(0)
H, D = 16, 128

def ops_step(q, k, v, g, beta, state):
    """T=1 ops-path math, mirroring the composed fallback in fast.cpp."""
    decay = mx.expand_dims(g, (-1, -2))         # [B,H,1,1] scalar decay
    s = state * decay
    kv = mx.sum(s * mx.expand_dims(k, -2), -1)  # [B,H,Dv]
    delta = (v - kv) * mx.expand_dims(beta, -1)
    s = s + mx.expand_dims(delta, -1) * mx.expand_dims(k, -2)
    o = mx.sum(s * mx.expand_dims(q, -2), -1)
    return o, s

def fin(a):
    return bool(mx.isfinite(a).all())

def case(name, q, k, v, g, beta, h0):
    o1, s1 = mx.fast.gated_delta_update(q, k, v, g, beta, h0)
    mx.eval(o1, s1)
    o2, s2 = ops_step(q, k, v, g, beta, h0)
    mx.eval(o2, s2)
    print(f"{name}: fused_out={fin(o1)} fused_state={fin(s1)} ops_out={fin(o2)} ops_state={fin(s2)}")

h0 = mx.array(rng.standard_normal((1, H, D, D)) * 0.05, mx.float32)
q = mx.array(rng.standard_normal((1, 1, H, D)) * 0.5, mx.bfloat16)
k = mx.array(rng.standard_normal((1, 1, H, D)) * 0.5, mx.bfloat16)
v = mx.array(rng.standard_normal((1, 1, H, D)) * 0.5, mx.bfloat16)

case("randn g (mixed sign)", q, k, v, mx.array(rng.standard_normal((1, 1, H)) * 0.1, mx.bfloat16),
     mx.array(np.full((1, 1, H), 0.5), mx.bfloat16), h0)

case("g = -0.1 (valid decay)", q, k, v, mx.full((1, 1, H), -0.1, mx.bfloat16),
     mx.array(np.full((1, 1, H), 0.5), mx.bfloat16), h0)

case("g = +0.1 (decay > 1)", q, k, v, mx.full((1, 1, H), 0.1, mx.bfloat16),
     mx.array(np.full((1, 1, H), 0.5), mx.bfloat16), h0)

case("g = 0", q, k, v, mx.zeros((1, 1, H), mx.bfloat16),
     mx.array(np.full((1, 1, H), 0.5), mx.bfloat16), h0)

case("randn g, h0 = 0", q, k, v, mx.array(rng.standard_normal((1, 1, H)) * 0.1, mx.bfloat16),
     mx.array(np.full((1, 1, H), 0.5), mx.bfloat16), mx.zeros((1, H, D, D), mx.float32))

# smallest single-head single-step reproducer check: which tensor drives it?
g_r = mx.array(rng.standard_normal((1, 1, H)) * 0.1, mx.bfloat16)
beta = mx.array(np.full((1, 1, H), 0.5), mx.bfloat16)
case("zeros q,k,v; randn g", mx.zeros((1, 1, H, D), mx.bfloat16), mx.zeros((1, 1, H, D), mx.bfloat16),
     mx.zeros((1, 1, H, D), mx.bfloat16), g_r, beta, h0)
case("randn all; beta = 0", q, k, v, g_r, mx.zeros((1, 1, H), mx.bfloat16), h0)
print("REPRO-DONE")

# mask hypothesis: in-model always passes a mask; probe so far didn't.
mask = mx.ones((1, 1), mx.bool_)
o3, s3 = mx.fast.gated_delta_update(q, k, v, g_r, beta, h0, mask)
mx.eval(o3, s3)
o4, s4 = mx.fast.gated_delta_update(q, k, v, mx.full((1,1,H), -0.1, mx.bfloat16), beta, h0, mask)
mx.eval(o4, s4)
print("with mask [1,1]: randn g:", fin(s3), "valid g:", fin(s4))
maskH = mx.ones((1, 1, H), mx.bool_)
o5, s5 = mx.fast.gated_delta_update(q, k, v, g_r, beta, h0, maskH)
mx.eval(o5, s5)
print("with mask [1,1,H]:", fin(s5))
print("REPRO2-DONE")
