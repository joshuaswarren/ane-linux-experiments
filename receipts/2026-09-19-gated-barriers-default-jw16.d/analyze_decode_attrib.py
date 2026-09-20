#!/usr/bin/env python3
"""Decode-leg barrier attribution from MLX_OMARCHY_GPU_PROFILE ndjson.

Compares two profile runs (e.g. default sink vs designedusccdmbarrier,
both on the hkccad76a extracted driver, short decode leg) and reports
per-node host record, bracket-to-bracket gap, and busy, plus the
realized per-launch delta in decode — the measurement the micro chain
cannot provide (micro −32% did not transfer to decode legs).

Usage: analyze_decode_attrib.py <default.ndjson> <cand.ndjson> [leg-label]
"""
import json, statistics, sys

def load(fn):
    evs = [json.loads(l) for l in open(fn) if l.strip().startswith("{")]
    d = [e for e in evs if e["k"] == "d"]
    # decode steps = submissions with n=201 dispatches (Qwen2.5-0.5B)
    from collections import defaultdict
    bys = defaultdict(list)
    for e in d:
        bys[e.get("s", 0)].append(e)
    steps = {s: rows for s, rows in bys.items() if len(rows) == 201}
    return steps

def summarize(steps):
    out = {}
    for s, rows in steps.items():
        hc = [r["h"] for r in rows]
        gaps = sorted(rows[i + 1]["t0"] - rows[i]["t1"] for i in range(len(rows) - 1))
        busy = sum(r["t1"] - r["t0"] for r in rows) / 1e6
        span = (max(r["t1"] for r in rows) - min(r["t0"] for r in rows)) / 1e6
        out[s] = {
            "host_med_us": statistics.median(hc) / 1e3,
            "gap_med_us": gaps[len(gaps) // 2] / 1e3,
            "gap_p90_us": gaps[int(len(gaps) * 0.9)] / 1e3,
            "busy_ms": busy, "span_ms": span,
        }
    return out

def main():
    a, b = summarize(load(sys.argv[1])), summarize(load(sys.argv[2]))
    label = sys.argv[3] if len(sys.argv) > 3 else "cand"
    print(f"{'sub':>4s} {'host(base→cand)':>22s} {'gap_med':>16s} {'gap_p90':>16s} {'busy_ms':>16s}")
    for s in sorted(set(a) & set(b)):
        A, B = a[s], b[s]
        print(f"{s:>4d} {A['host_med_us']:8.2f}→{B['host_med_us']:6.2f}µs "
              f"{A['gap_med_us']:6.2f}→{B['gap_med_us']:6.2f}µs "
              f"{A['gap_p90_us']:6.2f}→{B['gap_p90_us']:6.2f}µs "
              f"{A['busy_ms']:6.2f}→{B['busy_ms']:6.2f}ms")
    print(f"\nrealized decode delta = per-node machinery delta × 201; compare")
    print(f"against the micro's 7.94 µs/launch to measure the overlap hypothesis.")

if __name__ == "__main__":
    main()
