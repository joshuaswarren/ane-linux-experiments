import json
import numpy as np
import mlx.core as mx
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache

MODEL = "~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/0867d98bfb174b042d88461c0e7c97b86b34b381"
calls = {"raw": 0, "plain": 0}
orig_raw = mx.fast.gated_delta_update_raw
orig_plain = mx.fast.gated_delta_update
def raw(*a, **k):
    calls["raw"] += 1
    return orig_raw(*a, **k)
def plain(*a, **k):
    calls["plain"] += 1
    return orig_plain(*a, **k)
mx.fast.gated_delta_update_raw = raw
mx.fast.gated_delta_update = plain

model, tok = load(MODEL)
text = json.loads(open("/tmp/q38c/qwen38-2b-prompts.jsonl").readline())["text"]
cache = make_prompt_cache(model)
ids = tok.encode(text)
logits = model(mx.array(ids)[None], cache=cache)
print("after prefill:", calls)
tokid = int(np.argmax(np.array(logits[0, -1].astype(mx.float32))))
logits = model(mx.array([[tokid]]), cache=cache)
print("after decode1:", calls)
