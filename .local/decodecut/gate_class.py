import json, sys
import numpy as np

a = json.load(open(sys.argv[1] if len(sys.argv)>1 else "/var/tmp/decodecut/logits-fix.json"))
b = json.load(open("/tmp/q38c/logits-integ-m1-host.json"))
fa = {(r["prompt_idx"], s): st for r in a["records"] for s, st in enumerate(r["steps"])}
fb = {(r["prompt_idx"], s): st for r in b["records"] for s, st in enumerate(r["steps"])}

first_flip = {}
for p in range(10):
    for s in range(32):
        if fa[(p, s)]["chosen"] != fb[(p, s)]["chosen"]:
            first_flip[p] = s
            break

print("first flips:", first_flip)
# pre-divergence logit agreement: steps before each prompt's first flip
maxd = 0.0
for p in range(10):
    end = first_flip.get(p, 32)
    for s in range(end):
        base_top1 = fb[(p, s)]["top"][0]["logit"]
        cand_top1 = fa[(p, s)]["top"][0]["logit"]
        maxd = max(maxd, abs(base_top1 - cand_top1))
        for e in fb[(p, s)]["top"]:
            ce = next((x["logit"] for x in fa[(p, s)]["top"] if x["id"] == e["id"]), None)
            if ce is not None:
                maxd = max(maxd, abs(ce - e["logit"]))
print("max |delta logit| BEFORE first flip per prompt:", round(maxd, 4))
print("flip margins at first-flip steps:",
      {p: round(fb[(p, s)]["margin"], 3) for p, s in first_flip.items()})
