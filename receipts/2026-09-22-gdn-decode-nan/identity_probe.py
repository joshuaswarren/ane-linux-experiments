import os
import sys, traceback, mlx.core as mx
from mlx_lm import load
from mlx_lm.models.cache import make_prompt_cache

import glob
MODEL = glob.glob(os.path.expanduser("~/.cache/huggingface/hub/") + "models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*")[0]
REF = "760 1156 369 9859 279 1788 3296 5081 2942 13 353 1144 310 4087 424 2957 321 9077 13 198 248069 271 760 6511 314 9338 369 2972 57590 159034 248046 198"

model, tok = load(MODEL)

def gen(prompt_text, use_chat):
    if use_chat:
        msgs = [{"role": "user", "content": prompt_text}]
        p = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True)
    else:
        p = tok.encode(prompt_text)
    cache = make_prompt_cache(model)
    toks = []
    y = mx.array(p)
    for i in range(32):
        logits = model(y[None] if i == 0 else mx.array([[toks[-1]]]), cache=cache)
        t = mx.argmax(logits[:, -1, :], axis=-1).item()
        toks.append(t)
        y = None
    return toks


cands = [("France " * 16, True), ("The capital of France is a city in Europe.", True), ("France " * 16, False)]
for text, chat in cands:
    tf = gen(text, chat)
    import os
    os.environ["GD_FORCE_OPS"] = "1"
    to = gen(text, chat)
    del os.environ["GD_FORCE_OPS"]
    same = " ".join(map(str, tf)) == " ".join(map(str, to))
    print(("chat " if chat else "raw  ") + repr(text[:30]), "fused==ops:", same)
    print("  fused:", " ".join(map(str, tf)))
    if " ".join(map(str, tf)) == REF:
        print("  MATCH-REF")
print("ID-DONE")
