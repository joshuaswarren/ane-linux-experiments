#!/usr/bin/env python3
"""Per-shape bitwise equality + perf microbench for the SDPA hd256 arm.

For each k in K_VALUES, build q/k/v matching the Qwen3.8 decode shapes
(8 q heads x 256, 2 kv heads x 256, T=1, bf16, no mask), call
mx.fast.scaled_dot_product_attention with an interceptor that swaps in
the composed-fallback reference. Compute both:
  fused = the cand (built with sdpa_decode_hd256)
  composed = a Python emulated f32-score reference
Verify bitwise equality (max |fused - composed| / composed <= 0). Then
run 300 reps per k measuring the fused arm wall time per call (one
call per iteration, mx.eval joins).

Mirrors /var/tmp/vp/sdpa_token_counts.py + the t6001 microbench
(qwen38-decode-shapes, kWindow [13,44,300,513,2048], bitwise
fused==composed at every k).
"""
import argparse, json, os, sys, time

p = argparse.ArgumentParser()
p.add_argument("--out", required=True)
p.add_argument("--reps", type=int, default=300)
a = p.parse_args()

import mlx.core as mx

K_VALUES = [12, 13, 24, 44, 128, 300, 513, 2048]
H_Q, H_KV = 8, 2
HEAD_DIM = 256
SCALE = 1.0 / (HEAD_DIM ** 0.5)


def composed_reference(q, k, v):
    """f32-score composition that mirrors the mlx-omarchy composed SDPA path.
    Returns bf16."""
    # q [1, H_Q, 1, D]; k/v [1, H_KV, L, D]
    # GQA repeats: tile k/v to H_Q heads
    rep = H_Q // H_KV
    # broadcast k/v to H_Q heads: [1, H_Q, L, D]
    qf = q.astype(mx.float32)
    kf = mx.repeat(k.astype(mx.float32), rep, axis=1)
    vf = mx.repeat(v.astype(mx.float32), rep, axis=1)
    # scores = q @ k^T * scale -> [1, H_Q, 1, L]
    scores = mx.matmul(qf, mx.transpose(kf, (0, 1, 3, 2))) * SCALE
    probs = mx.softmax(scores, axis=-1)
    out = mx.matmul(probs, vf)
    return out.astype(mx.bfloat16)


def run_one(k_len, reps):
    mx.random.seed(42)
    q = mx.random.normal((1, H_Q, 1, HEAD_DIM)).astype(mx.bfloat16)
    k = mx.random.normal((1, H_KV, k_len, HEAD_DIM)).astype(mx.bfloat16)
    v = mx.random.normal((1, H_KV, k_len, HEAD_DIM)).astype(mx.bfloat16)
    # warmup
    for _ in range(3):
        o = mx.fast.scaled_dot_product_attention(q, k, v, scale=SCALE)
        mx.eval(o)
    ref = composed_reference(q, k, v)
    mx.eval(ref)
    # bitwise compare
    out_fused = mx.fast.scaled_dot_product_attention(q, k, v, scale=SCALE)
    mx.eval(out_fused)
    diff = mx.max(mx.abs(out_fused.astype(mx.float32) - ref.astype(mx.float32)))
    mx.eval(diff)
    diff_f = float(diff)
    bit_equal = diff_f == 0.0
    # perf
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        o = mx.fast.scaled_dot_product_attention(q, k, v, scale=SCALE)
        mx.eval(o)
        ts.append(time.perf_counter() - t0)
    ts.sort()
    med_us = ts[len(ts) // 2] * 1e6
    return {"k_len": k_len, "bit_equal": bit_equal, "max_abs_diff": diff_f,
            "median_us": med_us}


results = []
for k_len in K_VALUES:
    r = run_one(k_len, a.reps)
    results.append(r)
    print(f"k={k_len:5d}  bit_equal={r['bit_equal']}  max|Δ|={r['max_abs_diff']:.6g}  median={r['median_us']:.2f} us")
with open(a.out, "w") as f:
    json.dump(results, f, indent=1)
# gate
all_equal = all(r["bit_equal"] for r in results)
print(f"\nbitwise gate: {'PASS' if all_equal else 'FAIL'}  ({sum(r['bit_equal'] for r in results)}/{len(results)} equal)")
sys.exit(0 if all_equal else 1)
