#!/usr/bin/env python3
"""F1 drift forensics: widen the sign-flip sample (seeds 9-16, both arms)."""
from __future__ import annotations
import numpy as np
from pathlib import Path

CAP = Path("/var/tmp/jw16-conv-place/out3-{arm}-launch/encoder_hidden.npy")
OUT = Path("/var/tmp/f1-drift/probes")

def load(arm):
    return np.load(str(CAP).format(arm=arm)).astype(np.float32)

h_abc = load("abc")
d_j = load("j") - h_abc
d_jkhi = load("jkhi") - h_abc

def sf(shape, seed):
    return np.random.default_rng(seed).choice(
        np.array([-1.0, 1.0], dtype=np.float32), size=shape)

for s in range(9, 17):
    np.save(OUT / f"sfj-{s}.npy", (h_abc + d_j * sf(d_j.shape, 100 + s)).astype(np.float32))
    np.save(OUT / f"sfjkhi-{s}.npy", (h_abc + d_jkhi * sf(d_jkhi.shape, 200 + s)).astype(np.float32))
print("wrote 16 more probe hiddens")
