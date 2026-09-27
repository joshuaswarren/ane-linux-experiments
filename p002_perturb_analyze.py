#!/usr/bin/env python3
"""Analyze perturbation battery: per config, which outputs changed and by how
much vs the sig0002 baseline (unperturbed)."""
import sys
from pathlib import Path

import numpy as np

D = Path("/tmp/jw16-first-submit-ref4")
base = np.load(str(D / "sig0002.npz"))
BASE = {p: base[f"out__{p}"] for p in ("t15", "t31", "t35", "t37", "t41", "t50", "t52", "t53")}

for npz in sorted(D.glob("perturb-*.npz")):
    name = npz.stem.replace("perturb-", "")
    z = np.load(str(npz))
    parts = []
    for p in BASE:
        if f"out__{p}" not in z.files:
            continue
        got = z[f"out__{p}"].reshape(-1)
        ref = BASE[p].reshape(-1)
        nd = int(np.count_nonzero(got.view(np.uint16) != ref.view(np.uint16)))
        nchange_input = "?"
        parts.append(f"{p}:{nd}/{ref.size}")
    print(f"{name}: " + " ".join(parts), flush=True)
