#!/usr/bin/env python3
"""capture_all: per-program Apple references for the whole staged series.

For EVERY Program.execute: snapshot ALL input port views PRE-execute,
outputs POST-execute, re-read inputs post-execute (mutation check), save
the FIRST occurrence of each (input-ports, output-ports) signature.
Covers embed, state block, and every decoder program class in one run.

Output: /tmp/jw16-first-submit-ref4/ — sigNNNN.{npz,json} + provenance.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

os.environ["ANEFORGE_PATH"] = "/tmp/aneforge-capture-fix"
sys.path.insert(0, "/tmp/aneforge-capture-fix")
import aneforge._runtime as rt  # noqa: E402

DUMP = Path("/tmp/jw16-first-submit-ref4")
DUMP.mkdir(exist_ok=True)
SAVED_SIGS = {}
EXEC_N = [0]


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def snap(prog, ports):
    out = {}
    for p in ports:
        try:
            out[p] = np.ascontiguousarray(prog.input_view(p), dtype=np.float16)
        except Exception:
            out[p] = None
    return out


orig_execute = rt.Program.execute


def patched_execute(self):
    n = EXEC_N[0]
    EXEC_N[0] += 1
    ins, outs = list(self._inputs), list(self._outputs)
    sig = (tuple(ins), tuple(outs))
    pre = snap(self, ins)
    result = orig_execute(self)
    post = snap(self, ins)
    mutated = {}
    for p in ins:
        a, b = pre.get(p), post.get(p)
        if a is not None and b is not None and not bool(
                (a.view(np.uint16) == b.view(np.uint16)).all()):
            mutated[p] = int(np.count_nonzero(a.view(np.uint16) != b.view(np.uint16)))
    if sig not in SAVED_SIGS:
        SAVED_SIGS[sig] = len(SAVED_SIGS)
        idx = SAVED_SIGS[sig]
        out_arrs = {}
        for p in outs:
            try:
                out_arrs[p] = np.ascontiguousarray(self.output_view(p), dtype=np.float16)
            except RuntimeError:
                out_arrs[p] = None
        meta = {
            "signature_index": idx,
            "first_execute_index": n,
            "input_ports": {p: list(v.shape) if v is not None else None
                            for p, v in pre.items()},
            "input_sha256_16": {p: (sha(v.tobytes()) if v is not None else None)
                                for p, v in pre.items()},
            "input_mutated_in_execute": mutated,
            "output_ports": {p: list(v.shape) if v is not None else None
                             for p, v in out_arrs.items()},
            "output_sha256_16": {p: (sha(v.tobytes()) if v is not None else None)
                                 for p, v in out_arrs.items()},
        }
        payload = {f"in__{p}": v for p, v in pre.items() if v is not None}
        payload.update({f"out__{p}": v for p, v in out_arrs.items() if v is not None})
        np.savez(str(DUMP / f"sig{idx:04d}.npz"), **payload)
        json.dump(meta, open(str(DUMP / f"sig{idx:04d}.json"), "w"), indent=1)
        print(f"saved sig{idx:04d} (exec {n}): in={list(ins)} out={list(outs)} "
              f"mutated={mutated}", flush=True)
    return result


rt.Program.execute = patched_execute

rev = subprocess.run(["git", "-C", "/tmp/aneforge-capture-fix", "rev-parse", "HEAD"],
                     capture_output=True, text=True).stdout.strip()
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
prov = {"aneforge_rev": rev, "gguf": {"path": gguf, "bytes": os.stat(gguf).st_size},
        "prompt_ids_len": len(ids), "distinct_program_signatures": len(SAVED_SIGS),
        "total_executes": EXEC_N[0], "host": os.uname().nodename}
json.dump(prov, open(str(DUMP / "provenance.json"), "w"), indent=1)
print("provenance:", json.dumps(prov), flush=True)
