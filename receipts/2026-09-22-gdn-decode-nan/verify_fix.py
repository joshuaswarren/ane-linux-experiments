import mlx.core as mx, numpy as np
rng = np.random.default_rng(0)
H, D = 16, 128
B = 1

def ops_step(q, k, v, g, beta, state):
    decay = mx.expand_dims(g, (-1, -2))
    s = state * decay
    kv = mx.sum(s * mx.expand_dims(k, -2), -1)
    delta = (v - kv) * mx.expand_dims(beta, -1)
    s = s + mx.expand_dims(delta, -1) * mx.expand_dims(k, -2)
    o = mx.sum(s * mx.expand_dims(q, -2), -1)
    return o, s

def bf16_ulp_ok(a_f32, b_f32):
    # both bf16-quantized: pass if |diff| <= 1 ulp of bf16 at that magnitude
    a = np.array(a_f32, copy=False); b = np.array(b_f32, copy=False)
    au = a.view(np.uint32); bu = b.view(np.uint32)
    diff = np.abs(au.astype(np.int64) - bu.astype(np.int64))
    return bool((diff <= np.uint32(0x00800000)).all() or (diff <= 0x00800000).all())

h0 = mx.array(rng.standard_normal((1, H, D, D)) * 0.05, mx.float32)
q = mx.array(rng.standard_normal((1, 1, H, D)) * 0.5, mx.bfloat16)
k = mx.array(rng.standard_normal((1, 1, H, D)) * 0.5, mx.bfloat16)
v = mx.array(rng.standard_normal((1, 1, H, D)) * 0.5, mx.bfloat16)
g = mx.array(rng.standard_normal((1, 1, H)) * 0.1, mx.bfloat16)
beta = mx.array(np.full((1, 1, H), 0.5, np.float32), mx.bfloat16)

# 1) minimized reproducer cases: all finite
cases = [
    ("randn all", q, k, v, g, beta, h0),
    ("all zeros", mx.zeros_like(q), mx.zeros_like(k), mx.zeros_like(v),
     mx.zeros_like(g), mx.zeros_like(beta), mx.zeros((1, H, D, D), mx.float32)),
    ("g=-0.1", q, k, v, mx.full((1, 1, H), -0.1, mx.bfloat16), beta, h0),
    ("beta=0", q, k, v, g, mx.zeros_like(beta), h0),
    ("h0=0", q, k, v, g, beta, mx.zeros((1, H, D, D), mx.float32)),
]
for name, *args in cases:
    o, s = mx.fast.gated_delta_update(*args)
    mx.eval(o, s)
    print(f"finite {name}: out={bool(mx.isfinite(o).all())} state={bool(mx.isfinite(s).all())}")

# 2) strided T-slice (nonzero offset) case
q8 = mx.array(rng.standard_normal((1, 8, H, D)) * 0.5, mx.bfloat16)
k8 = mx.array(rng.standard_normal((1, 8, H, D)) * 0.5, mx.bfloat16)
v8 = mx.array(rng.standard_normal((1, 8, H, D)) * 0.5, mx.bfloat16)
g8 = mx.array(rng.standard_normal((1, 8, H)) * 0.1, mx.bfloat16)
b8 = mx.array(np.full((1, 8, H), 0.5, np.float32), mx.bfloat16)
q1, k1, v1, g1, b1 = q8[:, 3:4], k8[:, 3:4], v8[:, 3:4], g8[:, 3:4], b8[:, 3:4]
o1, s1 = mx.fast.gated_delta_update(q1, k1, v1, g1, b1, h0)
o1c, s1c = mx.fast.gated_delta_update(mx.contiguous(q1), mx.contiguous(k1),
                                      mx.contiguous(v1), mx.contiguous(g1),
                                      mx.contiguous(b1), h0)
mx.eval(o1, s1, o1c, s1c)
print("strided==contig:", bool(mx.array_equal(o1, o1c)), bool(mx.array_equal(s1, s1c)))

# 3) unit equivalence vs composed ops (T=1, same data)
o, s = mx.fast.gated_delta_update(q, k, v, g, beta, h0)
o2, s2 = ops_step(q, k, v, g, beta, h0)
mx.eval(o, s, o2, s2)
s_np = np.array(s, copy=False); s2_np = np.array(s2, copy=False)
s_maxabs = float(np.abs(s_np - s2_np).max()); s_denom = float(np.abs(s2_np).max())
o32 = np.array(o.astype(mx.float32), copy=False); o2_32 = np.array(o2.astype(mx.float32), copy=False)
print(f"state maxabs diff: {s_maxabs:.3e} (rel {s_maxabs/max(s_denom,1e-30):.3e})")
print(f"out maxabs diff:   {float(np.abs(o32-o2_32).max()):.3e}")
# bf16 ulp via f32 bit patterns: values equal to within 1 bf16 quantum
d32 = np.abs(o32 - o2_32)
mag = np.maximum(np.abs(o2_32), 1e-30)
ulp = np.maximum(2.0**(np.floor(np.log2(mag)) - 7), 2.0**-133)
print("out within 1 bf16 ulp:", bool((d32 <= ulp).all()), " max ulps:", float((d32/ulp).max()))
print("EXACT:", bool(mx.array_equal(o, o2)))
print("VERIFY-DONE")
