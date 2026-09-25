#!/usr/bin/env python3
"""Tensor-level bit-exactness qualification for the fused GDN norm kernels.

Compares, on the device:
  1. mx.fast.rms_norm_gated(x, gate, w, eps)  vs  composed
     rms_norm -> f32 silu(gate)*x chain (the mlx-lm _precise_swiglu form)
  2. mx.fast.rms_norm_scaled(x, w, scale, eps) vs scale * rms_norm(...)

Shapes and scalars mirror the m1-host GDN decode shapes exactly (16 heads x
128, hidden 2048 rows, inv_scale = 128**-0.5). Every case must be
array_equal (0 mismatched bits); the script exits nonzero otherwise.
"""
import mlx.core as mx
import numpy as np

rng = np.random.default_rng(20260923)


def rand_bf16(shape, scale=1.0):
    a = rng.standard_normal(shape).astype(np.float32) * scale
    return mx.array(a).astype(mx.bfloat16)


def composed_gated(x, gate, w, eps):
    y = mx.fast.rms_norm(x, w, eps)
    g = gate.astype(mx.float32)
    silu = g * mx.sigmoid(g)
    return (silu * y.astype(mx.float32)).astype(x.dtype)


def composed_scaled(x, w, scale, eps):
    y = mx.fast.rms_norm(x, w, eps)
    return scale * y


# The mlx-lm composed form passes a size-1 ones weight nowhere: upstream
# rms_norm takes None for weightless. Keep the weightless reference on
# the None path exactly as the model does.


def check(name, a, b):
    ea = np.array(a.astype(mx.float32))
    eb = np.array(b.astype(mx.float32))
    equal = np.array_equal(ea, eb)
    diff = float(np.abs(ea - eb).max()) if ea.size else 0.0
    ba = ea.view(np.uint32)
    bb = eb.view(np.uint32)
    bit_diff = int(np.count_nonzero(ba != bb))
    status = "OK " if equal and bit_diff == 0 else "FAIL"
    print(f"[{status}] {name:52s} bits_diff={bit_diff} max_abs={diff:.3e}")
    return equal and bit_diff == 0


ok = True
eps = 1e-6
inv_scale = 128 ** -0.5

for rows, hidden in [(16, 128), (1, 128), (7, 128), (256, 128), (3, 2048)]:
    x = rand_bf16((rows, hidden), scale=0.5)
    gate = rand_bf16((rows, hidden), scale=2.0)
    w = rand_bf16((hidden,), scale=0.1) + 1.0
    w1 = mx.array(np.ones((1,), np.float32)).astype(mx.bfloat16)

    ok &= check(
        f"gated w rows={rows}x{hidden}",
        mx.fast.rms_norm_gated(x, gate, w, eps),
        composed_gated(x, gate, w, eps),
    )
    ok &= check(
        f"gated weightless rows={rows}x{hidden}",
        mx.fast.rms_norm_gated(x, gate, w1, eps),
        composed_gated(x, gate, None, eps),
    )

    for scale, tag in (
        (inv_scale * inv_scale, "inv_scale^2"),
        (inv_scale, "inv_scale"),
        (1.0, "one"),
        (2.718281828459045, "e"),
        (1e-3, "1e-3"),
    ):
        ok &= check(
            f"scaled rows={rows}x{hidden} scale={tag}",
            mx.fast.rms_norm_scaled(x, None, scale, eps),
            composed_scaled(x, None, scale, eps),
        )
    ok &= check(
        f"scaled weighted rows={rows}x{hidden}",
        mx.fast.rms_norm_scaled(x, w, inv_scale, eps),
        composed_scaled(x, w, inv_scale, eps),
    )

# Adversarial: extreme magnitudes through silu, zeros, exact bf16 edges.
x = rand_bf16((16, 128), scale=30.0)
gate = (rand_bf16((16, 128), scale=30.0))
w1 = mx.array(np.ones((1,), np.float32)).astype(mx.bfloat16)
ok &= check(
    "gated extreme magnitudes",
    mx.fast.rms_norm_gated(x, gate, w1, eps),
    composed_gated(x, gate, None, eps),
)
z = mx.zeros((16, 128), dtype=mx.bfloat16)
ok &= check(
    "gated zero input",
    mx.fast.rms_norm_gated(z, gate, w1, eps),
    composed_gated(z, gate, None, eps),
)

# Informational, NOT gate-fatal: at >= 512 rows (prefill chunks) a rare
# ~1e-5-of-outputs 1-ULP deviation vs the composed path is known to
# appear (fused large-grid vs composed large-tensor dispatch difference,
# side undetermined). The mlx-lm routing gates fused dispatch to
# size <= 32768 (<= 256 rows), so prefill keeps the composed ops and
# model outputs stay bit-identical to the installed baseline. This case
# documents the deviation; it must not gate the decode contract.
w128 = rand_bf16((128,), scale=0.1) + 1.0
x = rand_bf16((1, 512, 16, 128), scale=0.5)
gate = rand_bf16((1, 512, 16, 128), scale=2.0)
check(
    "INFO prefill shape 1x512x16x128 (routed around, not gated)",
    mx.fast.rms_norm_gated(x, gate, w128, eps),
    composed_gated(x, gate, w128, eps),
)

print("ALL_BIT_EXACT" if ok else "BIT_EXACT_FAILURES")
raise SystemExit(0 if ok else 1)
