#!/usr/bin/env python3
"""Teacher-forced prefill logits digest for Qwen3.8 (mlx-lm), the correctness gate for
prefill kernels (T>=64 GDN chunk route, long causal SDPA) that the bench's ordered_records
digest never reaches (its records are 32 tokens after one short chat prompt).

For each T: ids = the 100-prompt corpus joined and repeated to T tokens (the bench's
pure-prefill construction over the whole corpus), one forward with a fresh prompt cache
(the bench's call shape), then
  sha256 over the bf16 bits of logits[0, :, :]          (bit-exactness gate)
  per-position argmax, top-1 and top-2 logit (f32)      (contract comparison)
  raw bf16 rows at positions 0, every 16th, and the last 32   (max |delta| checks)
saved to OUT_DIR/T{T}.npz (OUT_DIR "-" skips the npz); summary JSON on stdout with
"finite" = every logit of every position finite, exit status 3 otherwise (the gate: a 12-token chat prompt never
reaches the T>=64 GDN chunk route, which produced NaN at every position on 2026-09-29).
usage: prefill_logits_digest.py MODEL_DIR OUT_DIR T [T ...]
"""
import hashlib
import json
import os
import sys

import mlx.core as mx
import numpy as np
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache

model_dir, out_dir = sys.argv[1], sys.argv[2]
Ts = [int(t) for t in sys.argv[3:]] or [512, 1024, 2048]
save = out_dir != "-"
if save:
    os.makedirs(out_dir, exist_ok=True)
prompts_path = os.path.expanduser("~/bench-scripts/qwen38-2b-prompts.jsonl")
prompts = [json.loads(l)["text"] for l in open(prompts_path) if l.strip()]
model, tok = load(model_dir)
text = " ".join(prompts)
base = tok.encode(text)
summary = {"model": model_dir, "env": {k: v for k, v in os.environ.items()
                                        if k.startswith(("MLX_OMARCHY", "VK_", "HK_", "AGX_"))}}
for T in Ts:
    ids = list(base)
    while len(ids) < T:
        ids = ids + tok.encode(" " + text)
    ids = ids[:T]
    cache = make_prompt_cache(model)
    logits = model(mx.array(ids)[None], cache=cache)[0]
    top2 = mx.topk(logits.astype(mx.float32), 2, axis=-1)
    top2 = mx.sort(top2, axis=-1)
    am = mx.argmax(logits, axis=-1)
    bits = logits.view(mx.uint16)
    row_finite = mx.all(mx.isfinite(logits), axis=-1)
    mx.eval(bits, top2, am, row_finite)
    row_finite = np.array(row_finite)
    bits_np = np.array(bits)
    digest = hashlib.sha256(bits_np.tobytes()).hexdigest()
    rows = sorted(set(list(range(0, T, 16)) + list(range(max(0, T - 32), T))))
    if save:
        np.savez(os.path.join(out_dir, f"T{T}.npz"),
                 argmax=np.array(am).astype(np.int32),
                 top1=np.array(top2[:, 1]), top2=np.array(top2[:, 0]),
                 rows=np.array(rows, dtype=np.int32), row_bits=bits_np[rows])
    summary[f"T{T}"] = {"logits_sha256": digest, "ids_sha256":
                        hashlib.sha256(np.array(ids, dtype=np.int32).tobytes()).hexdigest(),
                        "argmax_sha256": hashlib.sha256(np.array(am).astype(np.int32).tobytes()).hexdigest(),
                        "finite": bool(row_finite.all()),
                        "nonfinite_positions": int((~row_finite).sum()),
                        "first_nonfinite_position": int(np.argmin(row_finite)) if not row_finite.all() else None}
    print(f"T={T} logits_sha256={digest} finite={bool(row_finite.all())}", file=sys.stderr, flush=True)
print(json.dumps(summary, indent=1))
# Exit 3 when any logit is non-finite: callers gate on the exit status.
sys.exit(0 if all(summary[f"T{T}"]["finite"] for T in Ts) else 3)
