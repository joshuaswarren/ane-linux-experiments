#!/usr/bin/env python3
"""K-sweep: bracket the family-dependent segmentation threshold (edge-k16).

Sweeps K in {8,16,24,32,48,64} at fixed M=375, N=1024, pair28 watermark
weights, canonical workroot (see mint_aneforge.py methods rule). Reports the
number of compiled program bundles per (K, arch) — >1 bundle means the
segmenter split the graph.

Run on BOTH hosts; compare per-family bundle counts.
"""
import json
import sys
from pathlib import Path

import numpy as np

for p in ("/tmp/t6021-mint", "/Users/joshuawarren/src/ANEForge"):
    if Path(p).is_dir():
        sys.path.insert(0, p)
        break
from aneforge._compile import _lower_fused_to_dir        # noqa: E402
from aneforge import _runtime                            # noqa: E402
from mint_aneforge import CANONICAL_WORKROOT, watermark_halves  # noqa: E402

M, N = 375, 1024
KS = [8, 16, 24, 32, 48, 64]
ARCHES = ["h14g", "h13"]


def main() -> None:
    out_root = Path(CANONICAL_WORKROOT) / "k-sweep"
    results = {}
    for k in KS:
        W = np.ascontiguousarray(watermark_halves(k * N).reshape(N, k))
        x = __import__("aneforge").input((M, k))
        y = x.linear(W)
        d = out_root / f"k{k}"
        dd = _lower_fused_to_dir(y, build_dir=d)
        row = {}
        for arch in ARCHES:
            cache = dd / f"cache_{arch}"
            rc = _runtime.compile_check(dd / "model.mil", str(cache),
                                        custom_ane_options=f"TargetArchitecture={arch}")
            bundles = len({p.parent.name for p in cache.rglob("*.bundle")
                           }) if cache.is_dir() else -1
            row[arch] = {"rc": rc, "program_bundles": bundles}
        results[k] = row
        print(f"K={k:3d}: " + "  ".join(f"{a}: rc={row[a]['rc']} bundles={row[a]['program_bundles']}"
                                         for a in ARCHES), flush=True)
    (out_root / "k-sweep.json").write_text(json.dumps(results, indent=2) + "\n")
    print("wrote", out_root / "k-sweep.json")


if __name__ == "__main__":
    main()
