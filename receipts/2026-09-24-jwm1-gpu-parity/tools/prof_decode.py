#!/usr/bin/env python3
"""Profile one decode token + one prefill pass on the installed mlx-omarchy
path, emitting CLOCK_MONOTONIC host markers around them. Mirrors
benchmarks/qwen38-mlx-bench.py exactly: load, make_prompt_cache, greedy
generate_step with mx.eval per token.

Mirrors /var/tmp/vprof/prof_decode.py (batchbudget lane) but targets the
contract corpus prompt 0 with 32 decode tokens after a 12-token prompt, so
the same decode regime as the contract bench.
"""
import argparse, json, os, time, sys
p = argparse.ArgumentParser()
p.add_argument("--model", required=True)
p.add_argument("--prompts", required=True)
p.add_argument("--prompt-idx", type=int, default=0)
p.add_argument("--new-tokens", type=int, default=32)
p.add_argument("--markers", required=True)
a = p.parse_args()

mf = open(a.markers, "w")
def mark(phase):
    mf.write(json.dumps({"t": time.monotonic_ns(), "p": phase}) + "\n")
    mf.flush()

import mlx.core as mx
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache
from mlx_lm.generate import generate_step

model, tok = load(a.model)
model.eval()
prompts = [json.loads(l)["text"] for l in open(a.prompts) if l.strip()]
prompt = prompts[a.prompt_idx][: a.new_tokens * 8]  # ~12-token regime
ids = tok.encode(prompt)
mark("model_loaded")
cache = make_prompt_cache(model)
it = generate_step(mx.array(ids), model, prompt_cache=cache)
mark("prefill_start")
# drain first iteration (the prompt)
token0 = next(it)[0]
mx.eval(token0)
mark("prefill_done")
# now 32 decode iterations
for i in range(a.new_tokens):
    t = next(it)[0]
    mx.eval(t)
    mark(f"decode_{i}")
mark("done")
mf.close()
