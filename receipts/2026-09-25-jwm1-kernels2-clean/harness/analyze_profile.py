#!/usr/bin/env python3
"""Per-dispatch GPU profile analyzer for jwm1 decode (Jwm1Kernels2).

Parses MLX_OMARCHY_GPU_PROFILE NDJSON (gpu_profiler.h: meta/b/d/s/q/j/end).
'd' events carry the kernel name in "p", enum in "e", groups in gx/gy/gz,
GPU ticks t0/t1 (BOTTOM_OF_PIPE), bindings "b" = [[buffer, offset, range]],
submit id in "s". Bytes = sum of binding ranges (upper-bound traffic proxy;
includes outputs, skips host-side offsets).

Modes:
  tail <k>   aggregate the last k submit groups (decode: k=33 ~= 1 warm
             token + 32 measured; skip the first of them)
  all        aggregate everything (prefill included)
"""
import json
import statistics
import sys


def main():
    path = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "tail"
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 33
    meta, ds, submit_ids = None, [], []
    for line in open(path):
        line = line.strip()
        if not line.startswith("{"):
            continue
        e = json.loads(line)
        kk = e.get("k")
        if kk == "meta":
            meta = e
        elif kk == "d":
            ds.append(e)
            if e["s"] not in submit_ids:
                submit_ids.append(e["s"])
    period = meta["period_ns"]
    if mode == "tail":
        keep = set(submit_ids[-k:])
        # drop the first kept group: it still pays stragglers/compile
        ds = [d for d in ds if d["s"] in keep and d["s"] != submit_ids[-k]]
    rows = {}
    total_ns = 0
    for d in ds:
        ns = (d["t1"] - d["t0"]) * period
        if ns < 0:
            continue
        bts = sum(b[2] for b in d.get("b", []) if len(b) > 2)
        name = d.get("p") or f"enum{d['e']}"
        r = rows.setdefault(name, {"n": 0, "ns": 0, "bytes": 0, "gx": [],
                                   "ns_list": []})
        r["n"] += 1
        r["ns"] += ns
        r["ns_list"].append(ns)
        r["bytes"] += bts
        r["gx"].append(d.get("gx", 0))
        total_ns += ns
    print(f"# {meta.get('device','?')} events={len(ds)} "
          f"submits={len(set(d['s'] for d in ds))} "
          f"gpu_sum={total_ns/1e6:.2f} ms")
    print(f"{'kernel':40s} {'n':>6} {'ms':>9} {'%':>5} {'GB/s':>7} "
          f"{'gx':>10} {'ns med':>9} {'ns max':>9}")
    ranked = sorted(rows.items(), key=lambda kv: -kv[1]["ns"])
    for name, r in ranked[:30]:
        gbs = r["bytes"] / r["ns"] if r["ns"] else 0.0
        print(f"{name:40s} {r['n']:6d} {r['ns']/1e6:9.3f} "
              f"{100*r['ns']/total_ns:5.1f} {gbs:7.1f} "
              f"{r['gx'][0]:10d} {statistics.median(r['ns_list'])/1e3:9.1f} "
              f"{max(r['ns_list'])/1e3:9.1f}")
    slow = sorted(ds, key=lambda d: (d["t1"] - d["t0"]) * period)[-12:]
    print("# slowest individual dispatches:")
    for d in reversed(slow):
        ns = (d["t1"] - d["t0"]) * period
        bts = sum(b[2] for b in d.get("b", []) if len(b) > 2)
        print(f"# s={d['s']} {d.get('p')} gx={d.get('gx')} "
              f"ns={ns:.0f} ({ns/1e3:.1f} us) ranges={bts/1e6:.2f}MB "
              f"achv={bts/ns if ns else 0:.1f} GB/s")


if __name__ == "__main__":
    main()
