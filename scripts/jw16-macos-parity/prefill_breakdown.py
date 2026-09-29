#!/usr/bin/env python3
"""Per-module wall time of one T-token prefill of Qwen3.8-2B (mlx-lm), eval-synced.

Times each distinct module class of layer 0 (GDN) and layer 3 (full attention)
on a random bf16 [1,T,H] input, median of REPS after 2 warmups, then scales by layer
counts. Runs on Linux (Honeykrisp) or macOS (Metal) unchanged, so the same table can
be produced on both sides. usage: prefill_breakdown.py MODEL_DIR [T] [REPS]
"""
import json, statistics as st, sys, time
import mlx.core as mx
from mlx_lm import load

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
        t0 = time.perf_counter(); mx.eval(fn()); ts.append(time.perf_counter() - t0)
    return st.median(ts) * 1000

rows = {}
kinds = {}
for i, l in enumerate(layers):
    k = "gdn" if hasattr(l, "linear_attn") else "attn"
    kinds.setdefault(k, []).append(i)
print("layers:", {k: len(v) for k, v in kinds.items()}, "T", T, file=sys.stderr)
for k, idxs in kinds.items():
    l = layers[idxs[0]]
    mixer = l.linear_attn if k == "gdn" else l.self_attn
    mask = None
    if k == "attn":
        from mlx_lm.models.base import create_attention_mask
        mask = create_attention_mask(x, None)
    def run_mixer():
        return mixer(x, mask=mask, cache=None) if k == "attn" else mixer(x, mask=None, cache=None)
    parts = {
        "input_norm": lambda: l.input_layernorm(x),
        "mixer": run_mixer,
        "post_norm": lambda: l.post_attention_layernorm(x),
        "mlp": lambda: l.mlp(x),
        "layer_total": lambda: l(x, mask=mask, cache=None),
    }
    for name, fn in parts.items():
        try:
            rows[f"{k}.{name}"] = round(timeit(fn), 2)
        except Exception as e:  # report, do not hide
            rows[f"{k}.{name}"] = f"ERR {type(e).__name__}: {e}"
head = getattr(model, "lm_head", None)
rows["lm_head_full_T"] = round(timeit(lambda: head(x) if head is not None else inner.embed_tokens.as_linear(x)), 2)
rows["final_norm"] = round(timeit(lambda: inner.norm(x)), 2)
tot = 0.0
for k, idxs in kinds.items():
    v = rows.get(f"{k}.layer_total")
    if isinstance(v, float):
        tot += v * len(idxs)
rows["model_layers_sum_ms"] = round(tot, 1)
rows["implied_tok_per_s"] = round(T / (tot / 1000), 1) if tot else None
x1 = x[:, :1, :]
def chain(idxs):
    def run():
        h = x1
        for i in idxs:
            h = layers[i](h, mask=None, cache=None)
        return h
    return run
rows["decode_chain_gdn18_ms"] = round(timeit(chain(kinds.get("gdn", []))), 3)
rows["decode_chain_attn6_ms"] = round(timeit(chain(kinds.get("attn", []))), 3)
rows["decode_chain_all24_ms"] = round(timeit(chain(range(len(layers)))), 3)
rows["decode_lm_head_1tok_ms"] = round(timeit(lambda: head(x1) if head is not None else inner.embed_tokens.as_linear(x1)), 3)
rows["T"] = T
print(json.dumps(rows, indent=1))
