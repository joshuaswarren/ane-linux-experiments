#!/usr/bin/env python3
"""Sanitize host-specific identifiers from tracked files (privacy gate).

Mapping (public repo must carry portable paths + generic SoC names only):
  m1-test-host-linux            -> m1-test-host
  m1-test-host                  -> M1TestHost
  m1-test-host                  -> m1-test-host
  t6001-test-host                  -> m1-max-test-host
  /var/tmp/m1-test-host-ane-step2   -> /var/tmp/ane-runtime
  /var/tmp/encwall-v071     -> /var/tmp/encoder-overlay
  /tmp/mesa-sin-ftz-m1-test-host    -> /tmp/mesa-icd-overlay
  /var/tmp/m1-test-host-v072rc1     -> /var/tmp/runtime-venv
  $HOME/.cache/mlx-omarchy -> <model-cache>/mlx-omarchy
  $HOME/src/ane-linux-experiments-parakeet-perf -> <repo-worktree>
  $HOME    -> <home>

Run from the repo root. Only rewrites files passed on argv.
"""
import re
import sys
from pathlib import Path

MAPPING = [
    ("/var/tmp/m1-test-host-ane-step2", "/var/tmp/ane-runtime"),
    ("/var/tmp/m1-test-host-v072rc1", "/var/tmp/runtime-venv"),
    ("/var/tmp/encwall-v071", "/var/tmp/encoder-overlay"),
    ("/tmp/mesa-sin-ftz-m1-test-host", "/tmp/mesa-icd-overlay"),
    ("$HOME/.cache/mlx-omarchy", "<model-cache>/mlx-omarchy"),
    ("$HOME/src/ane-linux-experiments-parakeet-perf", "<repo-worktree>"),
    ("$HOME", "<home>"),
    ("m1-test-host-linux", "m1-test-host"),
    ("m1-test-host", "M1TestHost"),
    ("m1-test-host", "m1-test-host"),
    ("t6001-test-host", "m1-max-test-host"),
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
