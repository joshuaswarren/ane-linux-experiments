#!/usr/bin/env python3
"""Bit-exactness microprobe for the fused RMSNorm epilogue primitives.

Compares, on-device on the GPU at decode shapes:
  mode 0: mx.fast.rms_norm_gated(x, z, w, eps) vs composed
          rms_norm -> CastF32(z) -> siluF32 -> CastF32(y) -> mulF32 -> CastBF16
  mode 1: mx.fast.rms_norm_scaled(x, None, scale, eps) vs composed
          rms_norm(x, None, eps) * scale
Prints mismatch counts and worst ULP deltas per shape. CPU reference included
for the composed path so the probe also flags composed-vs-composed GPU noise.
"""
import mlx.core as mx
import numpy as np

def composed_gated(x, z, w, eps):
    y = mx.fast.rms_norm(x, w, eps)
    g = mx.sigmoid(z.astype(mx.float32))
    g = (z.astype(mx.float32) * g)
    xf = y.astype(mx.float32)
    return (g * xf).astype(x.dtype)

def composed_scaled(x, scale, eps):
    return scale * mx.fast.rms_norm(x, None, eps)

mx.set_default_device(mx.gpu)
rng = np.random.default_rng(7)
shapes = [
    (1, 2048),                    # gated norm site: out [B,1,2048]
    (1, 16, 128),                 # gated norm site as [B,H,D]? actual: norm over last dim 128 -> x [1,16,128]... norm axis is last
    (1, 2048),                    # q/k sites: q [1,16,128]? real decode shapes below
    (1, 16, 128),
    (1, 32, 128),
]
eps = 1e-6
print("== mode 0: rms_norm_gated vs composed ==")
# real site: normed GDN out [1,1,16,128] bf16, gate z [1,1,16,128] bf16, weight [128] bf16
x = mx.array(rng.standard_normal((1, 1, 16, 128)).astype(np.float32)).astype(mx.bfloat16)
z = mx.array(rng.standard_normal((1, 1, 16, 128)).astype(np.float32)).astype(mx.bfloat16)
w = (mx.array(rng.standard_normal(128).astype(np.float32)) * 0.1 + 1.0).astype(mx.bfloat16)
fused = mx.fast.rms_norm_gated(x, z, w, eps)
comp = composed_gated(x, z, w, eps)
mx.eval(fused, comp)
f = np.array(fused.astype(mx.float32)); c = np.array(comp.astype(mx.float32))
mis = (f != c).sum()
print(f"shape x{tuple(x.shape)} z{tuple(z.shape)}: mismatched {mis}/{f.size}")
if mis:
    idx = np.argwhere(f != c)[:8]
    for i in idx:
        t = tuple(int(v) for v in i)
        print(f"  {t}: fused={f[t]} composed={c[t]}")
print("== mode 0 extremes: saturated sigmoid / outlier magnitudes ==")
for seed in (11, 12):
    r2 = np.random.default_rng(seed)
    z2 = mx.array(np.clip(r2.standard_normal((1, 1, 16, 128)) * 8.0, -40, 40).astype(np.float32)).astype(mx.bfloat16)
    x2 = mx.array((r2.standard_normal((1, 1, 16, 128)) * 3.0).astype(np.float32)).astype(mx.bfloat16)
    fu = mx.fast.rms_norm_gated(x2, z2, w, eps)
    cp = composed_gated(x2, z2, w, eps)
    mx.eval(fu, cp)
    fa = np.array(fu.astype(mx.float32)); ca = np.array(cp.astype(mx.float32))
    m2 = (fa != ca).sum()
    print(f"seed {seed}: mismatched {m2}/{fa.size}")
    if m2:
        idx = np.argwhere(fa != ca)[:8]
        for i in idx:
            t = tuple(int(v) for v in i)
            print(f"  {t}: fused={fa[t]} composed={ca[t]}")

print("== mode 1: rms_norm_scaled(weight=None) vs composed ==")
for shape in [(1, 16, 128), (1, 16, 128), (4, 16, 128)]:
    q = mx.array(rng.standard_normal(shape).astype(np.float32)).astype(mx.bfloat16)
    scale = (2 ** -0.5) ** 2  # inv_scale**2 for Dk=128... inv_scale = Dk**-0.5 = 0.088388; inv_scale**2 = 0.0078125
    for s in [scale, 0.08838834764831845]:
        fused = mx.fast.rms_norm_scaled(q, None, s, eps)
        comp = composed_scaled(q, s, eps)
        mx.eval(fused, comp)
        f = np.array(fused.astype(mx.float32)); c = np.array(comp.astype(mx.float32))
        mis = (f != c).sum()
        print(f"shape {shape} scale={s:.6f}: mismatched {mis}/{f.size}")
        if mis:
            idx = np.argwhere(f != c)[:5]
            for i in idx:
                t = tuple(int(v) for v in i)
                print(f"  {t}: fused={f[t]} composed={c[t]} bits={f[t].view(np.uint16) if False else ''}")
print("done")
