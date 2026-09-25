#!/usr/bin/env python3
"""Compare logitpin.py outputs against a reference: per run, the number of
steps whose logprob vector differs bitwise, the first such step, and how many
of those also changed the argmax (a divergence cascades: after the first
changed token every later step differs, so the cascade is collapsed to its
first step per prompt)."""
import json, sys
ref = json.load(open(sys.argv[1]))
rmap = {(r["pass"], r["prompt"], r["step"]): r for r in ref["steps"]}
for path in sys.argv[2:]:
    j = json.load(open(path))
    diff, first_by_prompt, cascade = 0, {}, set()
    for r in j["steps"]:
        k = (r["pass"], r["prompt"], r["step"])
        a = rmap.get(k)
        if a is None:
            continue
        key = (r["pass"], r["prompt"])
        if key in cascade:
            continue
        if a["sha"] != r["sha"]:
            diff += 1
            first_by_prompt.setdefault(key, (r["step"], a["token"] != r["token"], a["margin"]))
            if a["token"] != r["token"]:
                cascade.add(key)
    desc = " ".join(f"[pass {p} prompt {q}: step {s}{' TOKEN-FLIP' if fl else ''} margin={m:.3g}]"
                    for (p, q), (s, fl, m) in sorted(first_by_prompt.items()))
    print(f"{j['label']:20s} logit={j['logit_digest']} ids={j['ids_digest']} "
          f"differing_steps(pre-cascade)={diff} prompts_touched={len(first_by_prompt)} {desc}")
