#!/usr/bin/env python3
"""Numpy execution of prog_002's MIL graph vs Apple's sig0002 outputs."""
import importlib.util
import numpy as np

conv_spec = importlib.util.spec_from_file_location("conv", "/var/tmp/m1max-embed-recovery/tools/hwxv2-to-anec.py")
conv = importlib.util.module_from_spec(conv_spec)
conv_spec.loader.exec_module(conv)
data = open("/var/tmp/levers8/qwen/hwx/prog_002/model.hwx", "rb").read()
img = conv.parse_hwx(data)
kern = data[img.content_offset + img.kernel_offset: img.content_offset + img.kernel_offset + img.kernel_size]
z = np.load("/var/tmp/jw16-first-submit/ref4/sig0002.npz")
t7 = z["in__t7"].astype(np.float32).reshape(1, 2048)
t2 = z["in__t2"].astype(np.float32).reshape(16, 128)
t0 = z["in__t0"].astype(np.float32).reshape(16, 128)
t20 = z["in__t20"].astype(np.float32).reshape(6144, 3)

off = 0


def take(n_el):
    global off
    a = np.frombuffer(kern[off:off + n_el * 2], dtype=np.float16).astype(np.float32)
    off += n_el * 2
    return a


def silu(x):
    return x / (1 + np.exp(-x))


C1 = 0.01131439208984375   # 0x1.72cp-7
C2 = 0.045257568359375     # 0x1.72cp-5
C3 = 0.0010003416538238525  # 0x1.064p-10
C4 = 0.064117431640625     # 0x1.6ap-4
C10 = 10.0                 # 0x1.4p+3

t3_g = take(128).reshape(1, 128)
t6_w = take(2048 * 2048).reshape(2048, 2048)
t9_g = take(2048).reshape(1, 2048)
t10_w = take(6144 * 2048).reshape(6144, 2048)
t11_w = take(6144 * 2048).reshape(6144, 2048)
t14_w = take(2048 * 6144).reshape(2048, 6144)
t16 = take(6144 * 4).reshape(6144, 4)
t17_g = take(2048).reshape(1, 2048)
t18_w = take(6144 * 2048).reshape(6144, 2048)
t28 = take(16 * 16).reshape(16, 16)
t38_w = take(16 * 2048).reshape(16, 2048)
t42 = take(16)
t43 = take(16)
t44_w = take(16 * 2048).reshape(16, 2048)
t51_w = take(2048 * 2048).reshape(2048, 2048)
print("consumed", off, "of", len(kern))

t1 = silu(t0)
t3_sn = np.maximum(np.sqrt((t2 ** 2).sum(1, keepdims=True)), C1)
t3 = (t2 / t3_sn) * t3_g
t4 = t3 * t1
t5 = t4.reshape(1, 2048)
t6 = t5 @ t6_w.T
t8 = t7 + t6
t9_sn = np.maximum(np.sqrt((t8 ** 2).sum(1, keepdims=True)), C2)
t9 = (t8 / t9_sn) * t9_g
t10 = t9 @ t10_w.T
t11 = t9 @ t11_w.T
t12 = silu(t11)
t13 = t12 * t10
t14 = t13 @ t14_w.T
t15 = t8 + t14
t17_sn = np.maximum(np.sqrt((t15 ** 2).sum(1, keepdims=True)), C2)
t17 = (t15 / t17_sn) * t17_g
t18 = t17 @ t18_w.T
t19 = t18.reshape(6144, 1)
t21 = np.concatenate([t20, t19], axis=1)
t23 = (t21 * t16).sum(axis=1, keepdims=True)
t25 = silu(t23.reshape(1, 6144))
t27 = t25[:, :2048].reshape(16, 128)
t29 = t28 @ t27
t30 = t29 / np.maximum(np.sqrt((t29 ** 2).sum(1, keepdims=True)), C3)
t31 = t30 * C4
t33 = t25[:, 2048:4096].reshape(16, 128)
t34 = t28 @ t33
t35 = t34 / np.maximum(np.sqrt((t34 ** 2).sum(1, keepdims=True)), C3)
t37 = t25[:, 4096:6144].reshape(16, 128)
t38 = t17 @ t38_w.T
t40 = 1 / (1 + np.exp(-t38))
t41 = t40.reshape(16, 1, 1)
t44 = t17 @ t44_w.T
t46 = t44 + t43.reshape(1, 16)
t47 = np.log1p(np.exp(-np.abs(np.minimum(t46, C10)))) + np.maximum(np.minimum(t46, C10), 0)
t47 = t47 + np.maximum(t46 - C10, 0)
t48 = t47 * t42.reshape(1, 16)
t49 = np.exp(t48)
t50 = t49.reshape(16, 1, 1)
t51 = t17 @ t51_w.T
t52 = t51.reshape(16, 128)
t53 = t21[:, 1:4]

zref = np.load("/var/tmp/jw16-first-submit/ref4/sig0002.npz")
pairs = [("t15", t15), ("t31", t31), ("t35", t35), ("t37", t37), ("t41", t41),
         ("t50", t50), ("t52", t52), ("t53", t53)]
for nm, mine in pairs:
    got = np.ascontiguousarray(mine).astype(np.float16).reshape(-1)
    ref = np.ascontiguousarray(zref[f"out__{nm}"]).astype(np.float16).reshape(-1)
    n = min(got.size, ref.size)
    m = int(np.count_nonzero(got[:n].view(np.uint16) == ref[:n].view(np.uint16)))
    mx = float(np.abs(got[:n].astype(np.float32) - ref[:n].astype(np.float32)).max())
    print(f"numpy-graph {nm}: {m}/{n} bitwise, maxabs={mx:.4g}", flush=True)
np.savez("/var/tmp/jw16-first-submit/numpy-graph-outs.npz",
         **{nm: np.ascontiguousarray(v).astype(np.float16) for nm, v in pairs})
