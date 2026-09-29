import json
import statistics as st
import sys
import time

import mlx.core as mx
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache

model, tok = load(sys.argv[1])
ids = mx.array(tok.encode("Answer in one clear sentence: why seasons change on Earth."))[None]
out = {}


def one(cache, t):
    s = time.perf_counter()
    y = model(mx.array([[t]]), cache=cache)
    mx.eval(y)
    return (time.perf_counter() - s) * 1e3


# (a) fresh cache, 1 token, cold->warm
fresh = []
for _ in range(10):
    c = make_prompt_cache(model)
    fresh.append(one(c, 1000))
out["fresh_cache_L1_ms"] = round(st.median(fresh[2:]), 1)
# (b) continuing cache after a prompt prefill, per-token synchronous forward
c = make_prompt_cache(model)
mx.eval(model(ids, cache=c))
for _ in range(4):
    one(c, 1000)
seq = [one(c, 1000 + i) for i in range(48)]
out["cont_cache_sync_ms_med"] = round(st.median(seq), 1)
out["cont_cache_sync_ms_min"] = round(min(seq), 1)
# (c) pipelined: build next token graph before waiting on the previous (async_eval)
c = make_prompt_cache(model)
mx.eval(model(ids, cache=c))
t = 1000
y = model(mx.array([[t]]), cache=c)
mx.async_eval(y)
ts = []
last = time.perf_counter()
for i in range(48):
    y2 = model(mx.array([[1001 + i]]), cache=c)
    mx.async_eval(y2)
    mx.eval(y)
    now = time.perf_counter()
    ts.append((now - last) * 1e3)
    last = now
    y = y2
mx.eval(y)
out["pipelined_ms_med"] = round(st.median(ts[4:]), 1)
print("DSYNC", json.dumps(out))
