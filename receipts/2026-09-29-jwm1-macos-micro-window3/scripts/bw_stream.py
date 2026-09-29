import json
import statistics as st
import time

import mlx.core as mx

out = {}


def timeit(fn, reps=9):
    fn()
    fn()
    ts = []
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t)
    return st.median(ts)


for mb in (64, 256, 512):
    n = mb * 1024 * 1024 // 4
    x = mx.random.normal((n,))
    mx.eval(x)
    t = timeit(lambda: mx.eval(mx.sum(x)))
    out[f"sum_{mb}MB_GBps"] = round(mb * 1.048576e6 / 1e9 / t, 1)
    t = timeit(lambda: mx.eval(x + 1.0))
    out[f"add1_{mb}MB_GBps(r+w)"] = round(2 * mb * 1.048576e6 / 1e9 / t, 1)
    del x
for n_out, k in ((248320, 2048), (6144, 2048), (2048, 6144)):
    w = mx.random.normal((n_out, k)).astype(mx.bfloat16)
    qw, qs, qb = mx.quantize(w, group_size=64, bits=4)
    x = mx.random.normal((1, k)).astype(mx.bfloat16)
    mx.eval(qw, qs, qb, x)
    nbytes = qw.nbytes + qs.nbytes + qb.nbytes
    reps = 16 if n_out < 100000 else 4

    def fn():
        mx.eval([mx.quantized_matmul(x, qw, qs, qb, transpose=True, group_size=64, bits=4) for _ in range(reps)])

    t = timeit(fn) / reps
    out[f"qmm_M1_N{n_out}_K{k}_us"] = round(t * 1e6, 1)
    out[f"qmm_M1_N{n_out}_K{k}_GBps"] = round(nbytes / 1e9 / t, 1)
print("BW", json.dumps(out))
