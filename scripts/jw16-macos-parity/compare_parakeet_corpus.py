#!/usr/bin/env python3
"""Compare macOS CoreML Parakeet CLI outputs (ane/gpu arms) with the Linux pipeline (full vs mask valid-frames).
usage: compare_parakeet_corpus.py ARTIFACT_DIR  (dir with manifest.json, pk-full.jsonl, pk-mask3.jsonl, and ../macos-window-3/out-corpus)"""
import json
import re
import statistics as st
import sys
from pathlib import Path

d = Path(sys.argv[1])
mac = d.parent / "macos-window-3" / "out-corpus"
man = json.loads((d / "manifest.json").read_text())
load = lambda f: [json.loads(x) for x in open(d / f)]  # noqa: E731
full, mask = load("pk-full.jsonl"), load("pk-mask3.jsonl")


def norm(s):
    return re.sub(r"[^a-z' ]", " ", s.lower()).split()


def wer(ref, hyp):
    a, b = norm(ref), norm(hyp)
    if not a:
        return float(len(b) > 0)
    dist = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, dist[0] = dist[:], i
        for j, y in enumerate(b, 1):
            dist[j] = min(prev[j] + 1, dist[j - 1] + 1, prev[j - 1] + (x != y))
    return dist[len(b)] / len(a)


def timing(path):
    t = path.read_text()
    g = lambda k: (float(m.group(1)) if (m := re.search(k + r":\s+([\d.]+) s", t)) else None)  # noqa: E731
    return {"mel": g("mel"), "enc": g("encoder"), "dec": g("decode"), "inf": g("inference")}


rows = []
print("clip | sec | mac ane == mac gpu | Linux full == mac ane | Linux mask == mac ane | WER(linux full vs mac ane) | WER(mac ane vs ref) | mac ane inf s | linux full total ms | linux mask total ms")
for m in man:
    n = m["file"][:-5]
    ane = (mac / f"ane-{n}-r2.txt").read_text().strip()
    gpu = (mac / f"gpu-{n}-r2.txt").read_text().strip()
    lf = [r for r in full if r["file"] == m["file"] and r["status"] == "ok"]
    lm = [r for r in mask if r["file"] == m["file"] and r["status"] == "ok"]
    lft = lf[0]["transcript"].strip()
    lmt = lm[0]["transcript"].strip()
    ti = [timing(mac / f"ane-{n}-r{k}.err")["inf"] for k in (2, 3)]
    rows.append((m["sec"], ane == gpu, lft == ane, lmt == ane, wer(ane, lft), wer(m["text"], ane)))
    print(f"{m['file']} | {m['sec']} | {ane == gpu} | {lft == ane} | {lmt == ane} | {wer(ane, lft):.3f} | {wer(m['text'], ane):.3f} | {st.median(ti):.3f} | {st.median([r['total_ms'] for r in lf]):.0f} | {st.median([r['total_ms'] for r in lm]):.0f}")
print("exact Linux(full)==macOS(ane):", sum(r[2] for r in rows), "/", len(rows))
print("exact Linux(mask)==macOS(ane):", sum(r[3] for r in rows), "/", len(rows))
print("mean WER linux full vs mac ane:", round(st.mean(r[4] for r in rows), 4))
