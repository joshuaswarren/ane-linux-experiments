#!/usr/bin/env python3
"""dump_kernels.py — compile the deployed decode-class pipelines once so
AGX_MESA_DEBUG=shaders prints their NIR + AGX ISA to stderr. No timing, no
correctness claims. Same ops/shapes as chain_costs_decode2.py's GDN/norm/rope
chains."""
import mlx.core as mx

bf16 = mx.bfloat16
mx.random.seed(0)
NOTES = []

qhd = mx.random.normal((1, 1, 16, 128)).astype(bf16)
yhd = mx.random.normal((1, 1, 16, 128)).astype(bf16)
ghd = mx.random.normal((1, 1, 16, 128)).astype(bf16)
w128 = mx.random.normal((128,)).astype(bf16)
qkv = mx.random.normal((1, 1, 6144)).astype(bf16)
conv_w = mx.random.normal((6144, 4, 1)).astype(bf16)
conv_st = mx.zeros((1, 3, 6144), dtype=bf16)
qx = mx.random.normal((1, 1, 8, 256)).astype(bf16)
w2048 = mx.random.normal((2048,)).astype(bf16)
x2048 = mx.random.normal((1, 1, 2048)).astype(bf16)

outs = []
outs.append(mx.fast.rms_norm(x2048, w2048, 1e-6))
if hasattr(mx.fast, "rms_norm_scaled"):
    outs.append(mx.fast.rms_norm_scaled(qhd, None, (128 ** -0.5) ** 2, 1e-6))
if hasattr(mx.fast, "rms_norm_gated"):
    outs.append(mx.fast.rms_norm_gated(yhd, ghd, w128, 1e-6))
if hasattr(mx.fast, "gdn_conv_update"):
    try:
        o, s = mx.fast.gdn_conv_update(
            conv_st, qkv, conv_w, activate=True,
            qk_key_dim=2048, qk_scale_q=(128 ** -0.5) ** 2,
            qk_scale_k=128 ** -0.5, qk_eps=1e-6)
        NOTES.append("conv:fused")
        outs.extend([o, s])
    except Exception as e:
        NOTES.append("conv:plain:%r" % (e,))
        o, s = mx.fast.gdn_conv_update(conv_st, qkv, conv_w, activate=True)
        outs.extend([o, s])
try:
    from mlx_lm.models.gated_delta import gated_delta_update as gdu
    st = mx.zeros((1, 16, 128, 128), dtype=mx.float32)
    o, s = gdu(qhd, qhd, qhd, mx.zeros((1, 1, 16)), mx.zeros((1, 1, 16)),
               mx.zeros((16,)), mx.ones((16,)), st, None, use_kernel=True)
    NOTES.append("gdu:ok")
    outs.extend([o, s])
except Exception as e:
    NOTES.append("gdu:fail:%r" % (e,))
try:
    q = mx.fast.rope(qx, 256, traditional=False, base=100000.0, scale=1.0,
                     offset_or_positions=mx.array([0], dtype=mx.int32))
    q = mx.fast.rms_norm_scaled(q, None, 256 ** -0.5, 1e-6)
    NOTES.append("ropenorm:ok")
    outs.append(q)
except Exception as e:
    NOTES.append("ropenorm:fail:%r" % (e,))

mx.eval(outs)
import json
print(json.dumps({"notes": NOTES}))
