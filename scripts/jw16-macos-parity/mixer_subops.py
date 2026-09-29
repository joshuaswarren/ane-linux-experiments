#!/usr/bin/env python3
"""Sub-op wall times inside the GDN and full-attention mixers at T tokens (eval-synced,
median of REPS after 2 warmups; inputs precomputed so each row times only its own op).
Runs unchanged on Linux (Honeykrisp) and macOS (Metal). usage: mixer_subops.py MODEL_DIR [T] [REPS]
"""
import json
import statistics as st
import sys
import time

import mlx.core as mx
import mlx.nn as nn
from mlx_lm import load
from mlx_lm.models.gated_delta import gated_delta_update

model_dir = sys.argv[1]
T = int(sys.argv[2]) if len(sys.argv) > 2 else 2048
REPS = int(sys.argv[3]) if len(sys.argv) > 3 else 5
model, _ = load(model_dir)
inner = model.model if hasattr(model, "model") else model.language_model.model
layers = inner.layers
H = layers[0].input_layernorm.weight.shape[-1]
x = mx.random.normal((1, T, H)).astype(mx.bfloat16)
mx.eval(x)


def timeit(fn):
    for _ in range(2):
        mx.eval(fn())
    ts = []
    for _ in range(REPS):
        t0 = time.perf_counter()
        mx.eval(fn())
        ts.append(time.perf_counter() - t0)
    return round(st.median(ts) * 1000, 3)


rows = {"T": T}
g = next(l.linear_attn for l in layers if hasattr(l, "linear_attn"))
B, S = 1, T
rows["gdn.in_proj_qkv"] = timeit(lambda: g.in_proj_qkv(x))
rows["gdn.in_proj_z"] = timeit(lambda: g.in_proj_z(x))
rows["gdn.in_proj_b+a"] = timeit(lambda: (g.in_proj_b(x), g.in_proj_a(x)))
qkv = g.in_proj_qkv(x)
z = g.in_proj_z(x).reshape(B, S, g.num_v_heads, g.head_v_dim)
b = g.in_proj_b(x)
a = g.in_proj_a(x)
mx.eval(qkv, z, b, a)
conv_state = mx.zeros((B, g.conv_kernel_size - 1, g.conv_dim), dtype=x.dtype)
rows["gdn.conv(concat+conv1d+silu)"] = timeit(
    lambda: nn.silu(g.conv1d(mx.concatenate([conv_state, qkv], axis=1))))
conv_out = nn.silu(g.conv1d(mx.concatenate([conv_state, qkv], axis=1)))
mx.eval(conv_out)
q, k, v = [
    t.reshape(B, S, h, d)
    for t, h, d in zip(
        mx.split(conv_out, [g.key_dim, 2 * g.key_dim], -1),
        [g.num_k_heads, g.num_k_heads, g.num_v_heads],
        [g.head_k_dim, g.head_k_dim, g.head_v_dim],
    )
]
inv = k.shape[-1] ** -0.5
rows["gdn.qk_rms_norm"] = timeit(lambda: (
    (inv**2) * mx.fast.rms_norm(q, None, 1e-6), inv * mx.fast.rms_norm(k, None, 1e-6)))
qn = (inv**2) * mx.fast.rms_norm(q, None, 1e-6)
kn = inv * mx.fast.rms_norm(k, None, 1e-6)
mx.eval(qn, kn)
rows["gdn.gated_delta_update"] = timeit(lambda: gated_delta_update(
    qn, kn, v, a, b, g.A_log, g.dt_bias, None, None, use_kernel=True)[0])
out, _ = gated_delta_update(qn, kn, v, a, b, g.A_log, g.dt_bias, None, None, use_kernel=True)
mx.eval(out)
rows["gdn.norm_gated"] = timeit(lambda: g.norm(out, z))
o2 = g.norm(out, z).reshape(B, S, -1)
mx.eval(o2)
rows["gdn.out_proj"] = timeit(lambda: g.out_proj(o2))

at = next(l.self_attn for l in layers if hasattr(l, "self_attn"))
L = T
qp = at.q_proj(x).reshape(B, L, at.num_attention_heads, -1)
split_gate = hasattr(at, "q_gate_proj")  # Linux venv patch: q and gate are separate projections
queries = qp if split_gate else mx.split(qp, 2, axis=-1)[0]
if split_gate:
    rows["attn.q_gate_proj"] = timeit(lambda: at.q_gate_proj(x))
keys, values = at.k_proj(x), at.v_proj(x)
rows["attn.q_proj"] = timeit(lambda: at.q_proj(x))
rows["attn.k+v_proj"] = timeit(lambda: (at.k_proj(x), at.v_proj(x)))
queries = at.q_norm(queries).transpose(0, 2, 1, 3)
keys = at.k_norm(keys.reshape(B, L, at.num_key_value_heads, -1)).transpose(0, 2, 1, 3)
values = values.reshape(B, L, at.num_key_value_heads, -1).transpose(0, 2, 1, 3)
rows["attn.qk_norm+rope"] = timeit(lambda: (at.rope(at.q_norm(queries)), at.rope(at.k_norm(keys))))
queries = at.rope(queries)
keys = at.rope(keys)
mx.eval(queries, keys, values)
rows["attn.sdpa_causal"] = timeit(lambda: mx.fast.scaled_dot_product_attention(
    queries, keys, values, scale=at.scale, mask="causal"))
so = mx.fast.scaled_dot_product_attention(queries, keys, values, scale=at.scale, mask="causal")
so = so.transpose(0, 2, 1, 3).reshape(B, L, -1)
mx.eval(so)
rows["attn.o_proj"] = timeit(lambda: at.o_proj(so))
print(json.dumps(rows, indent=1))
