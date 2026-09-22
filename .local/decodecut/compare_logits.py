import json, sys
a = json.load(open(sys.argv[1]))  # candidate
b = json.load(open(sys.argv[2]))  # baseline
fa = {(r["prompt_idx"], s): st for r in a["records"] for s, st in enumerate(r["steps"])}
flips = []
maxd = 0.0
n = 0
for r in b["records"]:
    for s, st in enumerate(r["steps"]):
        ca = fa[(r["prompt_idx"], s)]
        n += 1
        if ca["chosen"] != st["chosen"]:
            flips.append((r["prompt_idx"], s, st["chosen"], ca["chosen"],
                          st["margin"]))
        # delta on baseline's chosen token logit
        base_logit = next(e["logit"] for e in st["top"] if e["id"] == st["chosen"])
        cand_logit = next((e["logit"] for e in ca["top"] if e["id"] == st["chosen"]), None)
        if cand_logit is not None:
            maxd = max(maxd, abs(cand_logit - base_logit))
print(f"steps compared: {n}")
print(f"argmax flips: {len(flips)}")
for f in flips[:20]:
    print("  flip prompt=%d step=%d base=%d cand=%d margin=%.3f" % f)
print(f"max |delta logit| on baseline-chosen token: {maxd:.4f}")
