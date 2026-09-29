import json, sys, time, statistics as st
import mlx.core as mx
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache
M = sys.argv[1]
model, tok = load(M)
text = " ".join(json.loads(l)["text"] for l in open(sys.argv[2]) if l.strip())
ids_all = tok.encode(text)
lens = [1, 2, 4, 8, 11, 16, 32, 64, 128, 256, 512]


def fwd(L):
    ids = mx.array(ids_all[:L])[None]
    cache = make_prompt_cache(model)
    t = time.perf_counter()
    mx.eval(model(ids, cache=cache))
    return (time.perf_counter() - t) * 1000


for L in lens[:3]:
    fwd(L)
out = {}
for L in lens:
    fwd(L)
    v = [fwd(L) for _ in range(10)]
    out[L] = {"median_ms": round(st.median(v), 1), "min_ms": round(min(v), 1)}
    print(L, out[L], flush=True)
print(json.dumps(out))
