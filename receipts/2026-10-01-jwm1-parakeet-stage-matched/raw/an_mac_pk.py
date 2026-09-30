import os
import glob
import re
import statistics as st

root = os.path.expanduser("~/.local/share/apple-silicon-lab/artifacts/jwm1-parity/parakeet-corpus/macos/")
for clip in ("fixture_v03", "fixture_v1", "fixture_v5", "fixture_v10", "fixture", "1089-134686-0000"):
    vals = {"mel": [], "encoder": [], "decode": [], "inference": []}
    for f in sorted(glob.glob(root + clip + ".r*.err")):
        t = open(f).read()
        for k in vals:
            m = re.search(rf"^\s*{k}:\s+([0-9.]+) s", t, re.M)
            if m:
                vals[k].append(float(m.group(1)) * 1e3)
    if vals["inference"]:
        print(clip, "n", len(vals["inference"]), {k: round(st.median(v), 1) for k, v in vals.items()})
