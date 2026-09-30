#!/usr/bin/env python3
"""Analyze the Linux ANE Qwen contract run (passes w1-w3 warmup, r01-r10 measured) against the macOS ANEForge record.
usage: analyze_qwen_contract.py RUN_DIR MACOS_JSON [--boot 10000] [--first-run DIR] [--cpu-ref DIR]
Reports: completeness, determinism across reps (ids + logits) and vs --first-run, per-prompt e2e median with
percentile-bootstrap CI and per-token latency, Linux/macOS e2e ratio per prompt (paired by prompt) with CI,
first-divergence vs macOS and vs the fp32 CPU reference (--cpu-ref)."""
import argparse
import json
import random
import statistics as st
from pathlib import Path

import numpy as np


def ids_of(path):
    return json.load(open(path))["prompts"][0]["runs"][0]["generated_ids"]


def logits_of(path):
    return np.load(path)["run_000"]


def first_div(a, b):
    return next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("macos_json", type=Path)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--first-run", type=Path, help="original 10-prompt run dir for bit-identity check")
    ap.add_argument("--cpu-ref", type=Path, help="fp32 CPU reference dir for first-divergence")
    args = ap.parse_args()
    run = args.run_dir
    mac = json.load(open(args.macos_json))["per_prompt"]
    nboot = args.boot
    passes = sorted(p.name for p in run.iterdir() if p.is_dir())
    meas = [p for p in passes if p.startswith("r")]
    print("passes present:", passes, "measured:", meas)
    mac_by = {}
    for r in mac:
        mac_by.setdefault(r["prompt_idx"], []).append(r)
    first_by, cpu_by = {}, {}
    if args.first_run:
        for f in args.first_run.glob("p*.json"):
            first_by[f.stem] = (ids_of(f), logits_of(args.first_run / f"{f.stem}-logits.npy"))
    if args.cpu_ref:
        for f in args.cpu_ref.glob("p*.json"):
            cpu_by[f.stem] = ids_of(f)
    rng = random.Random(0)
    # per-prompt e2e = the in-process "=== <id> done rc=0 wall=<s>" marker in <pass>.log (tokenize + prompt steps +
    # 32 logits/steps + save). The first prompt completed after each "##### attempt" marker is first-in-process
    # (carries first-use cache costs); it is excluded from e2e and summarized separately.
    wall, first_proc = {}, []
    for p in meas:
        log = run / f"{p}.log"
        if not log.exists():
            continue
        fresh = True
        for line in log.read_text(errors="replace").splitlines():
            if line.startswith("##### attempt"):
                fresh = True
            elif line.startswith("=== ") and " done rc=0 wall=" in line:
                pid, secs = line.split()[1], float(line.rsplit("wall=", 1)[1].rstrip("s"))
                if fresh:
                    first_proc.append(secs)
                else:
                    wall[(p, pid)] = secs
                fresh = False

    def boot_ci(xs):
        xs = list(xs)
        meds = sorted(st.median(rng.choices(xs, k=len(xs))) for _ in range(nboot))
        return meds[int(0.025 * nboot)], meds[int(0.975 * nboot) - 1]

    rows, gate = [], {}
    for i in range(10):
        pid = f"p{i + 1:03d}"
        recs = []
        for p in meas:
            f = run / p / f"{pid}.json"
            if f.exists():
                recs.append((p, ids_of(f), logits_of(run / p / f"{pid}-logits.npy")))
        if not recs:
            print(pid, "no measured reps yet")
            continue
        ids0, lg0 = recs[0][1], recs[0][2]
        ident = sum(ids == ids0 and np.array_equal(lg, lg0) for _, ids, lg in recs)
        extra = ""
        if pid in first_by:
            fid, flg = first_by[pid]
            extra += (f" vs-first-run(ids,logits)=({'EQ' if fid == ids0 else 'DIFF'},"
                      f"{'EQ' if np.array_equal(flg, lg0) else 'DIFF'})")
        e2e = [wall[(p, pid)] for p, _, _ in recs if (p, pid) in wall]
        div_mac = first_div(ids0, mac_by[i][0]["output_ids"])
        gate[pid] = all(first_div(ids, mac_by[i][0]["output_ids"]) is None for _, ids, _ in recs)
        div_cpu = first_div(ids0, cpu_by[pid]) if pid in cpu_by else None
        if not e2e:
            print(pid, f"reps={len(recs)} bit-identical={ident}/{len(recs)}{extra} "
                       f"first-div-vs-macOS {div_mac} vs-cpu-ref {div_cpu} (no steady-state e2e sample)")
            continue
        mac_e2e = [x["e2e_s"] for x in mac_by[i]]
        lo, hi = boot_ci(e2e)
        ratios = [a / b for a in e2e for b in mac_e2e]
        rlo, rhi = boot_ci(ratios)
        rows.append((pid, div_mac, st.median(ratios)))
        spread = (max(e2e) - min(e2e)) / st.median(e2e) * 100
        print(f"{pid} reps={len(recs)} bit-identical={ident}/{len(recs)}{extra} "
              f"linux e2e n={len(e2e)} med {st.median(e2e):.1f}s CI[{lo:.1f},{hi:.1f}] spread {spread:.2f}% "
              f"per-token {st.median(e2e) / 32.0 * 1000:.0f}ms "
              f"macOS med {st.median(mac_e2e):.2f}s ratio {st.median(ratios):.0f}x CI[{rlo:.0f},{rhi:.0f}] "
              f"first-div-vs-macOS {div_mac} vs-cpu-ref {div_cpu}")
    if first_proc:
        print(f"first-in-process prompts (excluded from e2e): n={len(first_proc)} walls={[round(x) for x in first_proc]}")
    if gate:
        print("prompts matching macOS on all 32 tokens in every measured rep:", sum(gate.values()), "/", len(gate))
    if rows:
        print("median Linux/macOS e2e ratio across prompts:", round(st.median(r[2] for r in rows)))


if __name__ == "__main__":
    main()
