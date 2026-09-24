#!/usr/bin/env python3
"""Instrument scaled_dot_product_attention + SdpaDecodeNativeBF16 dispatch
counts inside one real generate_step loop. Mirror of jw16's
sdpa_token_counts.py but adapted for the M1 batchbudget/umalimit1
torchpath.
"""
import argparse, json, os, time, sys

p = argparse.ArgumentParser()
p.add_argument("--model", required=True)
p.add_argument("--prompts", required=True)
p.add_argument("--new-tokens", type=int, default=32)
p.add_argument("--out", required=True)
a = p.parse_args()

import mlx.core as mx
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache
from mlx_lm.generate import generate_step

model, tok = load(a.model)
model.eval()

# Hook SDPA + the underlying fast kernel if exposed
sdpa_calls = 0
sdpa_orig = mx.fast.scaled_dot_product_attention
def sdpa_wrap(*args, **kwargs):
    global sdpa_calls
    sdpa_calls += 1
    return sdpa_orig(*args, **kwargs)
mx.fast.scaled_product_attention = sdpa_wrap  # not used; just bookkeeping
# real override below
mx.fast.scaled_dot_product_attention = sdpa_wrap

# Hook the compute layer so we can count SdpaDecodeNativeBF16 dispatches.
# Easiest path: count via a tag on the captured args (shapes).
captured_shapes = []
orig_sdpa_kwargs = {}

prompts = [json.loads(l)["text"] for l in open(a.prompts) if l.strip()]
prompt = prompts[0][: a.new_tokens * 8]
ids = tok.encode(prompt)
cache = make_prompt_cache(model)

# Drain prompt + decode 32 tokens under the hook
it = generate_step(mx.array(ids), model, prompt_cache=cache)
next(it)  # prefill
for _ in range(a.new_tokens):
    out = next(it)
    mx.eval(out[0])

# Unhook
mx.fast.scaled_dot_product_attention = sdpa_orig

with open(a.out, "w") as f:
    json.dump({
        "sdpa_dispatches": sdpa_calls,
        "n_decode_tokens": a.new_tokens,
        "sdpa_dispatches_per_tok": sdpa_calls / a.new_tokens,
    }, f, indent=1)
print(f"sdpa dispatches: {sdpa_calls} ({sdpa_calls / a.new_tokens:.2f}/tok)")
