#!/usr/bin/env python3
"""Analyze the Linux ANE Qwen contract run (passes w1-w3 warmup, r01-r10 measured) against the macOS ANEForge record.
usage: analyze_qwen_contract.py RUN_DIR MACOS_JSON [--boot 10000]
Reports: completeness, determinism across reps (ids + logits), per-prompt e2e median with percentile-bootstrap CI,
Linux/macOS e2e ratio per prompt (paired by prompt) with CI, first-divergence vs macOS per prompt."""
import glob
import json
import random
import statistics as st
import sys
from pathlib import Path

import numpy as np

run = Path(sys.argv[1])
mac = json.load(open(sys.argv[2]))["per_prompt"]
nboot = int(sys.argv[sys.argv.index("--boot") + 1]) if "--boot" in sys.argv else 10000
passes = sorted(p.name for p in run.iterdir() if p.is_dir())
meas = [p for p in passes if p.startswith("r")]
print("passes present:", passes)
mac_by = {}
for r in mac:
    mac_by.setdefault(r["prompt_idx"], []).append(r)
rng = random.Random(0)


def boot_ci(xs):
    xs = list(xs)
    meds = sorted(st.median(rng.choices(xs, k=len(xs))) for _ in range(nboot))
    return meds[int(0.025 * nboot)], meds[int(0.975 * nboot) - 1]


rows = []
for i in range(10):
    pid = f"p{i + 1:03d}"
    recs = []
    for p in meas:
        f = run / p / f"{pid}.json"
        if f.exists():
            r = json.load(open(f))["prompts"][0]["runs"][0]
            lg = np.load(run / p / f"{pid}-logits.npy")["run_000"]
            recs.append((p, r, lg))
    if not recs:
        print(pid, "no measured reps yet")
        continue
    ids0, lg0 = recs[0][1]["generated_ids"], recs[0][2]
    ident = sum(r["generated_ids"] == ids0 and np.array_equal(lg, lg0) for _, r, lg in recs)
    e2e = [r["step_seconds"] + r["logits_seconds"] for _, r, _ in recs]
    m = mac_by[i][0]["output_ids"]
    div = next((k for k, (a, b) in enumerate(zip(ids0, m)) if a != b), None)
    mac_e2e = [x["e2e_s"] for x in mac_by[i]]
    lo, hi = boot_ci(e2e)
    ratios = [a / b for a in e2e for b in mac_e2e]
    rlo, rhi = boot_ci(ratios)
    rows.append((pid, len(recs), ident, st.median(e2e), lo, hi, st.median(mac_e2e), st.median(ratios), rlo, rhi, div))
    print(f"{pid} reps={len(recs)} bit-identical={ident}/{len(recs)} linux e2e med {st.median(e2e):.1f}s CI[{lo:.1f},{hi:.1f}] "
          f"macOS med {st.median(mac_e2e):.2f}s ratio {st.median(ratios):.0f}x CI[{rlo:.0f},{rhi:.0f}] first-div-vs-macOS {div}")
if rows:
    print("prompts fully matching macOS over 32 tokens:", sum(r[10] is None for r in rows), "/", len(rows))
    print("median Linux/macOS e2e ratio across prompts:", round(st.median(r[7] for r in rows)))
