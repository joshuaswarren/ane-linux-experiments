import argparse, glob, os, sys, time
import mlx.core as mx
from mlx_lm.utils import load
from mlx_lm.models.cache import make_prompt_cache

ap = argparse.ArgumentParser()
ap.add_argument("--prompt", default="France")
ap.add_argument("--rep", type=int, default=16)
ap.add_argument("--max-tokens", type=int, default=32)
a = ap.parse_args()
snap = glob.glob(os.path.expanduser(
    "~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*"))[0]
model, tok = load(snap)
ids = tok.encode(a.prompt) * a.rep
print("PROMPT tok=", len(ids), file=sys.stderr)

def fresh():
    cache = make_prompt_cache(model)
    mx.eval(model(mx.array(ids)[None], cache=cache))
    return cache

fresh()  # warmup
t0 = time.perf_counter(); fresh(); prefill = time.perf_counter() - t0

cache = fresh()
toks = []
t0 = time.perf_counter()
last = mx.argmax(model(mx.array(ids)[None], cache=cache), axis=-1)[:, -1:]
mx.eval(last)
for i in range(a.max_tokens):
    toks.append(int(last.item()))
    last = mx.argmax(model(last, cache=cache), axis=-1)
    mx.eval(last)
decode = time.perf_counter() - t0
print("PREFILL wall_s=%.4f tok_per_s=%.2f" % (prefill, len(ids) / prefill), file=sys.stderr)
print("DECODE wall_s=%.4f tok_per_s=%.2f n=%d" % (decode, a.max_tokens / decode, a.max_tokens), file=sys.stderr)
print("TOKENS", " ".join(map(str, toks)))
