#!/usr/bin/env python3
"""Delete only the named experiment dirs under /var/tmp created by the jw16 parity session (build trees, test venvs,
superseded venv backups). Keeps: production venv, the original and latest venv backups, the deployed wheel's build dir,
the PR/poll driver .so files. Prints sizes freed."""
import shutil
import sys
from pathlib import Path

ROOT = Path("/var/tmp")
NAMES = [f"ew-build{i}" for i in (2, 3, 4, 5, 6, 7, 8, 9)] + [f"ew-venv{i}" for i in (3, 4, 5, 6, 7, 8, 9, 11)] + [
    "mesa-pr-src", "mesa-coh-src", "mesa-poll-src",
    "v072-venv-fused.pre-20260928T212512", "v072-venv-fused.pre-20260928T221930",
]
dry = "--apply" not in sys.argv
total = 0
for n in NAMES:
    p = ROOT / n
    if not p.is_dir() or p.resolve().parent != ROOT:
        continue
    size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())
    total += size
    print(("would remove " if dry else "removing ") + n, round(size / 1e6), "MB")
    if not dry:
        shutil.rmtree(p)
print("total MB", round(total / 1e6))
