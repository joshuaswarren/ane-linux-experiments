#!/usr/bin/env python3
"""Mint h14g/h13 ANE oracle libraries for the three t602x linear geometries.

Runs on macOS with ANEForge (drives Apple's private Espresso e5rt compiler —
the same compiler backend behind ANECompiler/ANECompilerService — with
TargetArchitecture passed as a custom ANE-compiler option).

Weights are INDEX-ENCODED (never uniform): every adjacent fp16 PAIR carries a
28-bit pair watermark:
    even half bits = 0x0400 + (p & 0x3FFF)          (positive normal)
    odd  half bits = 0x8400 + ((p >> 14) & 0x3FFF)  (negative normal)
so the emitted permutation is readable offline:
    p = (even - 0x0400) | ((odd - 0x8400) << 14)   (= source pair index)

Usage: mint_aneforge.py OUT_DIR [GEOM ...]
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/Users/joshuawarren/src/ANEForge")
import aneforge as af                                    # noqa: E402
from aneforge._compile import _lower_fused_to_dir        # noqa: E402
from aneforge import _runtime                            # noqa: E402

GEOMETRIES = {"oproj": (375, 1024, 1024), "mm1": (375, 1024, 4096),
              "mm2": (375, 4096, 1024)}
ARCHES = ["h14g", "h13"]


def watermark_halves(n_halves: int) -> np.ndarray:
    pairs = n_halves // 2
    idx = np.arange(pairs, dtype=np.uint32)
    even = (0x0400 + (idx & 0x3FFF)).astype(np.uint16)
    odd = (0x8400 + ((idx >> 14) & 0x3FFF)).astype(np.uint16)
    bits = np.empty(pairs * 2, dtype=np.uint16)
    bits[0::2], bits[1::2] = even, odd
    return bits.view(np.float16)


def main() -> None:
    out_root = Path(sys.argv[1])
    geoms = sys.argv[2:] or list(GEOMETRIES)
    summary = {}
    for name in geoms:
        m, k, n = GEOMETRIES[name]
        W = np.ascontiguousarray(watermark_halves(k * n).reshape(n, k))
        x = af.input((m, k))
        y = x.linear(W)
        d = out_root / name
        dd = _lower_fused_to_dir(y, build_dir=d)
        rec = {"geometry": name, "M": m, "K": k, "N": n,
               "weight_halves": k * n,
               "weight_source": "pair28 watermark (see module docstring)",
               "linear_W_shape": [n, k],
               "mil": str(dd / "model.mil"),
               "compiles": {}}
        for arch in ARCHES:
            cache = dd / f"cache_{arch}"
            rc = _runtime.compile_check(dd / "model.mil", str(cache),
                                        custom_ane_options=f"TargetArchitecture={arch}")
            files = sorted(str(p.relative_to(cache)) for p in cache.rglob("*")
                           if p.is_file()) if cache.is_dir() else []
            rec["compiles"][arch] = {"rc": rc, "cache_dir": str(cache),
                                     "files": files[:40]}
            print(f"[mint] {name} {arch}: rc={rc} files={len(files)}", flush=True)
        summary[name] = rec
    (out_root / "mint-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("wrote", out_root / "mint-summary.json")


if __name__ == "__main__":
    main()
