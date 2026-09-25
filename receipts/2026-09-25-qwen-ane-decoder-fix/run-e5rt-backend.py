#!/usr/bin/env python3
"""Bootstrap for validating staged_qwen_runner.py on macOS: builds the decoder with
ANEForge, hands the chunks to staged_e5rt_backend, then execs the runner's main.
Usage: run-e5rt-backend.py <gguf> [runner args...]
"""
import json
import os
import sys

sys.path.insert(0, os.environ.get("ANEFORGE_PATH", os.path.expanduser("~/src/ane-af-split-wt")))
from aneforge.qwen35 import load_gguf

import staged_e5rt_backend

gguf = sys.argv[sys.argv.index("--gguf") + 1]
m = load_gguf(gguf, resid_scale=1.0)
m.ane_lm_head = False
d = m._decoder(50)
staged_e5rt_backend.setup(d["chunks"])
# in-process cross-check: ANEForge's own step loop vs the runner chain, same programs
ids0 = json.load(open(sys.argv[sys.argv.index("--ref") + 1]))["prompts"][0]["prompt_token_ids"]
_g = m.generate(ids0, max_new_tokens=8, max_len=50, temperature=0.0, top_p=1.0, top_k=0, batched_prefill=False)
print("aneforge p001 first-8:", _g, flush=True)
_g2 = m.generate(ids0, max_new_tokens=8, max_len=50, temperature=0.0, top_p=1.0, top_k=0, batched_prefill=False)
print("aneforge p001 again first-8:", _g2, flush=True)
# the runner needs --gguf/--export/--mode/--ref/--backend-module; argv passes through
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "staged_qwen_runner.py")).read())
