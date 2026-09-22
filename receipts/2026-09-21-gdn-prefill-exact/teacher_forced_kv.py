#!/usr/bin/env python3
"""KV-cache teacher-forced sweep: fast (minutes) version.

Per prompt: ops-mode cached greedy reference stream (32 tok), then one
teacher-forced forward per mode over prompt+stream; compare argmax per
position, margins, determinism (two fused passes).
"""
import json
import os
import sys

import mlx.core as mx
from mlx_lm import load
from mlx_lm.generate import generate

MODEL = sys.argv[1]
PROMPTS = sys.argv[2]
N_PROMPT = int(os.environ.get("TF_PROMPT", "512"))
N_GEN = int(os.environ.get("TF_GEN", "32"))

rows = [json.loads(l) for l in open(PROMPTS)]
model, tokenizer = load(MODEL)

all_results = []
for pi, prow in enumerate(rows):
    prompt = tokenizer.encode(prow.get("text"))[:N_PROMPT]
    os.environ["GDN_DISABLE_FAST"] = "1"
    text = generate(model, tokenizer, prompt=prompt, max_tokens=N_GEN)
    stream = tokenizer.encode(text, add_special_tokens=False)
    stream = prompt + stream[:N_GEN]

    os.environ["GDN_DISABLE_FAST"] = "1"
    lg_ops = model(mx.array([stream]))[0]
    os.environ["GDN_DISABLE_FAST"] = "0"
    lg_f1 = model(mx.array([stream]))[0]
    lg_f2 = model(mx.array([stream]))[0]
    mx.eval(lg_ops, lg_f1, lg_f2)

    det = mx.array_equal(lg_f1, lg_f2).item()
    lo = lg_ops[:-1].astype(mx.float32)
    lf = lg_f1[:-1].astype(mx.float32)
    max_diff = mx.abs(lf - lo).max().item()
    am_ops = mx.argmax(lo, axis=-1)
    am_f = mx.argmax(lf, axis=-1)
    flips = []
    for t in range(lo.shape[0]):
        a, b = int(am_ops[t].item()), int(am_f[t].item())
        if a != b:
            rowf = lf[t]
            top1 = mx.max(rowf).item()
            flips.append({"pos": t, "ops_tok": a, "fused_tok": b,
                          "margin": top1 - max(rowf[a].item(), rowf[b].item())})
    all_results.append({"prompt": pi, "max_logit_diff": max_diff,
                        "flips": flips, "determinism": det})
    print("prompt", pi, "done", flush=True)

flips_all = [f for r in all_results for f in r["flips"]]
print(json.dumps({
    "per_prompt_max_logit_diff": [r["max_logit_diff"] for r in all_results],
    "total_flips": len(flips_all),
    "flip_margins": [f["margin"] for f in flips_all],
    "max_flip_margin": max((f["margin"] for f in flips_all), default=None),
    "all_deterministic": all(r["determinism"] for r in all_results),
}, indent=2))
