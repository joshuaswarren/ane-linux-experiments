#!/usr/bin/env python3
"""F1 drift forensics: in-situ island check on REAL encoder activations.

Runs every captured real conv input through its own ANE bundle (the exact
minted record sets the placed E2E consumes) and compares, per site:
  rel(ane vs gpu)   the true in-situ source perturbation of the placement
  rel(ane vs fp32)  the true in-situ device error against the exact reference
  rel(gpu vs fp32)  the GPU fp16 output's own rounding distance
  ulpflip           fraction of elements where ane != gpu at fp16
Plus adversarial-input cases at matched K=1024 reduction depth: the smallest
right singular vector of each weight matrix is tiled across time, so the
exact output is ~0 while partial sums stay large -- any fp16 accumulation in
the engine turns this into a huge relative error; fp32 accumulation stays at
rounding scale. CPU + ANE only; run under the window.
"""
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

_SPEC = importlib.util.spec_from_file_location(
    "conv_lane", "/tmp/conv-lane/conv_lane.py")
cl = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cl)

SOURCE = Path("/var/tmp/EncoderParityAne/encoder-source")
LIBANE = Path("/var/tmp/jw16-oproj-place/libane-strict-fill.so")
BUNDLES = Path("/var/tmp/jw16-conv-place/bundles-conv")
CAP = Path("/var/tmp/f1-drift/cap")
OUT = Path("/var/tmp/f1-drift/in-situ.json")

lib = cl.load_lib(LIBANE)
sites = {}
for name, kind, x4, w4, b, pt, g, W in cl.collect_sites(SOURCE):
    sites[(name, kind)] = (name, kind, x4, w4, b, pt, g, W)

results = {}
worst_ane_gpu = 0.0
for (name, kind) in sorted(sites, key=lambda nk: (nk[1], int(nk[0].rsplit("L", 1)[1]))):
    sname, skind, x4, w4, b, pt, g, W = sites[(name, kind)]
    layer = int(name.rsplit("L", 1)[1])
    stem = f"{kind}-L{layer:02d}"
    anec = BUNDLES / name / "program-0.anec"
    _, y4 = cl.conv_mil(x4, w4, b is not None, pt, g)
    W32 = np.asarray(W, dtype=np.float16).reshape(w4).astype(np.float32)
    b32 = (np.asarray(b, dtype=np.float16).astype(np.float32)
           if b is not None else None)
    x_real = np.load(CAP / f"{stem}-x.npy").astype(np.float16).reshape(x4)
    y_gpu = np.load(CAP / f"{stem}-y.npy").astype(np.float32).reshape(y4)
    ref = cl.ref_conv(x_real.astype(np.float32), W32, b32, pt, g)
    y_ane = cl.run_case(lib, anec, x_real, y4)
    rel = lambda a, bv: float(np.linalg.norm(a - bv) / np.linalg.norm(bv))
    r = {
        "rel_ane_gpu": rel(y_ane, y_gpu),
        "rel_ane_ref": rel(y_ane, ref),
        "rel_gpu_ref": rel(y_gpu, ref),
        "ulpflip": float(np.mean(y_ane.astype(np.float16) != y_gpu.astype(np.float16))),
        "maxabs_ane_gpu": float(np.abs(y_ane - y_gpu).max()),
    }
    worst_ane_gpu = max(worst_ane_gpu, r["rel_ane_gpu"])
    results[name] = r
    print(f"{name}: ane-gpu {r['rel_ane_gpu']:.3e} ane-ref {r['rel_ane_ref']:.3e} "
          f"gpu-ref {r['rel_gpu_ref']:.3e} ulpflip {r['ulpflip']:.3f}", flush=True)

# Adversarial: null-vector inputs at matched reduction depth, real weights.
adv = {}
for layer in (0, 11, 23):
    for kind in ("pw1", "pw2"):
        name = f"island-conv-{kind}-L{layer:02d}"
        sname, skind, x4, w4, b, pt, g, W = sites[(name, kind)]
        anec = BUNDLES / name / "program-0.anec"
        _, y4 = cl.conv_mil(x4, w4, b is not None, pt, g)
        W32 = np.asarray(W, dtype=np.float16).reshape(w4).astype(np.float32)
        b32 = (np.asarray(b, dtype=np.float16).astype(np.float32)
               if b is not None else None)
        _, _, vt = np.linalg.svd(W32.reshape(w4[0], w4[1]), full_matrices=False)
        v = vt[-1]  # smallest right singular vector: exact output ~ 0
        x_adv = np.zeros(x4, dtype=np.float16)
        x_adv[0, :, 0, :] = v[:, None].astype(np.float16)
        ref = cl.ref_conv(x_adv.astype(np.float32), W32, b32, pt, g)
        y_ane = cl.run_case(lib, anec, x_adv, y4)
        adv[name] = {
            "ref_maxabs": float(np.abs(ref).max()),
            "ane_minus_ref_maxabs": float(np.abs(y_ane - ref).max()),
            "ane_minus_ref_l2": float(np.linalg.norm(y_ane - ref)),
            "ref_l2": float(np.linalg.norm(ref)),
        }
        print(f"adv {name}: |ref|max {adv[name]['ref_maxabs']:.3e} "
              f"|ane-ref|max {adv[name]['ane_minus_ref_maxabs']:.3e}", flush=True)

summary = {"sites": results, "worst_rel_ane_gpu": worst_ane_gpu, "adversarial": adv}
OUT.write_text(json.dumps(summary, indent=2) + "\n")
print(f"in-situ probe: {len(results)} sites, worst ane-vs-gpu {worst_ane_gpu:.3e} -> {OUT}")
