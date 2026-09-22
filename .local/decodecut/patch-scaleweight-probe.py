#!/usr/bin/env python3
"""[PROBE] Fold GDN/full-attn q/k scale muls into rms_norm weight.
Numerically NOT identical (different rounding order) - dispatch-count probe only.
Usage: python patch-scaleweight-probe.py /path/to/venv"""
import glob, sys

old = """        q = (inv_scale**2) * mx.fast.rms_norm(q, None, 1e-6)
        k = inv_scale * mx.fast.rms_norm(k, None, 1e-6)"""
new = """        q = mx.fast.rms_norm(q, mx.full((q.shape[-1],), inv_scale**2, mx.bfloat16), 1e-6)
        k = mx.fast.rms_norm(k, mx.full((k.shape[-1],), inv_scale, mx.bfloat16), 1e-6)"""
hits = glob.glob(sys.argv[1].rstrip("/") + "/lib/python3*/site-packages/mlx_lm/models/qwen3_5.py")
t = open(hits[0]).read()
if old not in t:
    sys.exit("pattern not found (attention scale lines)")
open(hits[0], "w").write(t.replace(old, new))
print("patched (PROBE):", hits[0])
