#!/usr/bin/env python3
"""chain_costs_decode2.py — per-op cost of DEPENDENT decode-shaped ops, extended class coverage.

Extension of chain_costs_decode.py (Jw16DecodeGap w2 receipts; same slope method: n dependent
ops in ONE mx.eval, per-op cost = slope between n=32 and n=160, wall, median of 7). New chains
use the EXACT ops the deployed Qwen3.8-2B decode graph uses (mlx_lm 0.31.3 model helpers where a
wrapper picks the kernel), so each platform's installed kernels serve them:

  rms_norm_scaled q/k (FastNormGated), rms_norm_gated (FastNormGatedOnly),
  gdn_conv_update (GdnConvDecode, fused-qknorm form when available),
  gated_delta_update (GatedDeltaDecode, mlx_lm wrapper -> update_raw/update/kernel),
  rope+qknorm pair (FastRopeNorm class), sdpa decode hd256 (SdpaDecodeNative),
  greedy lm_head q4 248320x2048 (QmmVecGreedy / Metal qmm word),
  outgate qmm+sigmoid (QmmVecQ4MultiOutgate), tail: lse chain + embedding-take chain.

Usage: python3 chain_costs_decode2.py [--quick]
Output: one JSON object on stdout. Never mutates model/volume state; allocates its own weights.
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

NOTES = {}

# Model dims (Qwen3.8-2B, config 0867d98b)
HID = 2048
INTER = 6144
NKV_H = 16
HKD = 128
KEY_DIM = NKV_H * HKD  # 2048
CONV_DIM = KEY_DIM * 2 + KEY_DIM  # 6144
CONV_K = 4
NQ_H = 8
HD = 256
NKV2 = 2
VOCAB = 248320


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


x2048 = mx.random.normal((1, 1, HID)).astype(bf16)
w2048 = (mx.random.normal((HID,)) * 0.1 + 1.0).astype(bf16)
c2048 = mx.random.normal((1, 1, HID)).astype(bf16)
x6144 = mx.random.normal((1, 1, INTER)).astype(bf16)
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
    "notes": NOTES,
}
R = res["us_per_op"] = {}
R["add_2048"] = slope_us(ch_add)
R["rms_norm_2048"] = slope_us(ch_norm)
R["silu_mul_6144"] = slope_us(ch_silu)

shapes = {
    "out_2048x2048": (HID, HID),
    "qkv_6144x2048": (INTER, HID),
    "gate_6144x2048": (INTER, HID),
}
W = {k: qweight(*v) for k, v in shapes.items()}
Wdown = qweight(HID, INTER)
Wz = qweight(HID, HID)
Wlm = qweight(VOCAB, HID, count=3)


def ch_gemv_square(n):
    x = x2048
    ws = W["out_2048x2048"]
    for i in range(n):
        x = qmm(x, ws[i % len(ws)])
    return x


def ch_gemv_up(n):
    x = x2048
    ws = W["qkv_6144x2048"]
    for i in range(n):
        x = qmm(x, ws[i % len(ws)])[:, :, :HID]
    return x


def ch_up_down(n):
    x = x2048
    for i in range(n):
        x = qmm(x, W["gate_6144x2048"][i % len(W["gate_6144x2048"])])
        x = qmm(x, Wdown[i % len(Wdown)])
    return x


def ch_norm_gemv(n):
    x = x2048
    for i in range(n):
        x = mx.fast.rms_norm(x, w2048, 1e-6)
        x = qmm(x, W["out_2048x2048"][i % len(W["out_2048x2048"])])
    return x


def ch_qkvz_group(n):
    x = x2048
    for i in range(n):
        x = qmm(x, W["qkv_6144x2048"][i % len(W["qkv_6144x2048"])])[:, :, :HID]
        x = qmm(x, Wz[i % len(Wz)])
        x = x + c2048
    return x


R["gemv_2048x2048"] = slope_us(ch_gemv_square)
R["gemv_6144x2048"] = slope_us(ch_gemv_up)
R["gemv_up6144_then_down2048x6144_pair"] = slope_us(ch_up_down)
R["rms_norm_then_gemv_2048x2048_pair"] = slope_us(ch_norm_gemv)
R["qkv6144_z2048_add_triple"] = slope_us(ch_qkvz_group)

# ---------- GDN trio + gated norms (real decode shapes, ops as the model calls them) ----------
qhd = mx.random.normal((1, 1, NKV_H, HKD)).astype(bf16)
yhd = mx.random.normal((1, 1, NKV_H, HKD)).astype(bf16)
ghd = mx.random.normal((1, 1, NKV_H, HKD)).astype(bf16)
w128 = mx.random.normal((HKD,)).astype(bf16)
qkv = mx.random.normal((1, 1, CONV_DIM)).astype(bf16)
conv_w = mx.random.normal((CONV_DIM, CONV_K, 1)).astype(bf16)  # [C, K, 1] per gdn_conv_update docstring
conv_st = mx.zeros((1, CONV_K - 1, CONV_DIM), dtype=bf16)
q_gdn = mx.random.normal((1, 1, NKV_H, HKD)).astype(bf16)
k_gdn = mx.random.normal((1, 1, NKV_H, HKD)).astype(bf16)
v_gdn = mx.random.normal((1, 1, NKV_H, HKD)).astype(bf16)
a_gdn = mx.random.normal((1, 1, NKV_H)).astype(bf16)
b_gdn = mx.random.normal((1, 1, NKV_H)).astype(bf16)
st_gdn = mx.zeros((1, NKV_H, HKD, HKD), dtype=mx.float32)
qx = mx.random.normal((1, 1, NQ_H, HD)).astype(bf16)  # (B,S,N,D) for rope
qx_sdpa = mx.random.normal((1, NQ_H, 1, HD)).astype(bf16)  # [B,N,T,D] for sdpa
kc = mx.random.normal((1, NKV2, 512, HD)).astype(bf16)
vc = mx.random.normal((1, NKV2, 512, HD)).astype(bf16)
emb_words = Wlm[0][0]
ids = mx.array([[12345]], dtype=mx.int32)
A_LOG = mx.zeros((NKV_H,))
DT_BIAS = mx.ones((NKV_H,))
mx.eval(qhd, yhd, ghd, w128, qkv, conv_w, conv_st, q_gdn, k_gdn, v_gdn,
        a_gdn, b_gdn, st_gdn, qx, qx_sdpa, kc, vc, emb_words, ids, A_LOG, DT_BIAS)

if hasattr(mx.fast, "rms_norm_scaled"):
    def ch_rms_scaled(n):
        q = qhd
        for _ in range(n):
            q = mx.fast.rms_norm_scaled(q, None, (HKD ** -0.5) ** 2, 1e-6)
        return q
    R["rms_norm_scaled_16x128"] = slope_us(ch_rms_scaled)
else:
    NOTES["rms_norm_scaled"] = "absent"

if hasattr(mx.fast, "rms_norm_gated"):
    def ch_norm_gated(n):
        y = yhd
        for _ in range(n):
            y = mx.fast.rms_norm_gated(y, ghd, w128, 1e-6)
        return y
    R["rms_norm_gated_16x128"] = slope_us(ch_norm_gated)
else:
    NOTES["rms_norm_gated"] = "absent"

if hasattr(mx.fast, "gdn_conv_update"):
    FUSED_ARGS = {}
    try:
        o = mx.fast.gdn_conv_update(
            conv_st, qkv, conv_w, activate=True,
            qk_key_dim=KEY_DIM, qk_scale_q=(HKD ** -0.5) ** 2,
            qk_scale_k=HKD ** -0.5, qk_eps=1e-6,
        )
        mx.eval(o)
        FUSED_ARGS = dict(
            qk_key_dim=KEY_DIM, qk_scale_q=(HKD ** -0.5) ** 2,
            qk_scale_k=HKD ** -0.5, qk_eps=1e-6,
        )
        NOTES["gdn_conv_update"] = "fused_qknorm"
    except Exception as e:  # stock signature
        o = mx.fast.gdn_conv_update(conv_st, qkv, conv_w, activate=True)
        mx.eval(o)
        NOTES["gdn_conv_update"] = "plain (%s)" % type(e).__name__

    def ch_conv(n):
        st = conv_st
        out = None
        for _ in range(n):
            out, st = mx.fast.gdn_conv_update(st, qkv, conv_w, activate=True, **FUSED_ARGS)
        return out
    R["gdn_conv_decode_6144"] = slope_us(ch_conv)
else:
    NOTES["gdn_conv_update"] = "absent"

# Gated delta decode via the mlx_lm wrapper (picks update_raw / update / metal_kernel).
NOTES["gdu_raw"] = hasattr(mx.fast, "gated_delta_update_raw")
NOTES["gdu_upd"] = hasattr(mx.fast, "gated_delta_update")
try:
    from mlx_lm.models.gated_delta import gated_delta_update as gdu

    def ch_gdn_delta(n):
        st = st_gdn
        out = None
        for _ in range(n):
            out, st = gdu(q_gdn, k_gdn, v_gdn, a_gdn, b_gdn,
                          A_LOG, DT_BIAS, st, None, use_kernel=True)
        return out
    out0 = ch_gdn_delta(2)
    mx.eval(out0)
    R["gated_delta_decode_16x128x128"] = slope_us(ch_gdn_delta)
except Exception as e:
    NOTES["gated_delta_update"] = "failed: %r" % (e,)


def ch_rope_norm(n):
    q = qx
    pos = mx.array([0], dtype=mx.int32)
    for _ in range(n):
        try:
            q = mx.fast.rope(q, HD, traditional=False, base=100000.0, scale=1.0,
                             offset=pos)
        except TypeError:
            q = mx.fast.rope(q, HD, traditional=False, base=100000.0, scale=1.0,
                             offset_or_positions=pos)
        try:
            q = mx.fast.rms_norm_scaled(q, None, HD ** -0.5, 1e-6)
        except AttributeError:
            q = (HD ** -0.5) * mx.fast.rms_norm(q, None, 1e-6)
    return q


try:
    out0 = ch_rope_norm(2)
    mx.eval(out0)
    R["rope_then_qknorm_8x256"] = slope_us(ch_rope_norm)
except Exception as e:
    NOTES["rope_norm"] = "failed: %r" % (e,)


def ch_sdpa(n):
    q = qx_sdpa
    for _ in range(n):
        q = mx.fast.scaled_dot_product_attention(q, kc, vc, scale=HD ** -0.5, mask=None)
    return q


try:
    out0 = ch_sdpa(2)
    mx.eval(out0)
    R["sdpa_decode_8x256_kv512"] = slope_us(ch_sdpa)
except Exception as e:
    NOTES["sdpa"] = "failed: %r" % (e,)


def ch_outgate(n):
    x = x2048
    for i in range(n):
        x = qmm(x, Wz[i % len(Wz)])
        x = x * mx.sigmoid(x)
    return x


R["outgate_qmm_sigmoid_2048"] = slope_us(ch_outgate)


def ch_lm_head(n):
    x = x2048
    for i in range(n):
        x = qmm(x, Wlm[i % len(Wlm)])[:, :, :HID]
    return x


R["greedy_lm_head_248320x2048"] = slope_us(ch_lm_head)


def ch_lse(n):
    x = qmm(x2048, Wlm[0])
    for _ in range(n):
        x = x - mx.logsumexp(x)
    return x


R["lse_248320"] = slope_us(ch_lse)


def ch_take(n):
    i_ = ids
    for _ in range(n):
        i_ = (i_ + (mx.take(emb_words, i_).sum().astype(mx.int32) & 255)) % VOCAB
    return i_


try:
    out0 = ch_take(2)
    mx.eval(out0)
    R["take_u32_word_2048"] = slope_us(ch_take)
except Exception as e:
    NOTES["take"] = "failed: %r" % (e,)

# ---------- Composed fallback forms (identical Python both sides; this is what a
# stock-mlx side runs for these classes; on omarchy they route to elementwise kernels) ----------
def ch_norm_scaled_comp(n):
    q = qhd
    for _ in range(n):
        q = (HKD ** -0.5) * mx.fast.rms_norm(q, None, 1e-6)
    return q


R["rms_norm_scaled_composed_16x128"] = slope_us(ch_norm_scaled_comp)


def ch_norm_gated_comp(n):
    y = yhd
    for _ in range(n):
        x = mx.fast.rms_norm(y, w128, 1e-6)
        gate = mx.sigmoid(ghd.astype(mx.float32))
        y = (gate * x.astype(mx.float32)).astype(bf16)
    return y


R["rms_norm_gated_composed_16x128"] = slope_us(ch_norm_gated_comp)


def ch_conv_comp(n):
    import mlx.nn as nn

    conv1d = nn.Conv1d(CONV_DIM, CONV_DIM, CONV_K, bias=False, groups=CONV_DIM)
    mx.eval(conv1d.parameters())
    st = conv_st
    y = None
    for _ in range(n):
        x = mx.concatenate([st, qkv], axis=1)
        st = mx.contiguous(x[:, -(CONV_K - 1):, :])
        y = nn.silu(conv1d(x))
    return y


try:
    out0 = ch_conv_comp(2)
    mx.eval(out0)
    R["conv_composed_6144"] = slope_us(ch_conv_comp)
except Exception as e:
    NOTES["conv_composed"] = "failed: %r" % (e,)

mb = lambda n, k: (n * k / 2 + n * (k // 64) * 4) / 1e6
res["weight_MB"] = {
    "2048x2048": mb(HID, HID), "6144x2048": mb(INTER, HID), "2048x6144": mb(HID, INTER),
    "248320x2048": mb(VOCAB, HID),
}
res["gbps_from_slope"] = {
    "gemv_2048x2048": round(mb(HID, HID) / (R["gemv_2048x2048"][0] / 1e6) / 1e9, 1),
    "gemv_6144x2048": round(mb(INTER, HID) / (R["gemv_6144x2048"][0] / 1e6) / 1e9, 1),
    "up_down_pair": round(2 * mb(INTER, HID) / (R["gemv_up6144_then_down2048x6144_pair"][0] / 1e6 / 2) / 1e9, 1),
    "lm_head": round(mb(VOCAB, HID) / (R["greedy_lm_head_248320x2048"][0] / 1e6) / 1e9, 1),
}
res["async_eval_return_us_per_op"] = SUBMIT
print(json.dumps(res))
