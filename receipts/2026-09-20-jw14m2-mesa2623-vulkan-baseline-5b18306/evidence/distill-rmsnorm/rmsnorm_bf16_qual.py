#!/usr/bin/env python3
"""BF16 RMSNorm numeric qualification on the G14C Vulkan device (jw14m2).

For each (hidden, eps, scale) config:
  x_bf16 = random inputs (seeded) at the given scale, weights = bf16 ones (and a
  varied-weights case), computed three ways:
    gpu_fast : mx.fast.rms_norm(x, w, eps)            (the fused MLX kernel path)
    gpu_naive: x / sqrt(mean(x^2)+eps) * w            (explicit ops, same dtype)
    ref      : fp64 numpy on the SAME bf16-rounded inputs, then rounded to bf16
  Metrics vs ref: bit-exact fraction, max ulp (bf16 ulp on ref), max abs err.
Run: python3 rmsnorm_bf16_qual.py [--out results.json]
"""
import json
import numpy as np
import mlx.core as mx

EPS_LIST = [1e-6, 1e-5]
HIDDENS = [1024, 2048, 5120]
SCALES = [1.0, 1e-3, 1e3]
N = 1024  # rows


def bf16_ulp_spacing(ref_f32):
    # vectorized: spacing of bf16 at each ref magnitude (normals only; 0 for exp=0)
    u = np.ascontiguousarray(ref_f32).view(np.uint32)
    exp = ((u & 0x7F800000) >> 23).astype(np.int32)
    return np.ldexp(np.ones(exp.shape, dtype=np.float64), np.where(exp > 0, exp - 133, -1000))


def ref_np(x_bf16_np, w_bf16_np, eps):
    xf = x_bf16_np.astype(np.float64)
    wf = w_bf16_np.astype(np.float64)
    ms = np.mean(xf * xf, axis=-1, keepdims=True)
    return wf * xf / np.sqrt(ms + eps)


def to_bf16_np(a_f32):
    # round-to-nearest-even f32 -> bf16 -> back to f32
    u = a_f32.view(np.uint32)
    rounded = ((u + 0x7FFF + ((u >> 16) & 1)) & 0xFFFF0000).astype(np.uint32)
    return rounded.view(np.float32)


def main():
    rng = np.random.default_rng(0)
    results = []
    for H in HIDDENS:
        for eps in EPS_LIST:
            for scale in SCALES:
                x32 = (rng.standard_normal((N, H)) * scale).astype(np.float32)
                w32 = np.ones(H, dtype=np.float32)
                # bf16 rounding of inputs
                x_b = to_bf16_np(x32)
                w_b = to_bf16_np(w32)
                x = mx.array(x_b).astype(mx.bfloat16)
                w = mx.array(w_b).astype(mx.bfloat16)
                gpu_fast = np.array(mx.fast.rms_norm(x, w, eps).astype(mx.float32))
                sq = mx.mean(x * x, axis=-1, keepdims=True)
                gpu_naive = np.array((x / mx.sqrt(sq + eps) * w).astype(mx.float32))
                ref = to_bf16_np(ref_np(x_b, w_b, eps).astype(np.float32))
                for name, got in (("gpu_fast", gpu_fast), ("gpu_naive", gpu_naive)):
                    bit = float(np.mean(got.view(np.uint32) == ref.view(np.uint32)))
                    diff = np.abs(got.astype(np.float64) - ref.astype(np.float64))
                    ulp = bf16_ulp_spacing(ref)
                    max_ulp = float(np.max(diff / ulp)) if np.all(ulp > 0) else float("inf")
                    results.append({
                        "impl": name, "hidden": H, "eps": eps, "scale": scale,
                        "n": N, "bit_exact_frac": round(bit, 6),
                        "max_ulp": max_ulp,
                        "max_abs_err": float(np.max(diff)),
                        "ref_denormal_frac": float(np.mean(np.abs(ref) < 1.1754944e-38)),
                    })
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
