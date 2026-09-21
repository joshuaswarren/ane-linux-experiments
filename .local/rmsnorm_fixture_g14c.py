#!/usr/bin/env python3
"""Matched BF16 RMSNorm fixture run on G14C Vulkan (jw14m2) for the Distill lane.

Fixture: oprefs_cpu.safetensors (x [6,2048] bf16 recorded input, w0 [2048] bf16
checkpoint weight, n1 [6,2048] bf16 CPU-composite reference, n1_fp32ref fp32).
eps = 1e-6. dtype path bf16 in/out.
References (Distill spec): two-round = RNE_bf16(RNE_bf16(x*n)*w),
single-round = RNE_bf16((x*n)*w), n = 1/sqrt(mean(x^2,keepdims)+eps).
Run via mx.fast.rms_norm (fused kernel, the production path) and explicit naive.
"""
import json
import numpy as np
import mlx.core as mx
import struct

FIX = "/var/tmp/jw14-bench/oprefs_cpu.safetensors"
EPS = 1e-6

def load_safetensors_manual(path):
    with open(path, "rb") as f:
        (hlen,) = struct.unpack("<Q", f.read(8))
        header = json.loads(f.read(hlen))
        data = f.read()
    out = {}
    for k, v in header.items():
        if k == "__metadata__":
            continue
        b = data[v["data_offsets"][0]:v["data_offsets"][1]]
        dt = v["dtype"]
        if dt == "BF16":
            arr = np.frombuffer(b, dtype=np.uint16).astype(np.uint32) << 16
            out[k] = arr.view(np.float32).reshape(v["shape"])  # exact bf16 values as f32
        elif dt == "F32":
            out[k] = np.frombuffer(b, dtype=np.float32).reshape(v["shape"]).copy()
        else:
            raise ValueError(dt)
    return out

t = load_safetensors_manual(FIX)
print("fixture keys:", {k: (v.shape, "f32-view") for k, v in t.items()})

x_np = t["x"].reshape(6, 2048); w_np = t["w0"]; n1_np = t["n1"].reshape(6, 2048)
ref32 = t["n1_fp32ref"].reshape(6, 2048) if t["n1_fp32ref"].size == 6 * 2048 else None
print("shapes:", x_np.shape, w_np.shape, n1_np.shape, None if ref32 is None else ref32.shape)

def rne_bf16(a_f32):
    u = a_f32.view(np.uint32)
    r = ((u + 0x7FFF + ((u >> 16) & 1)) & 0xFFFF0000).astype(np.uint32)
    return r.view(np.float32)

xf = x_np.astype(np.float64)
n = 1.0 / np.sqrt(np.mean(xf * xf, axis=-1, keepdims=True) + EPS)
two_round = rne_bf16((rne_bf16((xf * n).astype(np.float32)) * w_np.astype(np.float64)).astype(np.float32))
single_round = rne_bf16(((xf * n).astype(np.float32) * w_np).astype(np.float32))

x = mx.array(x_np).astype(mx.bfloat16)
w = mx.array(w_np).astype(mx.bfloat16)

gpu_fast = mx.fast.rms_norm(x, w, EPS)
gpu_fast32 = np.array(gpu_fast.astype(mx.float32))
sq = mx.mean(x * x, axis=-1, keepdims=True)
gpu_naive = np.array(((x / mx.sqrt(sq + EPS)) * w).astype(mx.float32))

def cmp(name, got):
    d_comp = np.abs(got.astype(np.float64) - n1_np.astype(np.float64))
    row = {
        "impl": name,
        "vs_n1_maxabs": float(d_comp.max()),
        "vs_n1_bitexact_frac": float(np.mean(got.view(np.uint32) == n1_np.view(np.uint32))),
        "vs_tworound_bitexact_frac": float(np.mean(got.view(np.uint32) == two_round.view(np.uint32))),
        "vs_singleround_bitexact_frac": float(np.mean(got.view(np.uint32) == single_round.view(np.uint32))),
        "out_abs_max": float(np.abs(got).max()),
    }
    if ref32 is not None:
        d_ref = np.abs(got.astype(np.float64) - ref32.astype(np.float64))
        rel = np.sqrt(np.sum((got.astype(np.float64) - ref32.astype(np.float64)) ** 2)) / np.sqrt(np.sum(ref32.astype(np.float64) ** 2))
        row["vs_fp32ref_maxabs"] = float(d_ref.max())
        row["vs_fp32ref_relL2"] = float(rel)
    # PRESERVED MISMATCH CASES for the postfix-candidate gate (Main-directed):
    # every element where the GPU output differs from the chosen-contract
    # composite (n1), with got/n1 values — the postfix wheel must clear these.
    mis = np.nonzero(got.view(np.uint32).ravel() != n1_np.view(np.uint32).ravel())[0]
    row["mismatch_vs_n1"] = [{"idx": int(i),
                              "gpu": float(got.ravel()[i]),
                              "n1": float(n1_np.ravel()[i]),
                              "gpu_bits": hex(int(got.view(np.uint32).ravel()[i])),
                              "n1_bits": hex(int(n1_np.view(np.uint32).ravel()[i]))} for i in mis]
    row["mismatch_count_vs_n1"] = int(mis.size)
    return row

rows = [cmp("gpu_fast_rms_norm", gpu_fast32), cmp("gpu_naive_bf16", gpu_naive),
        cmp("cpu_tworound", two_round), cmp("cpu_singleround", single_round)]
print(json.dumps(rows, indent=1))
