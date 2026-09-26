#!/usr/bin/env python3
"""Regression: the contract-shape comparator must REJECT comparing runs
with different prompt counts (the 2026-09-26 flip incident: a --limit 1
digest 100a61b6 was compared against the --limit 10 pin 486872c4 and read
as a machine-state flip). Also: identical shapes must be accepted, and
missing keys must be rejected. Exit 0 = all pass."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import only the comparator pieces without pulling in mlx (which the bench
# imports at main()-module scope). Replicate the two pure functions from
# qwen38-mlx-bench.py via exec of their source blocks.
import re
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "qwen38-mlx-bench.py")).read()
ns = {}
for fn in ("contract_shape", "shapes_compatible"):
    m = re.search(rf"^def {fn}\(.*?(?=^def |\Z)", src, re.M | re.S)
    assert m, f"{fn} not found in bench source"
    exec(m.group(0), ns)
contract_shape = ns["contract_shape"]
shapes_compatible = ns["shapes_compatible"]


class Args:
    def __init__(self, warmup, passes, new_tokens, prefill, limit):
        self.warmup = warmup
        self.passes = passes
        self.new_tokens = new_tokens
        self.prefill_tokens = prefill
        self.limit = limit  # unused by contract_shape; prompts_per_pass set by caller


CORPUS = "9299a3b2fc136a4c0c355f9ad3e211be81823a5fb9eeadbc2e6608fb3e5718a0"
IDENT = "fedcba9876543210"


def shape(warmup, prompts_per_pass, passes=1, new_tokens=32, prefill=512):
    return {"prompts_per_pass": prompts_per_pass, "warmup": warmup,
            "passes": passes, "new_tokens": new_tokens,
            "prefill_leg_tokens": prefill, "prompts_corpus_sha256": CORPUS,
            "prompts_identity_sha256": IDENT}


failures = []

# 1. DIFFERENT prompt count must be rejected (the regression).
ok, why = shapes_compatible(shape(3, 10), shape(3, 1))
if ok:
    failures.append("different prompts_per_pass was accepted")

# 2. DIFFERENT warmup must be rejected.
ok, why = shapes_compatible(shape(3, 10), shape(1, 10))
if ok:
    failures.append("different warmup was accepted")

# 3. Identical shapes must be accepted.
ok, why = shapes_compatible(shape(3, 10), shape(3, 10))
if not ok:
    failures.append(f"identical shapes rejected: {why}")

# 4. contract_shape() with different args.limit must produce the same
#    shape (limit is NOT part of the fingerprint beyond prompts_per_pass
#    which the caller fills) — the guard keys on prompts_per_pass.
a10 = Args(3, 10, 32, 512, 10)
a1 = Args(3, 1, 32, 512, 1)
s10 = contract_shape(a10, CORPUS)
s1 = contract_shape(a1, CORPUS)
if s10 == s1:
    failures.append("contract_shape does not distinguish different --limit")

# 5. Missing shape keys must be rejected.
ok, why = shapes_compatible({}, shape(3, 10))
if ok:
    failures.append("missing keys were accepted")

# 6. The full-arg path: contract_shape with the Args used by main() must
#    embed prompts_per_pass via the caller (dict merge) and then differ
#    across prompt counts.
s_full_10 = dict(contract_shape(a10, CORPUS), prompts_per_pass=10,
                 prompts_identity_sha256=IDENT)
s_full_1 = dict(contract_shape(a1, CORPUS), prompts_per_pass=1,
                prompts_identity_sha256=IDENT)
ok, why = shapes_compatible(s_full_10, s_full_1)
if ok:
    failures.append("full-shape different prompt count was accepted")

if failures:
    print("SHAPE-GUARD REGRESSION FAILURES:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("shape-guard regression: all cases pass "
      "(different prompt count rejected, identical accepted, missing keys rejected)")
