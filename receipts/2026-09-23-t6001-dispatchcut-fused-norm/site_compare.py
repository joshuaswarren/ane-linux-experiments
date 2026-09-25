#!/usr/bin/env python3
"""Compare fused rms_norm_gated/rms_norm_scaled vs composed paths on REAL
model activations. Monkeypatches the model's RMSNormGated/GatedDeltaNet to
run BOTH paths per call, recording element mismatch stats with magnitudes.
Runs the contract decode (prompt 0, 16 tokens) so tensors are real.
"""
import json, sys, time
import mlx.core as mx
import numpy as np

stats = {"gated": [], "scaled": []}

import mlx.nn as nn

def composed_gated(h, z, w, eps):
    x = mx.fast.rms_norm(h, w, eps)
    g = nn.silu(z.astype(mx.float32))
    xf = x.astype(mx.float32)
    return (g * xf).astype(h.dtype)

def composed_scaled(q, scale, eps):
    return scale * mx.fast.rms_norm(q, None, eps)

def record(kind, fused, comp, tag):
    f = np.array(fused.astype(mx.float32))
    c = np.array(comp.astype(mx.float32))
    mis = f != c
    n = int(mis.sum())
    rec = {"tag": tag, "n": n, "size": int(f.size),
           "shape": list(fused.shape)}
    if n:
        idx = np.argwhere(mis)
        diffs = np.abs(f - c)
        ulps = []
        fb = f.view(np.uint32) if f.dtype == np.float32 else None
        rec["maxabs"] = float(diffs.max())
        rec["mis_mag_range"] = [float(np.abs(f[mis]).min()), float(np.abs(f[mis]).max())]
        samples = []
        for i in idx[:4]:
            t = tuple(int(v) for v in i)
            samples.append((t, float(f[t]), float(c[t])))
        rec["samples"] = samples
    stats[kind].append(rec)

import mlx_lm.models.qwen3_next as qn
import mlx_lm.models.qwen3_5 as q35

orig_gated_call = qn.Qwen3NextRMSNormGated.__call__
def gated_call(self, hidden_states, gate=None):
    if gate is not None and hidden_states.dtype == mx.bfloat16 and hidden_states.size <= 32768 and mx.default_device() == mx.gpu:
        fused = mx.fast.rms_norm_gated(hidden_states, gate, self.weight, self.eps)
        comp = composed_gated(hidden_states, gate, self.weight, self.eps)
        mx.eval(fused, comp)
        if len(stats["gated"]) == 1:
            print("DTYPES h", hidden_states.dtype, "z", gate.dtype,
                  "w", self.weight.dtype, "eps", self.eps,
                  "fused", fused.dtype, "comp", comp.dtype)
        record("gated", fused, comp, f"h{getattr(self,'_tag','?')}")
        return fused
    return orig_gated_call(self, hidden_states, gate)
qn.Qwen3NextRMSNormGated.__call__ = gated_call

orig_scaled = q35.GatedDeltaNet.__call__
def gdn_call(self, inputs, mask=None, cache=None):
    # intercept q/k norms by wrapping mx.fast.rms_norm? simpler: recompute here is
    # complex; instead patch at the fast-call level via subclass of the code path
    return orig_scaled(self, inputs, mask, cache)
# For scaled sites: wrap mx.fast.rms_norm_scaled to also compute composed
orig_scaled_fast = mx.fast.rms_norm_scaled
def scaled_probe(q, w, scale, eps):
    fused = orig_scaled_fast(q, w, scale, eps)
    comp = composed_scaled(q, scale, eps)
    mx.eval(fused, comp)
    record("scaled", fused, comp, f"q{tuple(q.shape)}s{scale:.6g}")
    return fused
mx.fast.rms_norm_scaled = scaled_probe
import mlx_lm.models.qwen3_5  # ensure module-level mx binding same object

MODEL = sys.argv[1]
PROMPTS = sys.argv[2]
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache
from mlx_lm.generate import generate_step
model, tok = load(MODEL)
# tag gated-norm sites per layer (qwen3_5 wraps the text model)
text_model = getattr(model, "model", None) or getattr(model, "language_model", None)
if text_model is None:
    text_model = next(m for m in (getattr(model, n) for n in dir(model)) if hasattr(m, "layers"))
# tag gated-norm sites per layer
for i, layer in enumerate(text_model.layers):
    if hasattr(layer, "linear_attn"):
        layer.linear_attn.norm._tag = f"L{i}"
prompts = [json.loads(l)["text"] for l in open(PROMPTS) if l.strip()]
ids = tok.encode(prompts[0])
cache = make_prompt_cache(model)
it = generate_step(mx.array(ids), model, prompt_cache=cache)
t0 = time.time()
n = 0
for tk, _ in it:
    n += 1
    mx.eval(tk)
    if n >= 16:
        break
print(f"generated {n} tokens in {time.time()-t0:.1f}s")
g = stats["gated"]; s = stats["scaled"]
print(f"gated calls: {len(g)}, mismatched calls: {sum(1 for r in g if r['n']>0)}, total mismatched elems: {sum(r['n'] for r in g)}")
for r in g:
    if r["n"]:
        print("  GATED", r)
print(f"scaled calls: {len(s)}, mismatched calls: {sum(1 for r in s if r['n']>0)}, total mismatched elems: {sum(r['n'] for r in s)}")
for r in s[:6]:
    if r["n"]:
        print("  SCALED", r)
json.dump(stats, open("/tmp/t6001cut/out/site-stats.json", "w"), indent=1)
