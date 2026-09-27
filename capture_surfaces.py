#!/usr/bin/env python3
"""capture_surfaces: dump the FULL raw ANE input-buffer surfaces (nbytes, not
just the logical view) for every distinct program signature, pre-execute.
Apple's own runtime packing is the ground truth for Linux-side buffers."""
import ctypes
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

os.environ["ANEFORGE_PATH"] = "/tmp/aneforge-capture-fix"
sys.path.insert(0, "/tmp/aneforge-capture-fix")
import aneforge._runtime as rt  # noqa: E402

DUMP = Path("/tmp/jw16-first-submit-ref4/surfaces")
DUMP.mkdir(exist_ok=True)
lib = rt._lib._ensure()
SAVED = set()
EXEC_N = [0]


def full_raw(prog, name):
    ptr, nbytes = ctypes.c_void_p(), ctypes.c_size_t()
    rc = lib.ane_e5rt_program_input_buffer(prog._handle, name.encode(),
                                           ctypes.byref(ptr), ctypes.byref(nbytes))
    if rc != 0 or not ptr.value:
        return None, 0
    return ctypes.string_at(ptr.value, nbytes.value), nbytes.value


orig_execute = rt.Program.execute


def patched_execute(self):
    n = EXEC_N[0]
    EXEC_N[0] += 1
    sig = (tuple(self._inputs), tuple(self._outputs))
    if sig not in SAVED:
        SAVED.add(sig)
        idx = len(SAVED) - 1
        surfaces = {}
        for p in self._inputs:
            raw, nb = full_raw(self, p)
            surfaces[p] = {"nbytes": nb, "sha256_16": hashlib.sha256(raw).hexdigest()[:16] if raw else None}
            if raw:
                (DUMP / f"sig{idx:04d}-in-{p}.bin").write_bytes(raw)
        json.dump({"signature_index": idx, "first_execute_index": n, "inputs": surfaces},
                  open(str(DUMP / f"sig{idx:04d}.json"), "w"), indent=1)
        print(f"sig{idx:04d} (exec {n}): " +
              " ".join(f"{p}:{surfaces[p]['nbytes']}" for p in self._inputs), flush=True)
    return orig_execute(self)


rt.Program.execute = patched_execute

rev = subprocess.run(["git", "-C", "/tmp/aneforge-capture-fix", "rev-parse", "HEAD"],
                     capture_output=True, text=True).stdout.strip()
ref = json.load(open(os.environ["ANEFORGE_CHUNK"]))
pr = ref["prompts"][0]
ids = pr.get("prompt_token_ids") or pr.get("prompt_ids")
from aneforge.qwen35 import load_gguf  # noqa: E402
gguf = os.environ.get("ANEFORGE_GGUF")
m = load_gguf(gguf, resid_scale=1.0)
m.ane_lm_head = False
gen = m.generate(ids, max_new_tokens=1, temperature=0.0, top_p=1.0, top_k=0,
                 batched_prefill=False)
print(f"generated: {gen}", flush=True)
prov = {"aneforge_rev": rev, "distinct_sigs": len(SAVED), "total_executes": EXEC_N[0],
        "host": os.uname().nodename}
json.dump(prov, open(str(DUMP / "provenance.json"), "w"), indent=1)
print("provenance:", json.dumps(prov), flush=True)
