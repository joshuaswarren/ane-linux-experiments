#!/usr/bin/env python3
"""Read 10 paired contract JSONs and compute the paired mean delta +
95% t-CI on decode tok/s (and on TTFT). Mirrors the gate window-b.sh
output table from the t6001 sdpa-decode-hd256 receipt.

Usage: paired_decode.py <OUT_DIR> <TAG>
Reads <OUT_DIR>/contract-{ctl,cand}-<TAG>-r{1..10}.json and emits
<OUT_DIR>/paired-<TAG>.md.
"""
import argparse, glob, json, math, os, sys

def summarize(values):
    n = len(values)
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    se = sd / math.sqrt(n) if n > 0 else 0.0
    return mean, sd, se

def t_critical_95(df):
    # Two-tailed t critical values for 95% CI, df=1..10 (lookup)
    table = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
             6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
             11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
             16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
    return table.get(df, 2.0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    p.add_argument("--tag", required=True)
    a = p.parse_args()
    ctl, cand = [], []
    for i in range(1, 11):
        c = os.path.join(a.out_dir, f"contract-ctl-{a.tag}-r{i}.json")
        x = os.path.join(a.out_dir, f"contract-cand-{a.tag}-r{i}.json")
        if not (os.path.exists(c) and os.path.exists(x)):
            print(f"missing rep {i}", file=sys.stderr); sys.exit(2)
        ctl.append(json.load(open(c))["decode_tok_rate"]["median"])
        cand.append(json.load(open(x))["decode_tok_rate"]["median"])
    diffs = [cand[i] - ctl[i] for i in range(len(ctl))]
    m, sd, se = summarize(diffs)
    df = len(diffs) - 1
    t = t_critical_95(df)
    lo, hi = m - t * se, m + t * se
    ratio = (sum(cand) / len(cand)) / (sum(ctl) / len(ctl))
    with open(os.path.join(a.out_dir, f"paired-{a.tag}.md"), "w") as f:
        f.write(f"# paired decode tok/s, n={len(ctl)}\n\n")
        f.write("| rep | ctl | cand | delta |\n| ---: | ---: | ---: | ---: |\n")
        for i, (c, x, d) in enumerate(zip(ctl, cand, diffs), 1):
            f.write(f"| {i} | {c:.3f} | {x:.3f} | {d:+.3f} |\n")
        f.write(f"\n| | mean | sd | SE | 95% CI |\n| --- | ---: | ---: | ---: | --- |\n")
        f.write(f"| paired delta | {m:+.3f} | {sd:.3f} | {se:.3f} | [{lo:+.3f}, {hi:+.3f}] |\n")
        f.write(f"\nratio (cand/ctl): {ratio:.4f}\n")
        f.write(f"\nCI entirely positive: {'YES' if lo > 0 else 'NO'}\n")
    print(f"paired mean delta = {m:+.3f} +/- {t*se:.3f} (95% CI), ratio = {ratio:.4f}")
    print(f"CI entirely positive: {'YES' if lo > 0 else 'NO'}")


if __name__ == "__main__":
    main()
