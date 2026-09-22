import mlx.core as mx, numpy as np
rng = np.random.default_rng(0)
H, D = 16, 128
def mk(a): return mx.array(a, mx.bfloat16)

def composed(q, k, v, g, beta, h0):
    # per-token GDN math in plain mx ops, f32
    qf = q.astype(mx.float32); kf = k.astype(mx.float32); vf = v.astype(mx.float32)
    g32 = g.astype(mx.float32); b32 = beta.astype(mx.float32)
    Sd = g32[..., None] * h0                                # [B,H,Dv,Dk]
    kv = b32[..., None] * mx.matmul(Sd, kf[..., 0, :, :][..., None])[..., 0]  # wrong shape; fix below
    return None

# do it per-head explicitly to avoid shape confusion
def composed2(q, k, v, g, beta, h0):
    qf = q.astype(mx.float32); kf = k.astype(mx.float32); vf = v.astype(mx.float32)
    g32 = g.astype(mx.float32); b32 = beta.astype(mx.float32)
    # q,k,v: [B,1,H,D] -> [B,H,1,D]; S: [B,H,Dv,Dk]
    qq = qf[:, 0]; kk = kf[:, 0]; vv = vf[:, 0]
    Sd = g32[:, 0][..., None, None] * h0
    kv = b32[:, 0][..., None] * (Sd @ kk[..., None])[..., 0]      # [B,H,Dv]
    delta = vv - kv
    S_new = Sd + delta[..., None] * kk[..., None, :]
    y = (S_new @ qq[..., None])[..., 0]
    return y.astype(mx.bfloat16), S_new

def run(q, k, v, g, beta, h0, tag):
    o, s = mx.fast.gated_delta_update(q, k, v, g, beta, h0)
    oc, sc = composed2(q, k, v, g, beta, h0)
    mx.eval(o, s, oc, sc)
    print(tag, "kernel state finite:", bool(mx.isfinite(s).all()),
          "| composed finite:", bool(mx.isfinite(sc).all()),
          "| match:", bool(mx.allclose(s, sc, rtol=1e-2, atol=1e-2)))

h0 = mx.array(rng.standard_normal((1, H, D, D)) * 0.05, mx.float32)
q = mk(rng.standard_normal((1, 1, H, D)) * 0.5)
k = mk(rng.standard_normal((1, 1, H, D)) * 0.5)
v = mk(rng.standard_normal((1, 1, H, D)) * 0.5)
beta = mk(np.full((1, 1, H), 0.5, np.float32))

run(q, k, v, mk(rng.standard_normal((1, 1, H)) * 0.1), beta, h0, "g=randn*0.1:")
run(q, k, v, mk(np.full((1, 1, H), -0.1, np.float32)), beta, h0, "g=-0.1    :")
run(q, k, v, mk(np.zeros((1, 1, H), np.float32)), beta, h0, "g=0       :")
print("DONE")
