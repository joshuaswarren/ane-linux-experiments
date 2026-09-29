import glob, json, statistics as st, sys, os
pins = {"d64": "7fe6badf4d560e25", "d128": "da5568eeb4b6a1c1", "d256": "828b55d6249d9679",
        "pf512": "ccb601895581d89f", "pf2048": "ccb601895581d89f"}
base = sys.argv[1]
for cell, pin in pins.items():
    rows = {}
    for f in sorted(glob.glob(f"{base}/h33-{cell}/*.json")):
        arm = os.path.basename(f)[0]
        d = json.load(open(f))
        dig = d["ordered_records_sha256"][:16]
        if cell.startswith("pf"):
            v = d["pure_prefill"]["pure_prefill_tok_rate"]
        else:
            v = d["decode_tok_rate"]["median"] if isinstance(d["decode_tok_rate"], dict) else None
        rows.setdefault(arm, []).append((v, dig))
    if not rows:
        continue
    med = {a: st.median(v for v, _ in r) for a, r in rows.items()}
    bad = [(a, dg) for a, r in rows.items() for _, dg in r if dg != pin and not cell.startswith("pf")]
    print(cell, "n", {a: len(r) for a, r in rows.items()}, "median", {a: round(m, 2) for a, m in med.items()},
          "ratio b/a", round(med["b"] / med["a"], 4), "c/a", round(med["c"] / med["a"], 4),
          "digest_mismatch", bad, "digests", sorted({dg for r in rows.values() for _, dg in r}))
