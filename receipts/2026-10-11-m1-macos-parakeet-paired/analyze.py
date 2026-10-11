"""analyze.py <results dir> <gold_f16.bin>: medians per arm from run-*.json, placement, bit-exact check of the dumps against gold."""
import glob
import json
import re
import statistics as st
import sys

import numpy as np

d, gold = sys.argv[1], sys.argv[2]
g = np.fromfile(gold, dtype=np.float16)
rows = {}
for p in sorted(glob.glob(d + "/run-*.json")):
    txt = open(p).read()
    m = re.search(r"^(\{.*\})$", txt, re.M)
    t = re.search(r"times_ms \[(.*?)\]", txt)
    if not (m and t):
        print(p, "UNPARSED", txt[:120])
        continue
    j = json.loads(m.group(1))
    ts = [float(x) for x in t.group(1).split(",")]
    arm = j["units"]
    out = np.fromfile(p.replace("run-", "out-").replace(".json", ".bin"), dtype=np.float32).astype(np.float16)
    ok = out.size == g.size and int((out != g).sum())
    print(p.split("/")[-1], "median", st.median(ts), "min", min(ts), "max", max(ts), "n", len(ts), "placement", j.get("placement"), "load_ms", j.get("load_ms"), "mismatch_words", ok)
    rows.setdefault(arm, []).extend(ts)
for arm, ts in rows.items():
    print(arm, "pooled median", round(st.median(ts), 2), "n", len(ts))
