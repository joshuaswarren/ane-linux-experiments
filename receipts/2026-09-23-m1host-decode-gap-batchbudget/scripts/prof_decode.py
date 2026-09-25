#!/usr/bin/env python3
"""Profile the contract decode path (mlx_lm generate_step, greedy) with
host-side CLOCK_MONOTONIC markers for profile_analyze.py.

Mirrors benchmarks/qwen38-mlx-bench.py exactly: load, make_prompt_cache,
generate_step iterator consumed with mx.eval per token. Run with
MLX_DISABLE_COMPILE=1 MLX_OMARCHY_GPU_PROFILE=<path> set.
"""
import argparse, json, time

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
prompts = [json.loads(l)["text"] for l in open(a.prompts) if l.strip()]
ids = tok.encode(prompts[a.prompt_idx])
mark("load_done")

cache = make_prompt_cache(model)
mark("prefill_start")
it = generate_step(mx.array(ids), model, prompt_cache=cache)
first = next(it)[0]
mx.eval(first)
mark("prefill_done")
mark("decode_start")

n = 1
t0 = time.monotonic_ns()
for tk, _ in it:
    n += 1
    mx.eval(tk)
    mark("tok")
    if n >= a.new_tokens:
        break
dt = time.monotonic_ns() - t0
mark("decode_done")
print(f"[prof_decode] prompt_tokens={len(ids)} tokens={n} "
      f"decode_ms={dt / 1e6:.2f} decode_tok_s={(n - 1) / (dt / 1e9):.2f}")
