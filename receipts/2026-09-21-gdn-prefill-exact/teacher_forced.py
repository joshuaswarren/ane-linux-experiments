#!/usr/bin/env python3
"""Teacher-forced fused-vs-ops comparison + determinism check.

Env: GDN_DISABLE_FAST=1 forces the ops path, unset routes to the fused
primitive. Sequence: (1) greedy reference stream under ops; (2) teacher-
forced logits for prompt+stream under ops and fused; (3) per-position
argmax flips with margins; (4) fused run twice for determinism.
"""
import json
import os
import sys

import mlx.core as mx
from mlx_lm import load

MODEL = sys.argv[1]
PROMPTS = sys.argv[2]
N_PROMPT = 512
N_GEN = int(os.environ.get("TF_GEN", "64"))

rows = [json.loads(l) for l in open(PROMPTS)]
prompts = [r.get("text") or r.get("prompt") or next(iter(r.values())) for r in rows]
model, tokenizer = load(MODEL)
prompt = tokenizer.encode(prompts[0])[:N_PROMPT]

def greedy(toks, n):
    out = list(toks)
    for _ in range(n):
        logits = model(mx.array([out]))
        mx.eval(logits)
        out.append(int(mx.argmax(logits[0, -1]).item()))
    return out

def logits_of(toks):
    lg = model(mx.array([toks]))
    mx.eval(lg)
    return lg[0]  # [T, V]

all_results = []
for pi, prows in enumerate(rows):
    prompt = tokenizer.encode(prows.get("text"))[:N_PROMPT]
    os.environ["GDN_DISABLE_FAST"] = "1"
    stream = greedy(prompt, N_GEN)
    lg_ops = logits_of(stream)
    os.environ["GDN_DISABLE_FAST"] = "0"
    lg_f1b = logits_of(stream)
    lg_f2 = logits_of(stream)
    det = mx.array_equal(lg_f1b, lg_f2).item()
    lo = lg_ops[:-1]; lf = lg_f1b[:-1]; ref = stream[1:]
    max_diff = mx.abs(lf.astype(mx.float32) - lo.astype(mx.float32)).max().item()
    am_ops = mx.argmax(lo, axis=-1); am_f = mx.argmax(lf, axis=-1)
    flips = []
    for t in range(lo.shape[0]):
        a, b = int(am_ops[t].item()), int(am_f[t].item())
        if a != b:
            rowf = lf[t].astype(mx.float32)
            top1 = mx.max(rowf).item()
            flips.append({"pos": t, "ops_tok": a, "fused_tok": b,
                          "margin": top1 - max(rowf[a].item(), rowf[b].item())})
    all_results.append({"prompt": pi, "max_logit_diff": max_diff,
                        "flips": flips, "determinism": det})
    mx.clear_cache()
flips_all = [f for r in all_results for f in r["flips"]]
print(json.dumps({
    "per_prompt_max_logit_diff": [r["max_logit_diff"] for r in all_results],
    "total_flips": len(flips_all),
    "flip_margins": [f["margin"] for f in flips_all],
    "max_flip_margin": max((f["margin"] for f in flips_all), default=None),
    "all_deterministic": all(r["determinism"] for r in all_results),
}, indent=2))

