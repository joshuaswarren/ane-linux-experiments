#!/usr/bin/env python3
"""Per-dispatch GPU profile analyzer for jwm1 decode (Jwm1Kernels2).

Reads an MLX_OMARCHY_GPU_PROFILE NDJSON stream (gpu_profiler.h schema:
meta/b/d/s/q/j/end) and the compute.h kernel enum, ranks kernels by total
GPU time and achieved bytes/s. Binding ranges are an upper-bound traffic
proxy (includes outputs); the max-range binding (weights) is reported
separately.

Usage: analyze_profile.py <profile.ndjson> <compute.h> [--top 25]
"""
import json
import re
import sys


def kernel_names(compute_h):
    # enum order = profile kernel id order (see gpu_profiler.h comment)
    body = re.search(r"enum(?:\s+\w+)?\s*\{(.*)\}", compute_h, re.S)
    names = []
    for m in re.finditer(r"^\s*(k?[A-Z][A-Za-z0-9_]*),?\s*(?://.*)?$",
                         body.group(1), re.M):
        n = m.group(1)
        if n.startswith("k"):  # constexpr counters live in the same header
            continue
        names.append(n)
    # de-dup consecutive while preserving order
    out = []
    for n in names:
        if n not in out:
            out.append(n)
    return out


def main():
    path, header = sys.argv[1], sys.argv[2]
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 25
    names = kernel_names(open(header).read())
    meta, events = None, []
    for line in open(path):
        line = line.strip()
        if not line.startswith("{"):
            continue
        e = json.loads(line)
        k = e.get("k")
        if k == "meta":
            meta = e
        elif k == "d":
            events.append(e)
    period = meta["period_ns"]
    valid_bits = meta.get("valid_bits", 64)
    wrap = 1 << valid_bits

    def dt(e):
        d = e["t1"] - e["t0"]
        if d < 0:
            d += wrap
        return d * period

    rows = {}
    for e in events:
        ker = names[e["kernel"]] if e["kernel"] < len(names) else f"enum{e['kernel']}"
        ns = dt(e)
        bts = sum(b.get("range", 0) for b in e.get("bindings", []))
        wgt = max((b.get("range", 0) for b in e.get("bindings", [])), default=0)
        r = rows.setdefault(ker, {"n": 0, "ns": 0, "bytes": 0, "wbytes": 0,
                                  "gx": e.get("groups", [0])[0]})
        r["n"] += 1
        r["ns"] += ns
        r["bytes"] += bts
        r["wbytes"] += wgt
    total_ns = sum(r["ns"] for r in rows.values())
    print(f"# {meta.get('device','?')}  events={len(events)}  "
          f"gpu_busy={total_ns/1e6:.2f} ms  period={period}ns")
    print(f"{'kernel':44s} {'n':>6} {'ms':>9} {'%':>5} "
          f"{'GB/s@ranges':>11} {'GB/s@wmax':>9} {'gx':>7}")
    for ker, r in sorted(rows.items(), key=lambda kv: -kv[1]["ns"])[:top]:
        ms = r["ns"] / 1e6
        gbr = r["bytes"] / r["ns"] if r["ns"] else 0
        gbw = r["wbytes"] / r["ns"] if r["ns"] else 0
        print(f"{ker:44s} {r['n']:6d} {ms:9.3f} {100*r['ns']/total_ns:5.1f} "
              f"{gbr:11.1f} {gbw:9.1f} {r['gx']:7d}")


if __name__ == "__main__":
    main()
