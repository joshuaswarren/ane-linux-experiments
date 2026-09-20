#!/usr/bin/env python3
"""CPU-only checks for exact warm accounting and complete profiler input."""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import qmm_weight_curve_micro as curve


def reject(fn):
    try:
        fn()
    except (SystemExit, ValueError):
        return
    raise AssertionError("corrupt attribution was accepted")


plan = [{"block": 0, "w": 1, "steps": 2}, {"block": 0, "w": 2, "steps": 2}]
subs = {i: [(100.0 if i <= 2 else float(i), 412)] for i in range(1, 7)}
by_w, _ = curve.attribute_by_submission(subs, plan)
assert by_w == {1: [3.5], 2: [5.5]}, by_w
reject(lambda: curve.attribute_by_submission({**subs, 7: [(7.0, 412)]}, plan))
reject(lambda: curve.attribute_by_submission({**subs, 7: [(7.0, 397)]}, plan))
reject(lambda: curve.attribute_by_submission({**subs, 7: [(7.0, 412), (8.0, 412)]}, plan))
reject(lambda: curve.attribute_by_submission({k: v for k, v in subs.items() if k != 4}, plan))

with tempfile.TemporaryDirectory() as root:
    root = Path(root)
    plan = curve.build_plan()
    warm = max(s["w"] for s in plan)
    count = warm + sum(s["steps"] for s in plan)
    records = [{"k": "meta", "period_ns": 1000, "valid_bits": 64}]
    records += [{"k": "d", "s": i + 1, "e": 412, "t0": 0,
                 "t1": 999 if i < warm else 10} for i in range(count)]
    records += [{"k": "end", "dispatches": count, "dropped": 0}]
    walls = [{**s, "wall_avg_us": 20} for s in plan]
    identity = {"pass": "compiled-curve", "outputs_finite": True, "walls": walls}
    profile, sidecar, out = (root / n for n in ("profile", "identity", "report"))
    sidecar.write_text(json.dumps(identity))
    args = SimpleNamespace(profile=str(profile), plan_meta=str(sidecar), out=str(out))
    def run(rows):
        profile.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        curve.pass_curve_report(args, plan)
    run(records)
    result = json.loads(out.read_text())
    assert all(v["p50"] == 10 for v in result["dispatch_us_quantiles_by_w"].values())
    reject(lambda: run(records[:-1]))
    reject(lambda: run(records[:-1] + [{**records[-1], "dropped": 1}]))
    reject(lambda: run(records[:-1] + [{**records[-1], "dispatches": count + 1}]))
    reject(lambda: run([records[0], {**records[1], "t1": -1}, *records[2:]]))
    sidecar.write_text(json.dumps({**identity, "walls": walls[::-1]}))
    reject(lambda: run(records))
print("PASS: exact warm accounting, surplus/foreign work, quantiles, EOF, drops, counts, ticks, plan")
