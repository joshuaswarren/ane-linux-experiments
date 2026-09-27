#!/usr/bin/env python3
"""MIL numpy graph with per-const alignment scan (P padding after each const)."""
import importlib.util
import numpy as np

conv_spec = importlib.util.spec_from_file_location("conv", "/var/tmp/m1max-embed-recovery/tools/hwxv2-to-anec.py")
conv = importlib.util.module_from_spec(conv_spec)
conv_spec.loader.exec_module(conv)
data = open("/var/tmp/levers8/qwen/hwx/prog_002/model.hwx", "rb").read()
img = conv.parse_hwx(data)
KERN = data[img.content_offset + img.kernel_offset: img.content_offset + img.kernel_offset + img.kernel_size]
z = np.load("/var/tmp/jw16-first-submit/ref4/sig0002.npz")
t7 = z["in__t7"].astype(np.float32).reshape(1, 2048)
t2 = z["in__t2"].astype(np.float32).reshape(16, 128)
t0 = z["in__t0"].astype(np.float32).reshape(16, 128)
t20 = z["in__t20"].astype(np.float32).reshape(6144, 3)
SHAPES = [(1, 128), (2048, 2048), (1, 2048), (6144, 2048), (6144, 2048), (2048, 6144),
          (6144, 4), (1, 2048), (6144, 2048), (16, 16), (16, 2048), (16,), (16,),
          (16, 2048), (2048, 2048)]
NAMES = ["t3_g", "t6_w", "t9_g", "t10_w", "t11_w", "t14_w", "t16", "t17_g",
         "t18_w", "t28", "t38_w", "t42", "t43", "t44_w", "t51_w"]


def extract(P):
    off = 0
    out = {}
    for nm, sh in zip(NAMES, SHAPES):
        n = int(np.prod(sh))
        a = np.frombuffer(KERN[off:off + n * 2], dtype=np.float16).astype(np.float32)
        if a.size != n:
            return None, None
        out[nm] = a.reshape(sh)
        off += n * 2 + P
        off = (off // 64) * 64 if P else off
    return out, off


def silu(x):
    return x / (1 + np.exp(-x))


C1, C2, C3, C4, C10 = 0.01131439208984375, 0.045257568359375, 0.0010003416538238525, 0.064117431640625, 10.0


def graph(W):
    t1 = silu(t0)
    t3_sn = np.maximum(np.sqrt((t2 ** 2).sum(1, keepdims=True)), C1)
    t4 = ((t2 / t3_sn) * W["t3_g"]) * t1
    with np.errstate(all="raise"):
        try:
            t6 = t4.reshape(1, 2048) @ W["t6_w"].T
        except Exception as e:
            print(f"P={P}: t6 matmul raised: {e}; t4 nan={int(np.isnan(t4).sum())} "
                  f"inf={int(np.isinf(t4).sum())}; W nan={int(np.isnan(W['t6_w']).sum())} "
                  f"inf={int(np.isinf(W['t6_w']).sum())}; t4 max={float(np.abs(t4).max())}", flush=True)
            return None
    t8 = t7 + t6
    if not np.isfinite(t8).all():
        print(f"P={P}: t8 non-finite: t6 nan={int(np.isnan(t6).sum())} inf={int(np.isinf(t6).sum())}", flush=True)
        return None
    t9_sn = np.maximum(np.sqrt((t8 ** 2).sum(1, keepdims=True)), C2)
    t9 = (t8 / t9_sn) * W["t9_g"]
    t13 = silu(t9 @ W["t11_w"].T) * (t9 @ W["t10_w"].T)
    t14 = t13 @ W["t14_w"].T
    t15 = t8 + t14
    if not np.isfinite(t15).all():
        return None
    t17_sn = np.maximum(np.sqrt((t15 ** 2).sum(1, keepdims=True)), C2)
    t17 = (t15 / t17_sn) * W["t17_g"]
    t18 = t17 @ W["t18_w"].T
    t19 = t18.reshape(6144, 1)
    t21 = np.concatenate([t20, t19], axis=1)
    t25 = silu((t21 * W["t16"]).sum(1, keepdims=True).reshape(1, 6144))
    t27 = t25[:, :2048].reshape(16, 128)
    t29 = W["t28"] @ t27
    t31 = (t29 / np.maximum(np.sqrt((t29 ** 2).sum(1, keepdims=True)), C3)) * C4
    t33 = t25[:, 2048:4096].reshape(16, 128)
    t34 = W["t28"] @ t33
    t35 = t34 / np.maximum(np.sqrt((t34 ** 2).sum(1, keepdims=True)), C3)
    t37 = t25[:, 4096:6144].reshape(16, 128)
    t38 = t17 @ W["t38_w"].T
    t41 = (1 / (1 + np.exp(-t38))).reshape(16, 1, 1)
    t44 = t17 @ W["t44_w"].T
    t46 = t44 + W["t43"].reshape(1, 16)
    t47m = np.minimum(t46, C10)
    t47 = np.log1p(np.exp(-np.abs(t47m))) + np.maximum(t47m, 0) + np.maximum(t46 - C10, 0)
    t49 = np.exp(t47 * W["t42"].reshape(1, 16))
    t50 = t49.reshape(16, 1, 1)
    t51 = t17 @ W["t51_w"].T
    t52 = t51.reshape(16, 128)
    t53 = t21[:, 1:4]
    return {"t15": t15, "t31": t31, "t35": t35, "t37": t37, "t41": t41,
            "t50": t50, "t52": t52, "t53": t53}


for P in (0, 16, 64, 256, 4096, 16384, 65536):
    W, consumed = extract(P)
    if W is None:
        print(f"P={P}: extraction overran", flush=True)
        continue
    outs = graph(W)
    if outs is None:
        print(f"P={P}: non-finite", flush=True)
        continue
    line = []
    tot = 0
    for nm, mine in outs.items():
        ref = z[f"out__{nm}"].reshape(-1)
        got = np.ascontiguousarray(mine).astype(np.float16).reshape(-1)
        n = min(got.size, ref.size)
        m = int(np.count_nonzero(got[:n].view(np.uint16) == ref[:n].view(np.uint16)))
        line.append(f"{nm}:{m}/{n}")
        tot += m
    print(f"P={P} (consumed {consumed}): " + " ".join(line), flush=True)
