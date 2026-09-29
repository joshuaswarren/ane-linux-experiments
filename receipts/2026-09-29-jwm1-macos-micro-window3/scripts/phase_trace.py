import json
import statistics as st
import sys
import time

import mlx.core as mx
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache

model, tok = load(sys.argv[1])
ids = mx.array(tok.encode("Answer in one clear sentence: why seasons change on Earth."))[None]
c = make_prompt_cache(model)
mx.eval(model(ids, cache=c))
for i in range(6):
    mx.eval(model(mx.array([[1000 + i]]), cache=c))
rows = []
for i in range(40):
    t0 = time.perf_counter()
    y = model(mx.array([[2000 + i]]), cache=c)
    t1 = time.perf_counter()
    mx.async_eval(y)
    t2 = time.perf_counter()
    mx.eval(y)
    t3 = time.perf_counter()
    rows.append(((t1 - t0) * 1e3, (t2 - t1) * 1e3, (t3 - t2) * 1e3))
m = [st.median(col) for col in zip(*rows[4:])]
print("PHASE", json.dumps({"py_build_ms": round(m[0], 2), "async_eval_return_ms": round(m[1], 2), "wait_ms": round(m[2], 2), "total_ms": round(sum(m), 2)}))
