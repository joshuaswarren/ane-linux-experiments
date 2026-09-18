#!/usr/bin/env python3
"""F1 drift forensics: build decode-probe hidden files from the bisect arms.

Pure CPU, no GPU, no ANE: subtracts the certified ABC hidden (out3-abc-launch)
from each placed-arm hidden and writes perturbed copies of the ABC hidden:
  probe-{arm}.npy       the arm's own hidden (transfer control)
  sfj-{s}.npy           h_abc + signflip_s(d_j)        (J-magnitude, independent)
  sfjkhi-{s}.npy        h_abc + signflip_s(d_jkhi)    (JKHI-magnitude, independent)
  sfj-t05-{s}.npy       h_abc + 0.5 * signflip_s(d_j)
  sfj-t2-{s}.npy        h_abc + 2.0 * signflip_s(d_j)
Sign-flipping preserves the drift spectrum exactly while decorrelating the
direction, so every draw is an independent realization at that arm's magnitude.
"""
from __future__ import annotations
import numpy as np
from pathlib import Path

CAP = Path("/var/tmp/jw16-conv-place/out3-{arm}-launch/encoder_hidden.npy")
OUT = Path("/var/tmp/f1-drift/probes")
OUT.mkdir(parents=True, exist_ok=True)

def load(arm: str) -> np.ndarray:
    return np.load(str(CAP).format(arm=arm)).astype(np.float32)

h_abc = load("abc")
h = {a: load(a) for a in ("j", "jkh", "jkhi")}
d = {a: h[a] - h_abc for a in h}

def save(name: str, arr: np.ndarray) -> None:
    np.save(OUT / f"{name}.npy", arr.astype(np.float32))

save("probe-abc", h_abc)
for a in h:
    save(f"probe-{a}", h[a])

def sf(shape, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).choice(
        np.array([-1.0, 1.0], dtype=np.float32), size=shape)

for s in range(1, 9):
    save(f"sfj-{s}", h_abc + d["j"] * sf(d["j"].shape, 100 + s))
    save(f"sfjkhi-{s}", h_abc + d["jkhi"] * sf(d["jkhi"].shape, 200 + s))
for s in range(1, 5):
    save(f"sfj-t05-{s}", h_abc + 0.5 * d["j"] * sf(d["j"].shape, 300 + s))
    save(f"sfj-t2-{s}", h_abc + 2.0 * d["j"] * sf(d["j"].shape, 400 + s))

print(f"wrote {len(list(OUT.glob('*.npy')))} probe hiddens to {OUT}")
