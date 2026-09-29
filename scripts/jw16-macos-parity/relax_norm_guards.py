#!/usr/bin/env python3
"""Remove the decode-only size guards of the fused-norm routes in a venv's mlx_lm (experiment; backup .orig kept).
usage: relax_norm_guards.py VENV"""
import re
import shutil
import sys
from pathlib import Path

site = next(Path(sys.argv[1]).glob("lib/python3.*/site-packages/mlx_lm/models"))
for name in ("qwen3_next.py", "qwen3_5.py"):
    p = site / name
    s = p.read_text()
    new = re.sub(r"\n\s+and hidden_states\.size <= 2048", "", s)
    new = re.sub(r"\n\s+and q\.size <= 32768", "", new)
    if new != s:
        shutil.copy(p, str(p) + ".orig")
        p.write_text(new)
        print("patched", name, "removed", (len(s) - len(new)), "bytes")
