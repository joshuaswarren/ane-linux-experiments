import mlx.core as mx
import numpy as np

B,L,H,D = 1,1,16,128
dims = 32
x = mx.random.normal((B,L,H,D)).astype(mx.bfloat16)
off = 3  # python int offset, like cache.offset
xt = x.transpose(0,2,1,3)  # (B,H,L,D) like the model
fast = mx.fast.rope(xt, dims, traditional=False, base=100000.0, scale=1.0, offset=off)
print("fast shape:", fast.shape)

half = dims//2
inv = mx.power(100000.0, -mx.arange(0, half, dtype=mx.float32)/half)
freqs = mx.array([3.0])[:,None]*inv[None,:]
cos = mx.cos(freqs)[0]; sin = mx.sin(freqs)[0]
f32 = xt.astype(mx.float32)
x1 = f32[...,:half]; x2 = f32[...,half:2*half]
comp = mx.concatenate([x1*cos - x2*sin, x1*sin + x2*cos, f32[...,dims:]], axis=-1)
d = np.abs(fast.astype(mx.float32).__array__() - comp.__array__())[0,0,0]
print("per-elem diff (first 20):", np.round(d[:20],4).tolist())
print("maxdiff:", float(d.max()), "at", int(d.argmax()))
print("tail ok:", bool(mx.array_equal(fast[0,0,0,dims:].astype(mx.float32), f32[0,0,0,dims:])))
# contiguous control
fastc = mx.fast.rope(x, dims, traditional=False, base=100000.0, scale=1.0, offset=off)
f32c = x.astype(mx.float32)
x1c = f32c[...,:half]; x2c = f32c[...,half:2*half]
compc = mx.concatenate([x1c*cos - x2c*sin, x1c*sin + x2c*cos, f32c[...,dims:]], axis=-1)
dc = np.abs(fastc.astype(mx.float32).__array__() - compc.__array__())
print("contig maxdiff:", float(dc.max()))
