#!/usr/bin/env python3
"""Expand pinned bench_matrix prompt ids to the exact texts the A/B
batteries used, write one file per id for xargs-free shell use."""
import json, pathlib
M = json.load(open("/var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_matrix.json"))
out = pathlib.Path("/var/tmp/TermASplit")
out.mkdir(exist_ok=True)
for pid in ("short", "ctx1024"):
    e = M["prompts"][pid]
    if "text" in e:
        t = e["text"]
    else:
        t = " ".join([e["base"]] + [
            f"{e['item']} Entry {i} of {e['items']}." for i in range(1, e["items"] + 1)])
    p = out / f"prompt-{pid}.txt"
    p.write_bytes(t.encode())
    print(pid, len(t.encode()), "bytes ->", p)
