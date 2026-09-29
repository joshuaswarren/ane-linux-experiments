import sys, time, statistics as st
import mlx.core as mx
import mlx.nn as nn
from mlx_lm.utils import load

model, tok = load(sys.argv[1])
seen = {}
for name, m in model.named_modules():
    if isinstance(m, nn.QuantizedLinear):
        k = (m.weight.shape, m.scales.shape)
        seen.setdefault(k, (name, m))
Ms = [16, 32, 64, 128, 256, 512]
REP = 16
for (wshape, sshape), (name, m) in seen.items():
    N = wshape[0]
    K = wshape[1] * 32 // m.bits
    wbytes = m.weight.nbytes + m.scales.nbytes + (m.biases.nbytes if "biases" in m else 0)
    row = {}
    for M in Ms:
        x = mx.random.normal((M, K)).astype(mx.bfloat16)
        mx.eval(x)
        for _ in range(2):
            mx.eval([m(x) for _ in range(REP)])
        ts = []
        for _ in range(7):
            t = time.perf_counter()
            mx.eval([m(x) for _ in range(REP)])
            ts.append((time.perf_counter() - t) / REP * 1e6)
        row[M] = round(st.median(ts), 1)
    gbs = 0
    print(f"{name} N={N} K={K} wMB={wbytes / 1e6:.2f} us_by_M={row} M64={row[64]}", flush=True)
