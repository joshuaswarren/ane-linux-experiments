#!/usr/bin/env python3
"""Identify scanned tunable tables by matching against m1n1 tunables_static
(flag-stripped), reporting exact and near matches with diffs."""
import struct, sys

sys.path.insert(0, "/var/tmp/tunables")
from extract_tunables import (T8103_SEQS, table_bytes)

def norm(entries):
    return [(off & 0x0fffffff, clr, setv) for off, clr, setv in entries]

def parse_tables(text):
    tables = []
    cur = None
    for line in text.splitlines():
        if line.startswith("TABLE"):
            _, fo, va, seg, n = line.split()
            cur = {"file": int(fo.split("=")[1], 16),
                   "va": int(va.split("=")[1], 16),
                   "seg": seg.split("=")[1],
                   "entries": []}
            tables.append(cur)
        elif line.startswith("    {") and cur is not None:
            a, b, c = [int(x, 16) for x in line.strip(" {}").split(",")]
            cur["entries"].append((a, b, c))
    return tables

def main(scan_txt):
    tables = parse_tables(open(scan_txt).read())
    for name, entries, base in T8103_SEQS:
        want = norm(entries)
        exact = []
        near = []
        for t in tables:
            got = norm(t["entries"])
            if got == want:
                exact.append(t)
            else:
                # near match: same offset sequence, some value diffs
                if [e[0] for e in got] == [e[0] for e in want]:
                    near.append((t, got))
        tag = f"{name} (m1n1 n={len(want)}, base={base:#x})"
        if exact:
            for t in exact:
                print(f"MATCH  {tag}: file={t['file']:#x} va={t['va']:#x} seg={t['seg']} n={len(t['entries'])}")
        else:
            print(f"NOMATCH {tag}")
            for t, got in near:
                diffs = [(w, g) for w, g in zip(want, got) if w != g]
                print(f"  NEAR file={t['file']:#x} va={t['va']:#x} n={len(got)} diffs={diffs[:6]}")
    unlabeled = []
    matched = set()
    for name, entries, base in T8103_SEQS:
        want = norm(entries)
        for t in tables:
            if norm(t["entries"]) == want:
                matched.add(t["file"])
    for t in tables:
        if t["file"] not in matched:
            unlabeled.append(t)
    print(f"\n# unlabeled tables: {len(unlabeled)}")
    for t in unlabeled:
        offs = [e[0] for e in t["entries"]]
        print(f"  file={t['file']:#x} va={t['va']:#x} n={len(t['entries'])} "
              f"off_range={min(offs):#x}-{max(offs):#x} first={t['entries'][0]} last={t['entries'][-1]}")

if __name__ == "__main__":
    main(sys.argv[1])
