#!/usr/bin/env python3
"""Venv libmlx identity guard for t6001-test-host certification lanes.

Refuses any venv whose mlx-omarchy libmlx identity is not on the certified
list (certified-libmlx-identities.txt, maintained beside receipts/) BEFORE
digest-pin lanes run, so drift fails loudly instead of as a confusing
mid-run identity-pin break (see receipts/2026-09-18-t6001-test-host-venv-identity-hygiene.md).

Checks per venv, no mlx import, no GPU:
  1. marker file <venv>/.mlx-NONCERTIFIED  -> refuse, quoting its reason.
  2. installed identity: sha256-16 of <site>/mlx/lib/libmlx.so plus the
     mlx_omarchy dist version -> must be on the certified list.
  3. loaded identity: first mlx/lib/libmlx.so found walking PYTHONPATH dirs
     then the venv site-packages (the order CPython resolves imports) -> must
     equal the installed identity. Catches the site-dir shadowing that made
     pre-gates see 65a641e4/84664140/e9e709f3 in Sep 17-18 windows.
     ponytail: ignores .pth tricks and namespace-path edits; a lane that
     mutates sys.path at runtime still has bench_decode's provenance line
     as the backstop.

Usage:
  python3 venv-identity-guard.py [--list FILE] [--expect LIBMLX16] VENV [VENV...]

Exit 0: every venv certified. Exit 3: any refusal (message names the venv,
its identity, and the list to fix or mark against).
"""
import argparse
import glob
import hashlib
import os
import sys

MARKER = ".mlx-NONCERTIFIED"


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def dist_version(site):
    versions = [
        os.path.basename(p)[len("mlx_omarchy-"):-len(".dist-info")]
        for p in glob.glob(os.path.join(site, "mlx_omarchy-*.dist-info"))
    ]
    return max(versions) if versions else None


def load_certified(path):
    entries = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            entries[parts[0]] = parts[1] if len(parts) > 1 else ""
    return entries


def identity(venv, pythonpath):
    site = None
    hits = sorted(glob.glob(os.path.join(venv, "lib", "python*", "site-packages")))
    if hits:
        site = hits[0]
    if site is None:
        return None
    installed = os.path.join(site, "mlx", "lib", "libmlx.so")
    loaded = None
    for d in pythonpath:
        cand = os.path.join(d, "mlx", "lib", "libmlx.so")
        if os.path.isfile(cand):
            loaded = cand
            break
    if loaded is None and os.path.isfile(installed):
        loaded = installed
    return {
        "site": site,
        "version": dist_version(site),
        "installed16": sha16(installed) if os.path.isfile(installed) else None,
        "loaded16": sha16(loaded) if loaded else None,
        "loaded_from": loaded,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("venvs", nargs="+")
    ap.add_argument("--list", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "certified-libmlx-identities.txt"))
    ap.add_argument("--expect", default=None, metavar="LIBMLX16",
                    help="additionally require the loaded identity to equal this")
    ap.add_argument("--pythonpath", default=os.environ.get("PYTHONPATH", ""),
                    help="PYTHONPATH the lane will run with (default: env)")
    args = ap.parse_args()
    certified = load_certified(args.list)
    pythonpath = [d for d in args.pythonpath.split(":") if d]

    failures = []
    for venv in args.venvs:
        if not os.path.isdir(venv):
            failures.append(f"REFUSE {venv}: not a venv directory")
            continue
        marker = os.path.join(venv, MARKER)
        if os.path.isfile(marker):
            reason = open(marker).read().strip().splitlines()[0] if open(marker).read().strip() else "no reason recorded"
            failures.append(
                f"REFUSE {venv}: marked NON-CERTIFIED ({marker}): {reason}")
            continue
        ident = identity(venv, pythonpath)
        if ident is None or ident["installed16"] is None:
            failures.append(
                f"REFUSE {venv}: no mlx-omarchy libmlx.so in venv site-packages")
            continue
        build = certified.get(ident["installed16"])
        if build is None:
            failures.append(
                f"REFUSE {venv}: installed libmlx16 {ident['installed16']} "
                f"(dist {ident['version']}) is NOT on the certified list "
                f"({args.list}). Repin the certified wheel or drop {marker}.")
            continue
        if ident["loaded16"] != ident["installed16"]:
            failures.append(
                f"REFUSE {venv}: PYTHONPATH SHADOWING - loaded libmlx16 "
                f"{ident['loaded16']} from {ident['loaded_from']} != installed "
                f"{ident['installed16']} ({build}). Clean PYTHONPATH or the "
                f"shadowing site dir.")
            continue
        if args.expect and ident["loaded16"] != args.expect:
            failures.append(
                f"REFUSE {venv}: loaded libmlx16 {ident['loaded16']} != "
                f"expected {args.expect}")
            continue
        print(f"PASS {venv}: {build} (libmlx16 {ident['loaded16']}, "
              f"dist {ident['version']})")

    for f in failures:
        print(f, file=sys.stderr)
    if failures:
        sys.exit(3)
    print(f"{len(args.venvs)} venv(s) certified ({args.list})")


if __name__ == "__main__":
    main()
