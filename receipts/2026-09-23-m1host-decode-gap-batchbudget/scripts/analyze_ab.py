#!/usr/bin/env python3
"""Paired A/B analysis over contract-<tag>-r<rep>.json files.
Paired by rep index; 95% CI via t distribution (df = n-1). Also checks
ordered-records digest identity across every run file."""
import glob, json, math, os, re, sys

d = sys.argv[1] if len(sys.argv) > 1 else "."

def load(tag):
    out = {}
    for f in glob.glob(os.path.join(d, f"contract-{tag}-r*.json")):
        rep = int(re.search(r"-r(\d+)\.json$", f).group(1))
        out[rep] = json.load(open(f))
    return out

ctl, cand = load("ctl"), load("cand")
reps = sorted(set(ctl) & set(cand))
print(f"paired reps: {reps}")

# digest identity across ALL runs (both arms)
digests = set()
for tag, runs in (("ctl", ctl), ("cand", cand)):
    for r, j in runs.items():
        digests.add(j["ordered_records_sha256"])
print(f"distinct ordered_records_sha256 across {sum(len(x) for x in (ctl, cand))} runs: {len(digests)}")
for dg in digests:
    print("  ", dg)

for metric in ("decode_tok_rate", "ttft_tok_rate"):
    c = [ctl[r]["decode_tok_rate"]["median"] if metric == "decode_tok_rate" else ctl[r][metric]["median"] for r in reps]
    g = [cand[r][metric]["median"] for r in reps]
    diffs = [b - a for a, b in zip(c, g)]
    n = len(diffs)
    mean = sum(diffs) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in diffs) / (n - 1)) if n > 1 else 0.0
    t95 = 2.262 if n == 10 else 2.0
    ci = t95 * sd / math.sqrt(n)
    cm, gm = sum(c) / n, sum(g) / n
    print(f"\n{metric}:")
    print(f"  ctl  per-rep: {[round(x, 2) for x in c]}  mean {cm:.2f}")
    print(f"  cand per-rep: {[round(x, 2) for x in g]}  mean {gm:.2f}")
    print(f"  paired delta: {mean:+.3f} +/- {ci:.3f} tok/s (95%, t, df={n-1})")
    print(f"  ratio cand/ctl: {gm/cm:.4f} ({(gm/cm-1)*100:+.1f}%)")

# prefill leg
pf_ctl = [ctl[r]["pure_prefill"]["tok_s"] for r in reps if ctl[r].get("pure_prefill")]
pf_cand = [cand[r]["pure_prefill"]["tok_s"] for r in reps if cand[r].get("pure_prefill")]
if pf_ctl and pf_cand:
    print(f"\npure_prefill tok/s: ctl mean {sum(pf_ctl)/len(pf_ctl):.2f}  cand mean {sum(pf_cand)/len(pf_cand):.2f}")
