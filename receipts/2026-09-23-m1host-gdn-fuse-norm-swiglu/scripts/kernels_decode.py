#!/usr/bin/env python3
"""Decode-window per-kernel breakdown for the m1-host batch-budget profile.

Same attribution contract as scripts/profile_analyze.py: a dispatch belongs
to its submission's marker phase; kernel names index the ComputeKernel enum.
"""
import json
import sys

import os
sys.path.insert(
    0, os.path.join(
        os.environ.get("MLX_OMARCHY_ROOT", "."), "scripts"))
from profile_analyze import parse_kernel_names, unwrap

prof = "receipts/2026-09-23-m1host-decode-gap-batchbudget/prof/prof-p0.jsonl"
markers_f = "receipts/2026-09-23-m1host-decode-gap-batchbudget/prof/markers-p0.jsonl"
header = "/tmp/compute-h-a91adbf.h"

names = parse_kernel_names(header)

meta = None
dispatches = []
submits = []
with open(prof) as f:
    for line in f:
        rec = json.loads(line)
        k = rec.get("k")
        if k == "meta":
            meta = rec
        elif k == "d":
            dispatches.append(rec)
        elif k == "s":
            submits.append(rec)

markers = [json.loads(l) for l in open(markers_f) if l.strip()]
n_tok = sum(1 for m in markers if m["p"] == "tok")


def phase_of_host(t):
    cur = markers[0]["p"]
    for m in markers:
        if m["t"] > t:
            break
        cur = m["p"]
    return cur


submit_by_s = {s["s"]: s for s in submits}
for d in dispatches:
    s_rec = submit_by_s.get(d["s"])
    d["phase"] = phase_of_host(s_rec["t"]) if s_rec else None

ordered = sorted((d for d in dispatches if "t0" in d), key=lambda d: d["t0"])
ticks = unwrap([d["t0"] for d in ordered] + [d["t1"] for d in ordered],
               meta["valid_bits"])
n = len(ordered)
t0s, t1s = ticks[:n], ticks[n:]

per_kernel = {}
total = 0.0
for d, u0, u1 in zip(ordered, t0s, t1s):
    if d["phase"] != "tok":
        continue
    dur = max(0.0, (u1 - u0)) * meta["period_ns"]
    total += dur
    name = names[d["e"]] if d["e"] < len(names) else f"kernel_{d['e']}"
    a = per_kernel.setdefault(name, {"n": 0, "dur": 0.0, "durs": []})
    a["n"] += 1
    a["dur"] += dur
    a["durs"].append(dur)

n_int = n_tok - 1
print(f"decode window: {n_int} inter-token intervals, "
      f"{sum(a['n'] for a in per_kernel.values())} dispatches "
      f"({sum(a['n'] for a in per_kernel.values())/n_int:.1f}/tok), "
      f"GPU busy {total/1e6/n_int:.3f} ms/tok\n")
print(f"{'kernel':34s} {'n/tok':>7s} {'ms/tok':>8s} {'us/launch':>10s} "
      f"{'share':>6s}")
for name, a in sorted(per_kernel.items(), key=lambda kv: -kv[1]["dur"]):
    print(f"{name:34s} {a['n']/n_int:7.1f} {a['dur']/1e6/n_int:8.3f} "
          f"{a['dur']/a['n']/1e3:10.1f} {100*a['dur']/total:5.1f}%")
