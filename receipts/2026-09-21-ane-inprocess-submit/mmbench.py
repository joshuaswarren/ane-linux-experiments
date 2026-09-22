import mlx.core as mx, numpy as np, time
mx.set_default_device(mx.gpu)
def bench(fn, n=20):
    fn(); mx.eval(mx.zeros(1)) if False else None
    ts=[]
    for _ in range(n):
        t=time.monotonic_ns(); out=fn(); mx.eval(out); ts.append(time.monotonic_ns()-t)
    ts.sort(); return ts[len(ts)//2]/1e6
x16 = mx.array(np.random.rand(8,375,64).astype(np.float16))
y16T = mx.array(np.random.rand(8,375,64).astype(np.float16))
yT = mx.swapaxes(y16T, -1, -2)
# runner's exact chain: fp32 upcast, matmul, fp16 downcast
ms = bench(lambda: (x16.astype(mx.float32) @ yT.astype(mx.float32)).astype(mx.float16))
print("fp32-chain [8,375,64]@[8,375,64]T:", round(ms,3), "ms  GFLOPS", round(2*8*375*375*64/(ms/1e3)/1e9,1))
ms2 = bench(lambda: mx.matmul(x16, yT))
print("fp16 matmul same shapes:", round(ms2,3), "ms  GFLOPS", round(2*8*375*375*64/(ms2/1e3)/1e9,1))
# bigger sanity: known-good shape
a = mx.random.normal((1024,1024)).astype(mx.float16)
b = mx.random.normal((1024,1024)).astype(mx.float16)
ms3 = bench(lambda: mx.matmul(a,b), n=10)
print("fp16 1024^3:", round(ms3,3), "ms  GFLOPS", round(2*1024**3/(ms3/1e3)/1e9,1))
