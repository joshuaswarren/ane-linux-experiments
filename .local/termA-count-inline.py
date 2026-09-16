#!/usr/bin/env python3
"""Per-token trace counters around a minimal greedy decode loop."""
import ctypes, json, pathlib, sys, os
os.environ["MLX_DISABLE_COMPILE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
import mlx.core as mx
from mlx_lm import load

class Snapshot(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in (
        "gpu_primitive_dispatches", "vk_submissions",
        "vk_buffer_copies", "vk_buffer_fills", "vk_compute_dispatches",
        "omarchy_finalize_calls", "commit_calls_with_work",
        "commit_calls_noop")]

so = pathlib.Path(mx.__file__).parent / "lib" / "libmlx.so"
lib = ctypes.CDLL(str(so))
lib.mlx_omarchy_trace_snapshot.argtypes = [ctypes.POINTER(Snapshot)]
snap = Snapshot()

def read():
    lib.mlx_omarchy_trace_snapshot(ctypes.byref(snap))
    return {n: getattr(snap, n) for n, _ in Snapshot._fields_}

model, tok = load("/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx")
text = open(sys.argv[1]).read()
prompt = mx.array(tok.apply_chat_template(
    [{"role": "user", "content": text}], add_generation_prompt=True, tokenize=True))[None]

cache = None
# 4 warmup tokens, then 3 measured
tokens = []
for i in range(7):
    before = read()
    logits = model(prompt if not tokens else mx.array([[tokens[-1]]]), cache=cache)
    t = mx.argmax(logits[0, -1, :])
    mx.eval(t)
    tokens.append(t)
    after = read()
    tag = "warm" if i < 4 else f"tok{i-4}"
    print(tag, {k: after[k] - before[k] for k in after if after[k] != before[k]})
