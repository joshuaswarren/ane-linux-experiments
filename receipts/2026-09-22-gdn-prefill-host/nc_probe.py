import mlx.core as mx
import numpy as np

B, T, H, D = 1, 8, 16, 128
rng = np.random.default_rng(0)
def bf16(a): return mx.array(a, mx.bfloat16)

q = bf16(rng.standard_normal((B, T, H, D)) * 0.5)
k = bf16(rng.standard_normal((B, T, H, D)) * 0.5)
v = bf16(rng.standard_normal((B, T, H, D)) * 0.5)
g = bf16(rng.standard_normal((B, T, H)) * 0.1)
beta = mx.array(np.full((B, T, H), 0.5, np.float32), mx.bfloat16)
h0 = mx.array(rng.standard_normal((B, H, D, D)) * 0.05, mx.float32)

# non-contiguous T-slice (odd rows)
q_nc = q[:, ::2]; k_nc = k[:, ::2]; v_nc = v[:, ::2]; g_nc = g[:, ::2]; beta_nc = beta[:, ::2]
out_n, st_n = mx.fast.gated_delta_update(q_nc, k_nc, v_nc, g_nc, beta_nc, h0)
mx.eval(out_n, st_n)
print("noncontig T=4 state finite:", bool(mx.isfinite(st_n).all()), "out finite:", bool(mx.isfinite(out_n).all()))

# decode shape T=1 on a strided slice
q1 = q[:, 3:4]; k1 = k[:, 3:4]; v1 = v[:, 3:4]; g1 = g[:, 3:4]; b1 = beta[:, 3:4]
out1, st1 = mx.fast.gated_delta_update(q1, k1, v1, g1, b1, h0)
mx.eval(out1, st1)
print("strided T=1 state finite:", bool(mx.isfinite(st1).all()), "out finite:", bool(mx.isfinite(out1).all()))

# equivalence: strided T=1 result == contiguous single-token call on same data
qc = mx.contiguous(q1); kc = mx.contiguous(k1); vc = mx.contiguous(v1)
gc = mx.contiguous(g1); bc = mx.contiguous(b1)
out1c, st1c = mx.fast.gated_delta_update(qc, kc, vc, gc, bc, h0)
mx.eval(out1c, st1c)
print("strided==contig T=1:", bool(mx.array_equal(st1, st1c)), bool(mx.array_equal(out1, out1c)))
print("PROBE-DONE")

# isolate: fresh contiguous T=1 vs slice-derived contiguous T=1
qf = mx.contiguous(mx.array(np.ascontiguousarray(rng.standard_normal((1,1,16,128))*0.5), mx.bfloat16))
kf = mx.contiguous(mx.array(np.ascontiguousarray(rng.standard_normal((1,1,16,128))*0.5), mx.bfloat16))
vf = mx.contiguous(mx.array(np.ascontiguousarray(rng.standard_normal((1,1,16,128))*0.5), mx.bfloat16))
gf = mx.array(np.full((1,1,16), 0.1, np.float32), mx.bfloat16)
bf = mx.array(np.full((1,1,16), 0.5, np.float32), mx.bfloat16)
o_f, s_f = mx.fast.gated_delta_update(qf, kf, vf, gf, bf, h0)
mx.eval(o_f, s_f)
print("fresh T=1 finite:", bool(mx.isfinite(s_f).all()))
o_c2, s_c2 = mx.fast.gated_delta_update(qc, kc, vc, gc, bc, h0)
mx.eval(o_c2, s_c2)
print("slice-derived contig T=1 finite:", bool(mx.isfinite(s_c2).all()))
