#!/usr/bin/env python3
"""Aggregate micro-<arm>-<rep>.json into the sink-vs-turnaround split.
Reads chain_us_per_launch medians per HK_PERFTEST arm and prints:
  default, nocdmbarrier (no cache maintenance), usccdmbarrier (USC inval only)
  sink share = default - nocdmbarrier
  turnaround remainder = nocdmbarrier (firmware launch cadence + jump)
Usage: analyze_attrib.py /var/tmp/gdb
"""
import glob, json, statistics, sys

def med(vals):
    return statistics.median(vals)

def main():
    base = sys.argv[1]
    out = {}
    for arm in ("default", "nocdmbarrier", "usccdmbarrier", "designedusccdmbarrier"):
        files = sorted(glob.glob(f"{base}/micro-{arm}-*.json"))
        vals = []
        for f in files:
            d = json.load(open(f))
            vals.append(d["chain_us_per_launch"]["median"])
        if vals:
            out[arm] = med(vals)
            print(f"{arm:15s} n={len(vals)} chain_us median {out[arm]:7.2f}  vals {[round(v,1) for v in vals]}")
        else:
            print(f"{arm:15s} NO DATA")
    if "default" in out and "nocdmbarrier" in out:
        sink = out["default"] - out["nocdmbarrier"]
        print(f"\nsink+cache-maintenance share : {sink:6.2f} µs/launch ({100*sink/out['default']:.0f}% of default)")
        print(f"launch/turnaround remainder  : {out['nocdmbarrier']:6.2f} µs/launch")
    if "default" in out and "usccdmbarrier" in out:
        d = out["default"] - out["usccdmbarrier"]
        print(f"USC-inval-only saving        : {d:6.2f} µs/launch ({100*d/out['default']:.0f}% of default)")
    print("\nreading: sink share on REAL kernels = the addressable-by-driver slice;")
    print("remainder is firmware launch cadence (~2.5 µs class on trivial chains)")
    print("plus any residual scheduling cost — not driver-addressable.")

if __name__ == "__main__":
    main()
