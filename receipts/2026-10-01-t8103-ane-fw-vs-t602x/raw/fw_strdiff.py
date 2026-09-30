import re


def srcs(p):
    d = open(p, "rb").read()
    s = set(m.group().decode() for m in re.finditer(rb"\./sne/[A-Za-z0-9_/]+\.cpp", d))
    allstr = set(m.group().decode() for m in re.finditer(rb"[ -~]{8,}", d))
    return s, allstr


h13, h13all = srcs("/tmp/h131b/h13_135.bin")
sel, selall = srcs("/tmp/h131b/selene_135.bin")
print("h13 (13.5) source files:", len(h13), " selene (13.5):", len(sel))
print("only in H13:", sorted(h13 - sel))
print("only in selene:", sorted(sel - h13))
keys = [s for s in sorted(h13all ^ selall) if re.search(r"Scratch|SCRATCH|Mailbox|mailbox|boot|Boot|PowerControl|Pmgr|PMGR|DART|Dart|tunable|Tunable|RTKit|RTBuddy|endpoint|Endpoint", s)]
for s in keys[:40]:
    print(("H13 " if s in h13all else "SEL ") + s[:130])
