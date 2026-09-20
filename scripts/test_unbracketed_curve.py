#!/usr/bin/env python3
"""CPU-only checks using the existing fake MLX; no performance claims."""
import json
import os
import tempfile
import types
from pathlib import Path
from test_compiled_curve_source import install, load_micro, K, COLS

mod = load_micro()
failures = []
try:
    mod.require_sync(types.SimpleNamespace())
except SystemExit:
    pass
else:
    failures.append("missing sync API was accepted")

plan = [{"block": 0, "w": 1, "steps": 2}, {"block": 0, "w": 2, "steps": 2}]
previous = os.environ.pop("MLX_OMARCHY_GPU_PROFILE", None)
try:
    with tempfile.TemporaryDirectory() as td:
        args = types.SimpleNamespace(out=str(Path(td) / "wall.json"), profile="unused")
        core = install()
        mod.pass_unbracketed(args, K, COLS, plan)
        result = json.loads(Path(args.out).read_text())
        qmm_calls = [e for e in core.log if e[0] == "qmm"]
        if len(qmm_calls) != 3 * (2 + 4):
            failures.append("unprofiled path did not use the three-member compiled graph")
        if sum(e[0] == "sync" for e in core.log) != 1 + len(plan):
            failures.append("unprofiled path lacks synchronized segment endpoints")
        if result.get("pass") != "compiled-unbracketed" or result.get("profile_path") is not None:
            failures.append("unprofiled identity is missing or incorrectly labeled")
        if result.get("outputs_finite") is not True or len(result.get("walls", [])) != len(plan):
            failures.append("unprofiled finite/segment evidence is missing")
        os.environ["MLX_OMARCHY_GPU_PROFILE"] = str(Path(td) / "forbidden.ndjson")
        core = install()
        try:
            mod.pass_unbracketed(args, K, COLS, plan)
        except SystemExit:
            if core.log:
                failures.append("profiler rejection occurred after device work")
        else:
            failures.append("unprofiled pass accepted an enabled profiler")
finally:
    os.environ.pop("MLX_OMARCHY_GPU_PROFILE", None)
    if previous is not None:
        os.environ["MLX_OMARCHY_GPU_PROFILE"] = previous
assert not failures, "; ".join(failures)
print("PASS: sync capability guard, shared compiled route, synchronized walls, profiler exclusion")
