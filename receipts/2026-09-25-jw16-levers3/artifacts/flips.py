#!/usr/bin/env python3
"""Locate where contract runs diverge from a reference run (pass, prompt, first token, positions)."""
import json, sys
ref = json.load(open(sys.argv[1]))
refmap = {(r["pass"], r["prompt_idx"]): r["output_ids"] for r in ref["per_prompt"]}
for path in sys.argv[2:]:
    j = json.load(open(path))
    label = j["meta"].get("label", path)
    dig = j["ordered_records_sha256"][:8]
    flips = []
    for r in j["per_prompt"]:
        key = (r["pass"], r["prompt_idx"])
        a = refmap.get(key)
        if a is None:
            continue
        b = r["output_ids"]
        diff = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
        if diff or len(a) != len(b):
            flips.append((key, diff[0] if diff else -1, len(diff)))
    print(f"{label:24s} {dig} records={len(j['per_prompt'])} diverged={len(flips)} " +
          " ".join(f"[pass {p} prompt {q}: token {t}, {n} pos]" for (p, q), t, n in flips))
