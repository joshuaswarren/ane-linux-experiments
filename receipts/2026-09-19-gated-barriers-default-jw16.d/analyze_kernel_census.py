#!/usr/bin/env python3
"""Kernel-level busy census from MLX_OMARCHY_GPU_PROFILE ndjson.

Attributes profiled busy time (t1-t0, bracket-inflated — relative shares
only) to kernels by enum name (declaration order in compute.h). First
step of kernel-side decode attribution (KV walk / qmm / elementwise).

Event-field contract (gpu_profiler.h flush_slot emitf): the KERNEL ENUM
is field "e"; "op" is params.operation — a per-kernel code (the qmm
shaders carry the bit width there, so every Q4 qmm dispatch has op=4) —
never a kernel id. Grouping by "op" collapsed the whole Qmm Q4 family
onto names[4] = CastBoolF32 (the 2026-09-19 census mislabel; guarded by
scripts/test_profile_kernel_census.py). Busy time converts raw ticks
with meta.period_ns. Dispatches without recorded timestamps (pool
exhaustion) are counted and skipped.

Usage: analyze_kernel_census.py <compute.h> <profile.ndjson> [ndjson...]
"""
import json, re, sys
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
    steps = 0
    noticks = 0
    period_ns = 1.0
    for fn in sys.argv[2:]:
        for line in open(fn):
            if not line.strip().startswith("{"):
                continue
            e = json.loads(line)
            if e.get("k") == "meta":
                period_ns = float(e.get("period_ns", 1.0))
                continue
            if e.get("k") != "d":
                continue
            if "t0" not in e or "t1" not in e:
                noticks += 1
                continue
            k = names[e["e"]] if e["e"] < len(names) else f"unk{e['e']}"
            busy[k] += (e["t1"] - e["t0"]) * period_ns / 1e6
            cnt[k] += 1
            steps += 1
    total = sum(busy.values())
    print(f"dispatches={steps} no-tick skipped={noticks} "
          f"total bracketed busy={total:.1f} ms "
          f"(period_ns={period_ns:g}; bracket-inflated, shares only)")
    for k, v in sorted(busy.items(), key=lambda kv: -kv[1]):
        print(f"  {k:38s} {v:8.2f} ms  {100*v/total:5.1f}%  n={cnt[k]}"
              f"  mean={1000*v/cnt[k]:8.1f} us")

if __name__ == "__main__":
    main()
