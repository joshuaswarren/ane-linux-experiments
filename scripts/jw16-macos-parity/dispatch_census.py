#!/usr/bin/env python3
"""Per-token dispatch census from an MLX_OMARCHY_TRACE_DISPATCH stderr capture.
usage: dispatch_census.py TRACE_TXT COMPUTE_H
Finds the steady-state decode period (dispatches/token) and prints kernel counts and a window of the sequence."""
import collections
import re
import sys

trace, compute_h = sys.argv[1], sys.argv[2]
src = open(compute_h).read()
body = src[src.index("enum class ComputeKernel"):]
body = body[body.index("{") + 1:body.index("};")]
names = []
for line in body.splitlines():
    for tok in line.split("//")[0].split(","):
        tok = tok.strip()
        if tok:
            names.append(tok.split("=")[0].strip())
ids = [int(re.search(r"kernel=(\d+)", ln).group(1)) for ln in open(trace) if "kernel=" in ln]
seq = [names[i] if i < len(names) else str(i) for i in ids]
print("total dispatches", len(seq))
tail = seq[-2400:]
period = None
for p in range(300, 700):
    if len(tail) >= 2 * p and tail[-p:] == tail[-2 * p:-p]:
        period = p
        break
print("period (dispatches/token):", period)
if period:
    cyc = seq[-period:]
    for k, v in collections.Counter(cyc).most_common():
        print(f"{v:4d} {k}")
    print("cycle[0:70]:", cyc[:70])
    print("cycle[70:140]:", cyc[70:140])
