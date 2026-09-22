import sys, time, os, glob
import mlx.core as mx
from mlx_lm.utils import load
from mlx_lm.models.cache import make_prompt_cache

snap = glob.glob(os.path.expanduser(
    "~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*"))[0]
model, tok = load(snap)

text = open(sys.argv[1]).read()
ids = tok.encode(text)[:512]
if len(ids) < 512:
    ids = ids + ids[:512 - len(ids)]

# warmup (untraced effect is fine; envs are on the whole process)
cache = make_prompt_cache(model)
mx.eval(model(mx.array(ids)[None], cache=cache))

t0 = time.perf_counter()
cache = make_prompt_cache(model)
mx.eval(model(mx.array(ids)[None], cache=cache))
dt = time.perf_counter() - t0
print("PREFILL wall_s=%.4f tok_per_s=%.2f" % (dt, len(ids) / dt), file=sys.stderr)
