#!/usr/bin/env python3
"""Per-op cost of DEPENDENT decode-shaped ops in one eval (macOS Metal and Linux Honeykrisp, same script).

Each chain is n dependent ops (op i reads op i-1's output) in ONE mx.eval; per-op cost is the slope
between n=32 and n=160 (wall, median of 7), so fixed eval/submit/sync cost cancels. GEMV chains cycle
24 distinct random q4/g64 weights per shape (defeats the SLC like the 24-layer model does).
Output: one JSON object on stdout. usage: python3 chain_costs_decode.py [--quick]
"""
import json
import platform
import statistics
import sys
import time

import mlx.core as mx

QUICK = "--quick" in sys.argv
REPS = 3 if QUICK else 7
N_LO, N_HI = 32, 160
bf16 = mx.bfloat16
mx.random.seed(0)


def qweight(n_out, k, count=24):
    ws = []
    for _ in range(count):
        w = (mx.random.normal((n_out, k)) * 0.02).astype(bf16)
        wq, s, b = mx.quantize(w, group_size=64, bits=4)
        ws.append((wq, s, b))
    mx.eval(ws)
    return ws


def qmm(x, wsb):
    wq, s, b = wsb
    return mx.quantized_matmul(x, wq, s, b, transpose=True, group_size=64, bits=4)


SUBMIT = {}


def timed(build, n):
    ts, rs = [], []
    for _ in range(REPS):
        out = build(n)
        mx.synchronize()
        t0 = time.perf_counter()
        mx.async_eval(out)
        t1 = time.perf_counter()
        mx.eval(out)
        mx.synchronize()
        ts.append(time.perf_counter() - t0)
        rs.append(t1 - t0)
    return statistics.median(ts), statistics.median(rs)


def slope_us(build, per=1):
    timed(build, N_LO)  # warm
    (lo, rlo), (hi, rhi) = timed(build, N_LO), timed(build, N_HI)
    SUBMIT[build.__name__] = round((rhi - rlo) / (N_HI - N_LO) / per * 1e6, 2)
    return round((hi - lo) / (N_HI - N_LO) / per * 1e6, 2), round(lo * 1e3, 3), round(hi * 1e3, 3)


x2048 = mx.random.normal((1, 1, 2048)).astype(bf16)
w2048 = (mx.random.normal((2048,)) * 0.1 + 1.0).astype(bf16)
c2048 = mx.random.normal((1, 1, 2048)).astype(bf16)
x6144 = mx.random.normal((1, 1, 6144)).astype(bf16)
mx.eval(x2048, w2048, c2048, x6144)


def ch_add(n):
    x = x2048
    for _ in range(n):
        x = x + c2048
    return x


def ch_norm(n):
    x = x2048
    for _ in range(n):
        x = mx.fast.rms_norm(x, w2048, 1e-6)
    return x


def ch_silu(n):
    x = x6144
    for _ in range(n):
        x = x * mx.sigmoid(x)
    return x


res = {
    "platform": platform.platform(),
    "machine": platform.machine(),
    "mlx": getattr(mx, "__version__", "?"),
    "device": str(mx.default_device()),
    "n_lo": N_LO,
    "n_hi": N_HI,
    "reps": REPS,
    "us_per_op": {},
}
R = res["us_per_op"]
R["add_2048"] = slope_us(ch_add)
R["rms_norm_2048"] = slope_us(ch_norm)
R["silu_mul_6144"] = slope_us(ch_silu)

shapes = {
    "out_2048x2048": (2048, 2048),
    "qkv_6144x2048": (6144, 2048),
    "gate_6144x2048": (6144, 2048),
}
W = {k: qweight(*v) for k, v in shapes.items()}
Wdown = qweight(2048, 6144)
Wz = qweight(2048, 2048)


def ch_gemv_square(n):
    x = x2048
    ws = W["out_2048x2048"]
    for i in range(n):
        x = qmm(x, ws[i % 24])
    return x


def ch_gemv_up(n):
    x = x2048
    ws = W["qkv_6144x2048"]
    for i in range(n):
        x = qmm(x, ws[i % 24])[..., :2048]
    return x


def ch_up_down(n):
    x = x2048
    for i in range(n):
        y = qmm(x, W["gate_6144x2048"][i % 24])
        x = qmm(y, Wdown[i % 24])
    return x


def ch_norm_gemv(n):
    x = x2048
    ws = W["out_2048x2048"]
    for i in range(n):
        x = qmm(mx.fast.rms_norm(x, w2048, 1e-6), ws[i % 24])
    return x


def ch_qkvz_group(n):
    # GDN in-proj shape: four GEMVs of one x (qkv 6144, z 2048), next x = qkv slice
    x = x2048
    for i in range(n):
        a = qmm(x, W["qkv_6144x2048"][i % 24])
        z = qmm(x, Wz[i % 24])
        x = a[..., :2048] + z
    return x


R["gemv_2048x2048"] = slope_us(ch_gemv_square)
R["gemv_6144x2048"] = slope_us(ch_gemv_up)
R["gemv_up6144_then_down2048x6144_pair"] = slope_us(ch_up_down)
R["rms_norm_then_gemv_2048x2048_pair"] = slope_us(ch_norm_gemv)
R["qkv6144_z2048_add_triple"] = slope_us(ch_qkvz_group)
mb = lambda n, k: (n * k / 2 + n * (k // 64) * 4) / 1e6
res["weight_MB"] = {"2048x2048": mb(2048, 2048), "6144x2048": mb(6144, 2048), "2048x6144": mb(2048, 6144)}
res["gbps_from_slope"] = {
    "gemv_2048x2048": round(mb(2048, 2048) * 1e3 / R["gemv_2048x2048"][0], 1),
    "gemv_6144x2048": round(mb(6144, 2048) * 1e3 / R["gemv_6144x2048"][0], 1),
    "up_down_pair": round(2 * mb(6144, 2048) * 1e3 / R["gemv_up6144_then_down2048x6144_pair"][0], 1),
}
res["async_eval_return_us_per_op"] = SUBMIT
print(json.dumps(res))
