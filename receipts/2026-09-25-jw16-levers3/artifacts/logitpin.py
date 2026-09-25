#!/usr/bin/env python3
"""Per-step logprob fingerprint of the contract decode (greedy, 32 new tokens,
10 prompts): the token-id digest only sees argmax flips at near-ties, this sees
any bit of any logit. Records per step: sha256 of the fp32 logprob vector,
argmax, top-2 margin. --dump "p:s,p:s" saves those steps' vectors as .npy."""
import argparse, hashlib, json, os, sys, time
p = argparse.ArgumentParser()
p.add_argument("--model", required=True)
p.add_argument("--prompts", required=True)
p.add_argument("--limit", type=int, default=10)
p.add_argument("--new-tokens", type=int, default=32)
p.add_argument("--passes", type=int, default=1)
p.add_argument("--warmup", type=int, default=1)
p.add_argument("--label", default="")
p.add_argument("--out", required=True)
p.add_argument("--dump", default="", help="prompt:step[,...] logprob vectors to save next to --out")
a = p.parse_args()
import numpy as np
import mlx.core as mx
from mlx_lm import load, generate
from mlx_lm.models.cache import make_prompt_cache
from mlx_lm.generate import generate_step
dump = set()
for item in a.dump.split(","):
    if item.strip():
        pp, ss = item.split(":")
        dump.add((int(pp), int(ss)))
prompts = [json.loads(l)["text"] for l in open(a.prompts) if l.strip()][: a.limit]
model, tok = load(a.model)
for _ in range(a.warmup):
    generate(model, tok, prompt=prompts[0], max_tokens=8, verbose=False)
steps = []
t0 = time.perf_counter()
for ps in range(a.passes):
    for i, text in enumerate(prompts):
        ids = tok.encode(text)
        cache = make_prompt_cache(model)
        for s, (tk, lp) in enumerate(generate_step(mx.array(ids), model, prompt_cache=cache)):
            v = np.asarray(lp.astype(mx.float32)).reshape(-1)
            top2 = np.partition(v, -2)[-2:]
            rec = {"pass": ps, "prompt": i, "step": s, "token": int(tk),
                   "sha": hashlib.sha256(v.tobytes()).hexdigest()[:16],
                   "argmax": int(v.argmax()), "margin": float(top2[1] - top2[0])}
            steps.append(rec)
            if (i, s) in dump:
                np.save(f"{a.out}.p{i}s{s}.npy", v)
            if s + 1 >= a.new_tokens:
                break
wall = time.perf_counter() - t0
digest = hashlib.sha256("".join(r["sha"] for r in steps).encode()).hexdigest()[:8]
ids_digest = hashlib.sha256(json.dumps([r["token"] for r in steps]).encode()).hexdigest()[:8]
json.dump({"label": a.label, "wall_s": round(wall, 2), "logit_digest": digest, "ids_digest": ids_digest,
           "steps": steps}, open(a.out, "w"))
print(f"{a.label:20s} logit_digest={digest} ids_digest={ids_digest} steps={len(steps)} wall={wall:.1f}s "
      f"min_margin={min(r['margin'] for r in steps):.4g} at " +
      str(min(steps, key=lambda r: r['margin'])['prompt']) + ":" + str(min(steps, key=lambda r: r['margin'])['step']),
      flush=True)
