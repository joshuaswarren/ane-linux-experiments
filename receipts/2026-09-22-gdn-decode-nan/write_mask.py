import mlx.core as mx, numpy as np
H, D = 16, 128
h0 = mx.zeros((1, H, D, D), mx.float32)
z = lambda *s: mx.zeros((1, 1) + s, mx.bfloat16)
o, s = mx.fast.gated_delta_update(z(H, D), z(H, D), z(H, D),
                                 mx.full((1,1,H), -0.1, mx.bfloat16),
                                 mx.full((1,1,H), 0.5, mx.bfloat16), h0)
mx.eval(o, s)
onp = np.array(o.astype(mx.float32), copy=False)
snp = np.array(s, copy=False)
print("out: total", onp.size, "finite", int(np.isfinite(onp).sum()), "nonzero", int((onp != 0).sum()))
print("state: total", snp.size, "finite", int(np.isfinite(snp).sum()), "nonzero", int((snp != 0).sum()))
fn = np.isfinite(onp).reshape(H, D)
print("out finite per head:", [int(r.sum()) for r in fn])
# finite positions
idx = np.argwhere(np.isfinite(onp.reshape(H, D)))
print("finite (head,row) sample:", idx[:20].tolist())
print("DONE")
