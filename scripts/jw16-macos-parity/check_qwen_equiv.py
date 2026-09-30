#!/usr/bin/env python3
"""Bit-equality gate for the multi-prompt mode: p001+p008 ids, prompt token ids and full logits
vs the per-prompt-process first run (qwen-ane-linux) and repeat run (qwen-ane-repeat)."""
import json
import sys
from pathlib import Path

import numpy as np

NEW = Path(sys.argv[1] if len(sys.argv) > 1 else "/var/tmp/jw16-parity/qwen-ane-equiv")
BASES = {
    "first-run": Path("/var/tmp/jw16-parity/qwen-ane-linux"),
    "repeat": Path("/var/tmp/jw16-parity/qwen-ane-repeat"),
}


def load(d, pid):
    p = json.load(open(d / f"{pid}.json"))["prompts"][0]
    lg = np.load(d / f"{pid}-logits.npy")["run_000"]
    return {**p["runs"][0], "prompt_token_ids": p["prompt_token_ids"]}, lg


fail = False
for pid in ("p001", "p008"):
    r_new, lg_new = load(NEW, pid)
    for label, base in BASES.items():
        r_ref, lg_ref = load(base, pid)
        ids_eq = r_new["generated_ids"] == r_ref["generated_ids"]
        tin_eq = r_new["prompt_token_ids"] == r_ref["prompt_token_ids"]
        lg_eq = bool(np.array_equal(lg_new, lg_ref))
        maxd = float(np.abs(lg_new.astype(np.float64) - lg_ref.astype(np.float64)).max())
        ok = ids_eq and tin_eq and lg_eq
        fail |= not ok
        print(f"{pid} {label}: ids={'EQ' if ids_eq else 'DIFF'} prompt_tokens="
              f"{'EQ' if tin_eq else 'DIFF'} logits={'EQ' if lg_eq else 'DIFF'} max|d|={maxd:g}")
print("EQUIVALENCE:", "PASS" if not fail else "FAIL")
sys.exit(1 if fail else 0)
