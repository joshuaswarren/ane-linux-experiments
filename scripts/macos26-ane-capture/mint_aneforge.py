#!/usr/bin/env python3
"""Mint ANE oracle libraries for t602x linear geometries (v3).

Runs on macOS with ANEForge (drives Apple's private Espresso e5rt compiler —
the same compiler backend behind ANECompiler/ANECompilerService — with
TargetArchitecture passed as a custom ANE-compiler option, compile-only).

Weights are INDEX-ENCODED (never uniform): every adjacent fp16 PAIR carries a
28-bit pair watermark:
    even half bits = 0x0400 + (p & 0x3FFF)          (positive normal fp16)
    odd  half bits = 0x8400 + ((p >> 14) & 0x3FFF)  (negative normal fp16)
so the emitted permutation is readable offline:
    p = (even - 0x0400) | ((odd - 0x8400) << 14)   (= source pair index)

Usage:
    mint_aneforge.py [--workroot DIR] [GEOM ...]
    Geometries: oproj mm1 mm2 edge-n1000 edge-k64 edge-k16
    (default: all, under the canonical workroot)

METHODS RULE (2026-09-17, load-bearing — do not bypass):
The ANE compiler embeds the MIL source path VERBATIM in the compiled program
("input-file-path" metadata), and changing the path re-salts the entire
encoding: program length tracks path length, and two compiles differing only
in path differed in 1117/2320 bytes (measured, oproj). Byte-diff comparisons
of minted artifacts are ONLY valid when every host mints at an IDENTICAL
normalized absolute path. This driver therefore defaults to the canonical
workroot `/tmp/anec-mint-normalized` and warns loudly on overrides; cross-host
comparisons must use the default (or pass the identical --workroot everywhere).
Comparing artifacts minted at different paths compares provenance noise, not
architecture. Same-path recompiles are byte-identical (verified 2026-09-17).

Known compiler behavior (ANECompiler 9.509.0, macOS 26.6.2 25G83):
TargetArchitecture is IGNORED for family selection — the emitted program is
keyed to the LOCAL machine's ANE (bundle named H13D.bundle on M1-family hosts,
H14C.bundle on t6021), regardless of the option. Oracles are host-SoC by
construction; mint on the target SoC. Program bytes are otherwise
family-invariant for linear (single-byte family id at 0x908).
"""
import json
import sys
from pathlib import Path

import numpy as np

for p in ("/tmp/t6021-mint", "$HOME/src/ANEForge"):
    if Path(p).is_dir():
        sys.path.insert(0, p)
        break
import aneforge as af                                    # noqa: E402
from aneforge._compile import _lower_fused_to_dir        # noqa: E402
from aneforge import _runtime                            # noqa: E402

GEOMETRIES = {
    "oproj": (375, 1024, 1024),
    "mm1": (375, 1024, 4096),
    "mm2": (375, 4096, 1024),
    "edge-n1000": (375, 1024, 1000),   # output count NOT a multiple of 16
    "edge-k64": (375, 64, 1024),       # small reduction depth
    "edge-k16": (375, 16, 1024),       # minimal reduction depth (one lane group)
}
ARCHES = ["h14g", "h13"]
CANONICAL_WORKROOT = "/tmp/anec-mint-normalized"


def watermark_halves(n_halves: int) -> np.ndarray:
    pairs = n_halves // 2
    idx = np.arange(pairs, dtype=np.uint32)
    even = (0x0400 + (idx & 0x3FFF)).astype(np.uint16)
    odd = (0x8400 + ((idx >> 14) & 0x3FFF)).astype(np.uint16)
    bits = np.empty(pairs * 2, dtype=np.uint16)
    bits[0::2], bits[1::2] = even, odd
    return bits.view(np.float16)


def main() -> None:
    args = sys.argv[1:]
    workroot = CANONICAL_WORKROOT
    if "--workroot" in args:
        i = args.index("--workroot")
        workroot = args[i + 1]
        del args[i:i + 2]
    if workroot != CANONICAL_WORKROOT:
        print(f"[methods] WARNING: non-canonical workroot {workroot!r}. "
              "Cross-host byte comparisons are INVALID unless every host uses "
              "this exact same path (the compiler embeds it and path re-salts "
              "the encoding).", flush=True)
    geoms = [a for a in args if not a.startswith("-")] or list(GEOMETRIES)
    out_root = Path(workroot)
    summary = {"workroot": str(out_root), "canonical": workroot == CANONICAL_WORKROOT,
               "geometries": {}}
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
        summary["geometries"][name] = rec
    (out_root / "mint-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("wrote", out_root / "mint-summary.json")


if __name__ == "__main__":
    main()
