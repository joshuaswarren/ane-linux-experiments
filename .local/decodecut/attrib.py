#!/usr/bin/env python3
"""Per-(kernel, primitive) attribution over the decode window of an
MLX_OMARCHY_GPU_PROFILE NDJSON stream. Phase mapping identical to
scripts/profile_analyze.py (dispatch belongs to its submission's phase).
Usage: attrib.py PROFILE.jsonl markers.jsonl compute.h [--phase decode]"""
import argparse, json, re, sys
from collections import defaultdict

ap = argparse.ArgumentParser()
ap.add_argument("profile")
ap.add_argument("markers")
ap.add_argument("header")
ap.add_argument("--phase", default="decode")
a = ap.parse_args()

names = {}
inside = False
for line in open(a.header, encoding="utf-8"):
    if "enum class ComputeKernel" in line:
        inside = True
        continue
    if inside:
        m = re.match(r"^\s{2}(\w+),\s*$", line)
        if m:
            names[len(names)] = m.group(1)
        elif "};" in line:
            break

dispatches, submits, markers = [], [], []
meta = None
for line in open(a.profile, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    r = json.loads(line)
    k = r.get("k")
    if k == "d":
        dispatches.append(r)
    elif k == "s":
        submits.append(r)
    elif k == "meta":
        meta = r
    elif k in ("b", "j", "q", "end"):
        pass
for line in open(a.markers, encoding="utf-8"):
    line = line.strip()
    if line:
        markers.append(json.loads(line))

submit_by_s = {s["s"]: s for s in submits}
PHASE_OF_MARKER = {"load_start": "load", "prefill_start": "prefill",
                   "decode_start": "decode", "tok": "decode", "decode": "decode"}

def phase_of_host(t):
    cur = markers[0]["p"]
    for m in markers:
        if m["t"] > t:
            break
        cur = m["p"]
    return PHASE_OF_MARKER.get(cur)

agg = defaultdict(lambda: [0, 0.0])  # (kernel, prim) -> [n, total_ns]
period = meta["period_ns"]
valid_bits = meta["valid_bits"]
tok_n = sum(1 for m in markers if m["p"] == "tok")

for d in dispatches:
    s = submit_by_s.get(d["s"])
    if s is None:
        continue
    if phase_of_host(s["t"]) != a.phase:
        continue
    key = (names.get(d["e"], f"k{d['e']}"), d.get("p", "") or "?")
    agg[key][0] += 1
    if "t0" in d and "t1" in d and d["t1"] >= d["t0"]:
        agg[key][1] += (d["t1"] - d["t0"]) * period

print(f"# phase={a.phase} n_tok={tok_n} interval={tok_n-1}")
rows = sorted(agg.items(), key=lambda kv: -kv[1][0])
tot = sum(v[0] for v in agg.values())
print(f"# total dispatches {tot} = {tot/max(1,tok_n-1):.1f}/token")
print(f"{'kernel':32s} {'prim':28s} {'n':>8s} {'n/tok':>7s} {'ms':>9s}")
for (k, p), (n, ns) in rows:
    if n * 40 < tot:  # skip long tail below 2.5%
        continue
    print(f"{k:32s} {p:28s} {n:8d} {n/max(1,tok_n-1):7.1f} {ns/1e6:9.2f}")
