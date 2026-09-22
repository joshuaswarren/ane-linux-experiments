import mlx.core as mx
import numpy as np

B,H,T,D = 1,8,29,256
dims = 64
base = 10000000.0
x = mx.random.normal((B,H,T,D)).astype(mx.bfloat16)
xt = x.transpose(0,2,1,3)  # (B,T,H,D)
fast = mx.fast.rope(xt, dims, traditional=False, base=base, scale=1.0, offset=0)
f32 = xt.astype(mx.float32)
half = dims//2
inv = mx.power(base, -mx.arange(0, half, dtype=mx.float32)/half)
freqs = mx.arange(0,T,dtype=mx.float32)[:,None]*inv[None,:]  # (T,32)
cos = mx.cos(freqs)[:,None,:]; sin = mx.sin(freqs)[:,None,:]
x1 = f32[...,:half]; x2 = f32[...,half:2*half]
comp = mx.concatenate([x1*cos - x2*sin, x1*sin + x2*cos, f32[...,dims:]], axis=-1)
d = np.abs(fast.astype(mx.float32).__array__() - comp.__array__())
print("transposed maxdiff:", np.nanmax(d), "nan fast:", int(np.isnan(fast.astype(mx.float32).__array__()).sum()))
fastc = mx.fast.rope(x, dims, traditional=False, base=base, scale=1.0, offset=0)
f32c = x.astype(mx.float32)  # (B,H,T,D): T axis=2
x1c = f32c[...,:half]; x2c = f32c[...,half:2*half]
compc = mx.concatenate([x1c*cos.transpose(1,0,2) - x2c*sin.transpose(1,0,2), x1c*sin.transpose(1,0,2) + x2c*cos.transpose(1,0,2), f32c[...,dims:]], axis=-1)
dc = np.abs(fastc.astype(mx.float32).__array__() - compc.__array__())
print("contig maxdiff:", np.nanmax(dc), "nan fastc:", int(np.isnan(fastc.astype(mx.float32).__array__()).sum()))
