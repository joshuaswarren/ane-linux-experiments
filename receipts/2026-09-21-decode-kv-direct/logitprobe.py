import sys
import mlx.core as mx
from mlx_lm.utils import load
path = sys.argv[1]
model, tok = load(path)
ids = tok.encode("What is the capital of France? "*4)
x = mx.array([ids])
from mlx_lm.models import cache as lmcache
cache = lmcache.make_prompt_cache(model)
out = model(x, cache=cache)
print("prefill top5:", mx.argmax(out[0,-1,:]).item())
nxt = mx.argmax(out[:,-1,:],axis=-1)
toks=[int(nxt.item())]
for i in range(4):
    out = model(nxt[:,None], cache=cache)
    nxt = mx.argmax(out[:,-1,:],axis=-1)
    toks.append(int(nxt.item()))
print("first5:", toks)
# probe rope outputs directly inside layer? quick: check cache arrays after step
