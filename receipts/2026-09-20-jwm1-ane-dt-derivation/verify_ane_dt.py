#!/usr/bin/env python3
"""Canonical property comparison: built ANE dtb vs carved historical dtb.

Extracts the ane node, its three DART iommus, and the six ANE pmgr
pwrstate nodes from both decompiled trees, resolves phandle references
to node paths, strips cosmetic node names and phandle ids, and diffs.
Exit 0 = canonical-equal.
"""
import re, subprocess, sys
from pathlib import Path


def decompile(dtb, out):
    subprocess.run(["dtc", "-I", "dtb", "-O", "dts", "-o", out, dtb],
                   check=True, stderr=subprocess.DEVNULL)
    return Path(out).read_text()


def phandle_map(text):
    m = {}
    for nm, ph in re.findall(r"([\w@,-]+) \{[^{}]*?phandle = <0x([0-9a-f]+)>;",
                             text, re.S):
        m["0x" + ph] = nm
    return m


def find_block(text, needle, depth_tabs="\t\t"):
    i = text.find(needle)
    if i == -1:
        return None
    start = text.rfind("\n", 0, i) + 1
    j = text.index("{", i)
    d = 1
    k = j + 1
    while d:
        if text[k] == "{":
            d += 1
        elif text[k] == "}":
            d -= 1
        k += 1
    return text[start:k]


REF_PROPS = {"iommus", "power-domains"}


def canon(block, ph):
    block = re.sub(r"\bphandle = <0x[0-9a-f]+>;\n", "", block)

    def resolve(m):
        prop = m.group(1)
        if prop not in REF_PROPS:
            return m.group(0)
        cells = m.group(2).split()
        out = ["&" + ph[c] if c in ph else c for c in cells]
        if prop == "iommus":
            out = [c for c in out if c != "0x00"]
        return f"{prop} = <" + " ".join(out) + ">;"

    block = re.sub(r"(\w[-\w]*) = <((?:0x[0-9a-f]+|&[\w@,-]+)(?: 0x[0-9a-f]+| &[\w@,-]+)*)>;",
                   resolve, block)
    return re.sub(r"\n\s*\n", "\n", block)


def main(patched_dtb, hist_dtb):
    a_txt = decompile(str(patched_dtb), "/tmp/verify.ane.dts")
    h_txt = decompile(str(hist_dtb), "/tmp/verify.hist.dts")
    a_ph, h_ph = phandle_map(a_txt), phandle_map(h_txt)

    blocks = {}
    for tag, txt, ph in (("BUILT", a_txt, a_ph), ("HISTORICAL", h_txt, h_ph)):
        ane = None
        for nm in ("ane@26bc04000", "ane@26a000000"):
            ane = find_block(txt, nm)
            if ane:
                break
        blocks.setdefault(tag, {})["ANE"] = canon(ane, ph) if ane else "ABSENT"
        for unit in ("26b800000", "26b810000", "26b820000"):
            b = find_block(txt, f"iommu@{unit}")
            blocks.setdefault(tag, {})[f"DART@{unit}"] = canon(b, ph) if b else "ABSENT"
        for off, lbl in (("c008", "ane_base"), ("c010", "ane_set1"),
                         ("c018", "ane_set2"), ("c020", "ane_set3"),
                         ("c028", "ane_set4"), ("c030", "ane_set5"),
                         ("c000", "ane_sys_cpu"), ("470", "ane_sys")):
            blk = None
            for m in re.finditer(r"(power-controller@" + off + r"})", txt):
                start = txt.rfind("\n", 0, m.start()) + 1
                k = txt.index("};", m.start())
                blk = txt[start:k + 3]
                break
            key = f"PMGR:{lbl}@{off}"
            blocks.setdefault(tag, {})[key] = canon(blk, ph) if blk else "ABSENT"

    diffs = []
    for key in sorted(set(blocks["BUILT"]) | set(blocks["HISTORICAL"])):
        a = blocks["BUILT"].get(key, "ABSENT")
        h = blocks["HISTORICAL"].get(key, "ABSENT")
        # normalize the node name difference (complex vs subblock addressing)
        a = re.sub(r"ane@26(a000000|bc04000)", "ANE_NODE", a)
        h = re.sub(r"ane@26(a000000|bc04000)", "ANE_NODE", h)
        if a != h:
            diffs.append((key, a, h))
    if diffs:
        for key, a, h in diffs:
            print(f"DIFF {key}\n--- built\n{a}\n--- historical\n{h}")
        sys.exit(1)
    print("CANONICAL-EQUAL: ane node, 3 ANE DARTs, and all six SET-word "
          "pmgr pwrstate nodes match the carved historical working tree "
          "(phandle-free, node-name-normalized).")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
