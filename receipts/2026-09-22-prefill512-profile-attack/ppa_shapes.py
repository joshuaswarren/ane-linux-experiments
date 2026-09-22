#!/usr/bin/env python3
"""Per-shape dispatch table for selected kernels from a GPU profile jsonl."""
import json, sys, collections

prof, hdr = sys.argv[1], sys.argv[2]
want = set(int(x) for x in sys.argv[3].split(","))
names = []
inside = False
import re
for line in open(hdr):
    if "enum class ComputeKernel" in line:
        inside = True
        continue
    if inside:
        m = re.match(r"\s+(\w+),\s*$", line)
        if m:
            names.append(m.group(1))
        elif "};" in line:
            break
meta = None
rows = collections.defaultdict(list)
for line in open(prof):
    r = json.loads(line)
    if r["k"] == "meta":
        meta = r
    elif r["k"] == "d" and r["e"] in want:
        rows[r["e"]].append(r)
pn = meta["period_ns"] if meta else 1.0
for kern, rs in sorted(rows.items()):
    agg = collections.defaultdict(lambda: [0, 0.0])
    for r in rs:
        t = 0.0
        if "t0" in r and "t1" in r and r["t1"] > r["t0"]:
            t = (r["t1"] - r["t0"]) * pn / 1e6
        key = (r["n"], r["gx"], r.get("gy"), r.get("gz"), r["b"] and len(r["b"]) or 0, len(r.get("b") or []) and r["b"][-1][1] or 0)
        a = agg[key]
        a[0] += 1
        a[1] += t
    print("== kernel", kern, names[kern] if kern < len(names) else "?")
    for key, (n, tms) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        print("  count=%s gx=%s gy=%s gz=%s nb=%s lastbuf=%s n=%d total=%.2fms mean=%.3fms"
              % (key[0], key[1], key[2], key[3], key[4], key[5], n, tms, tms / n))
