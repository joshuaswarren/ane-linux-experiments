#!/usr/bin/env python3
"""Locate the first free-running divergence: ops stream vs fused stream."""
import json
import os
import sys

import mlx.core as mx
from mlx_lm import load

MODEL = sys.argv[1]
PROMPTS = sys.argv[2]
model, tokenizer = load(MODEL)
rows = [json.loads(l) for l in open(PROMPTS)]
prompt = tokenizer.encode(rows[0].get("text"))[:512]

def greedy(n):
    out = list(prompt)
    for step in range(n):
        logits = model(mx.array([out]))
        mx.eval(logits)
        out.append(int(mx.argmax(logits[0, -1]).item()))
    return out

os.environ["GDN_DISABLE_FAST"] = "1"
ops_stream = greedy(96)
os.environ["GDN_DISABLE_FAST"] = "0"
fused_stream = greedy(96)
for i, (a, b) in enumerate(zip(ops_stream, fused_stream)):
    if a != b:
        print(json.dumps({"first_divergence_index": i,
                          "in_decode": i >= len(prompt),
                          "ops_tok": a, "fused_tok": b}))
        break
else:
    print(json.dumps({"first_divergence_index": None}))
