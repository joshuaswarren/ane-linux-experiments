import json
import mlx.core as mx
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache

MODEL = "~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/0867d98bfb174b042d88461c0e7c97b86b34b381"
calls = {"n": 0}
orig = mx.fast.gated_delta_update_raw
def spy(*a, **k):
    q, kk, v, aa, bb, A_log, dt_bias, state = a[:8]
    if calls["n"] == 0:
        print("raw call shapes/dtypes:")
        for name, t in [("q",q),("k",kk),("v",v),("a",aa),("b",bb),("A_log",A_log),("dt",dt_bias),("state",state)]:
            try:
                print(f"  {name}: shape={t.shape} dtype={t.dtype} rc={t.flags().row_contiguous}")
            except Exception as e:
                print(f"  {name}: type={type(t)} repr={repr(t)[:200]}")
        print("  mask arg:", a[8] if len(a) > 8 else k.get("mask"))
    calls["n"] += 1
    return orig(*a, **k)
mx.fast.gated_delta_update_raw = spy

model, tok = load(MODEL)
text = json.loads(open("/tmp/q38c/qwen38-2b-prompts.jsonl").readline())["text"]
cache = make_prompt_cache(model)
ids = tok.encode(text)
mx.eval(model(mx.array(ids)[None], cache=cache))
n_after_prefill = calls["n"]
tokid = 1
mx.eval(model(mx.array([[tokid]]), cache=cache))
print("raw calls prefill:", n_after_prefill, "after decode1:", calls["n"])
