import mlx.core as mx
import numpy as np

def check(B,H,T,D,dims,base,transposed,tag):
    x = mx.random.normal((B,H,T,D)).astype(mx.bfloat16)
    inp = x.transpose(0,2,1,3) if transposed else x
    fast = mx.fast.rope(inp, dims, traditional=False, base=base, scale=1.0, offset=0)
    f32 = inp.astype(mx.float32)
    half = dims//2
    inv = mx.power(base, -mx.arange(0, half, dtype=mx.float32)/half)
    freqs = mx.arange(0,T,dtype=mx.float32)[:,None]*inv[None,:]  # (T,half)
    cosT = mx.cos(freqs); sinT = mx.sin(freqs)                    # (T,half)
    x1 = f32[...,:half]; x2 = f32[...,half:2*half]
    if transposed:
        c = cosT[None,:,None,:]; s = sinT[None,:,None,:]   # (1,T,1,half)
    else:
        c = cosT[None,None,:,:]; s = sinT[None,None,:,:]   # (1,1,T,half)
    comp = mx.concatenate([x1*c - x2*s, x1*s + x2*c, f32[...,dims:]], axis=-1)
    d = np.abs(fast.astype(mx.float32).__array__() - comp.__array__())
    print(f"{tag}: maxdiff={np.nanmax(d):.4g} nanfast={int(np.isnan(fast.astype(mx.float32).__array__()).sum())}")

check(1,8,29,256,256,10000000.0,False,"fullrot contig  D=256 dims=256")
check(1,8,29,256,256,10000000.0,True, "fullrot transp  D=256 dims=256")
check(1,8,29,256,64,10000000.0,True, "part transp T=29 D=256 dims=64 (MODEL)")
check(1,8,29,256,64,10000000.0,False,"part contig  T=29 D=256 dims=64")
check(1,8,1,256,64,10000000.0,True, "part transp T=1  D=256 dims=64")
check(1,16,1,128,32,10000.0,True, "part transp T=1  D=128 dims=32 (earlier OK)")
check(1,16,29,128,32,10000000.0,True, "part transp T=29 D=128 dims=32")
check(1,16,29,64,32,10000000.0,True, "part transp T=29 D=64 dims=32")
