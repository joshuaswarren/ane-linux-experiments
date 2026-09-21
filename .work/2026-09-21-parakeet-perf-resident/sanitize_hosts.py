#!/usr/bin/env python3
"""Sanitize host-specific identifiers from tracked files (privacy gate).

Mapping (public repo must carry portable paths + generic SoC names only):
  jwm1-linux            -> m1-test-host
  Jwm1                  -> M1TestHost
  jwm1                  -> m1-test-host
  jw16                  -> m1-max-test-host
  /var/tmp/jwm1-ane-step2   -> /var/tmp/ane-runtime
  /var/tmp/encwall-v071     -> /var/tmp/encoder-overlay
  /tmp/mesa-sin-ftz-jwm1    -> /tmp/mesa-icd-overlay
  /var/tmp/jwm1-v072rc1     -> /var/tmp/runtime-venv
  /home/joshuawarren/.cache/mlx-omarchy -> <model-cache>/mlx-omarchy
  /home/joshuawarren/src/ane-linux-experiments-parakeet-perf -> <repo-worktree>
  /home/joshuawarren    -> <home>

Run from the repo root. Only rewrites files passed on argv.
"""
import re
import sys
from pathlib import Path

MAPPING = [
    ("/var/tmp/jwm1-ane-step2", "/var/tmp/ane-runtime"),
    ("/var/tmp/jwm1-v072rc1", "/var/tmp/runtime-venv"),
    ("/var/tmp/encwall-v071", "/var/tmp/encoder-overlay"),
    ("/tmp/mesa-sin-ftz-jwm1", "/tmp/mesa-icd-overlay"),
    ("/home/joshuawarren/.cache/mlx-omarchy", "<model-cache>/mlx-omarchy"),
    ("/home/joshuawarren/src/ane-linux-experiments-parakeet-perf", "<repo-worktree>"),
    ("/home/joshuawarren", "<home>"),
    ("jwm1-linux", "m1-test-host"),
    ("Jwm1", "M1TestHost"),
    ("jwm1", "m1-test-host"),
    ("jw16", "m1-max-test-host"),
]

changed = 0
for arg in sys.argv[1:]:
    p = Path(arg)
    if not p.is_file():
        continue
    text = p.read_text(errors="replace")
    orig = text
    for old, new in MAPPING:
        text = text.replace(old, new)
    # Binary-ish content guard: skip if replacement exploded size
    if len(text) > len(orig) * 1.2 + 1024:
        print(f"SKIP (suspicious growth): {p}")
        continue
    if text != orig:
        p.write_text(text)
        changed += 1
        print(f"sanitized: {p}")
print(f"files changed: {changed}")
