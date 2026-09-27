#!/usr/bin/env python3
"""capture_perturb: Apple-side element-group consumption probe for prog_002.

For each (port, group): at the FIRST prog_002-class execute, add +4.0 to
the group's elements of that input port via the writable input_view,
execute, save all outputs. Diff vs the unperturbed baseline run reveals
which output elements each input group feeds.

12 configs = quarters of [16,128] for t0/t2/t7 (4 each) + t20 column
planes (3) done as first-quarter perturbations of the compact buffer.
"""
import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

os.environ["ANEFORGE_PATH"] = "/tmp/aneforge-capture-fix"
sys.path.insert(0, "/tmp/aneforge-capture-fix")
import aneforge._runtime as rt  # noqa: E402

DUMP = Path("/tmp/jw16-first-submit-ref4/perturb")
DUMP.mkdir(exist_ok=True)
lib = rt._lib._ensure()

CFG = os.environ["PERTURB_CFG"]  # e.g. "t0:0", "t20:2"
PORT, GROUP = CFG.split(":")
GROUP = int(GROUP)

TARGET_SIG = (["t7", "t2", "t0", "t20"], ["t15", "t31", "t35", "t37", "t41", "t50", "t52", "t53"])
HIT = [False]
EXEC_N = [0]

orig_execute = rt.Program.execute


def patched_execute(self):
    n = EXEC_N[0]
    EXEC_N[0] += 1
    is_target = (list(self._inputs) == TARGET_SIG[0] and list(self._outputs) == TARGET_SIG[1])
    if is_target and not HIT[0]:
        HIT[0] = True
        view = self.input_view(PORT).reshape(-1)
        g = view.size // 4
        sl = slice(GROUP * g, (GROUP + 1) * g)
        before = view[sl].copy()
        view[sl] = (view[sl].astype(np.float32) + 4.0).astype(np.float16)
        print(f"perturbed {PORT} group {GROUP} ({g} elements) at exec {n}", flush=True)
    result = orig_execute(self)
    if is_target and HIT[0] and result is not None:
        outs = {}
        for p in self._outputs:
            try:
                outs[p] = np.ascontiguousarray(self.output_view(p), dtype=np.float16)
            except RuntimeError:
                outs[p] = None
        np.savez(str(DUMP / f"perturb-{PORT}-g{GROUP}.npz"),
                 **{f"out__{p}": v for p, v in outs.items() if v is not None})
        print(f"saved outputs for {PORT} g{GROUP}", flush=True)
    return result


rt.Program.execute = patched_execute

gguf = os.environ["ANEFORGE_GGUF"]
ref = json.load(open(os.environ["ANEFORGE_CHUNK"]))
pr = ref["prompts"][0]
ids = pr.get("prompt_token_ids") or pr.get("prompt_ids")
from aneforge.qwen35 import load_gguf  # noqa: E402
m = load_gguf(gguf, resid_scale=1.0)
m.ane_lm_head = False
gen = m.generate(ids, max_new_tokens=1, temperature=0.0, top_p=1.0, top_k=0,
                 batched_prefill=False)
print(f"generated: {gen}", flush=True)
