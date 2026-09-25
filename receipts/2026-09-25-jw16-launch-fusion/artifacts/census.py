#!/usr/bin/env python3
"""Per-token dispatch census: trace every compute dispatch for a few mid-run
decode tokens (MLX_OMARCHY_TRACE_DISPATCH is read per dispatch, so toggling the
env var in-process brackets exactly the token steps we want)."""
import json, os, sys, time
sys.path.insert(0, os.path.expanduser("~/bench-scripts"))
import mlx.core as mx
from mlx_lm import load, generate
from mlx_lm.models.cache import make_prompt_cache
from mlx_lm.generate import generate_step

model_path, prompts_path, out_path = sys.argv[1:4]
ntrace = int(sys.argv[4]) if len(sys.argv) > 4 else 4
prompts = [json.loads(l)["text"] for l in open(prompts_path) if l.strip()]
model, tok = load(model_path)
print("MODEL_TREE_BEGIN", file=sys.stderr)
for name, mod in model.named_modules():
    ws = {k: (list(v.shape), str(v.dtype)) for k, v in mod.parameters().items() if hasattr(v, "shape")}
    print(f"MOD {name} {type(mod).__name__} {json.dumps(ws)}", file=sys.stderr)
print("MODEL_TREE_END", file=sys.stderr)
generate(model, tok, prompt=prompts[0], max_tokens=8, verbose=False)
ids = tok.encode(prompts[0])
cache = make_prompt_cache(model)
it = generate_step(mx.array(ids), model, prompt_cache=cache)
first = next(it)[0]
mx.eval(first)
out = [int(first)]
# two untraced tokens to settle, then ntrace traced steps
for k, (tk, _) in enumerate(it):
    if k == 2:
        os.environ["MLX_OMARCHY_TRACE_DISPATCH"] = "1"
    if 2 <= k < 2 + ntrace:
        print(f"TOKEN_BEGIN {k}", file=sys.stderr); sys.stderr.flush()
    out.append(int(tk))
    mx.eval(tk)
    if 2 <= k < 2 + ntrace:
        print(f"TOKEN_END {k}", file=sys.stderr); sys.stderr.flush()
    if k == 1 + ntrace:
        os.environ.pop("MLX_OMARCHY_TRACE_DISPATCH", None)
    if len(out) >= 12:
        break
print("OUT", out, file=sys.stderr)
