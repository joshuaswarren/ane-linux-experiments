#!/usr/bin/env python3
"""Kernel-level busy census from MLX_OMARCHY_GPU_PROFILE ndjson.

Attributes profiled busy time (t1-t0, bracket-inflated — relative shares
only) to kernels by enum name (declaration order in compute.h). First
step of kernel-side decode attribution (KV walk / qmm / elementwise).

Usage: analyze_kernel_census.py <compute.h> <profile.ndjson> [ndjson...]
"""
import json, re, statistics, sys
from collections import defaultdict

def kernel_names(h):
    names, in_enum = [], False
    for line in open(h):
        s = line.strip()
        if s.startswith("enum class ComputeKernel"):
            in_enum = True
            continue
        if in_enum:
            if s.startswith("}"):
                break
            m = re.match(r"^([A-Za-z0-9_]+),?$", s)
            if m:
                names.append(m.group(1))
    return names

def main():
    names = kernel_names(sys.argv[1])
    busy = defaultdict(float)
    cnt = defaultdict(int)
    steps = []
    for fn in sys.argv[2:]:
        for line in open(fn):
            if not line.strip().startswith("{"):
                continue
            e = json.loads(line)
            if e.get("k") != "d":
                continue
            k = names[e["op"]] if e["op"] < len(names) else f"unk{e['op']}"
            busy[k] += (e["t1"] - e["t0"]) / 1e6
            cnt[k] += 1
            steps.append(e)
    total = sum(busy.values())
    print(f"dispatches={len(steps)} total bracketed busy={total:.1f} ms")
    for k, v in sorted(busy.items(), key=lambda kv: -kv[1]):
        print(f"  {k:38s} {v:8.2f} ms  {100*v/total:5.1f}%  n={cnt[k]}")

if __name__ == "__main__":
    main()
