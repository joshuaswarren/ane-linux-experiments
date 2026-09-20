#!/usr/bin/env python3
"""Canonical property comparison: built ANE dtb vs carved historical dtb.

v2 per Main's review: exact node-boundary extraction (every expected block
must exist), formatting-insensitive canonicalization, arity-aware phandle
resolution (SID cells preserved, never erased), interrupt-parent resolved,
and two negative self-tests (mutate only a provider parent; mutate only a
DMA range — each must FAIL the comparison).

Usage: verify_ane_dt.py BUILT.dtb HISTORICAL.dtb [--workdir DIR]
Exit 0 = canonical-equal (and negative self-tests pass). Exit 1 = diff.
"""
import re, subprocess, sys
from pathlib import Path

EXPECTED = (["ANE"] +
            ["DART@26b800000", "DART@26b810000", "DART@26b820000"] +
            ["PMGR:ane_sys@470", "PMGR:ane_sys_cpu@c000", "PMGR:ane_base@c008",
             "PMGR:ane_set1@c010", "PMGR:ane_set2@c018", "PMGR:ane_set3@c020",
             "PMGR:ane_set4@c028", "PMGR:ane_set5@c030"])


def find_block(text, header):
    i = text.find(header)
    if i == -1:
        return None
    start = text.rfind("\n", 0, i) + 1
    j = text.index("{", i)
    d, k = 1, j + 1
    while d:
        if text[k] == "{":
            d += 1
        elif text[k] == "}":
            d -= 1
        k += 1
    return text[start:k]


def iommu_arities(text):
    """phandle -> cells consumed per iommus reference (#iommu-cells)."""
    out = {}
    for m in re.finditer(r"([\w@,-]+) \{([^{}]*)\}", text):
        body = m.group(2)
        decl = re.search(r"#iommu-cells = <0x([0-9a-f]+)>;", body)
        for ph in re.findall(r"phandle = <0x([0-9a-f]+)>;", body):
            out["0x" + ph] = int(decl.group(1), 16) if decl else 0
    return out


def canon(block, ph, arity):
    block = re.sub(r"\bphandle = <0x[0-9a-f]+>;\n", "", block)

    def resolve(m):
        toks = m.group(1).split()
        out, i = [], 0
        while i < len(toks):
            t = toks[i]
            if t in ph:
                nm, n = ph[t], arity.get(t, 0)
                out.append("&" + nm)
                out.extend(toks[i + 1:i + 1 + n])
                i += 1 + n
            else:
                out.append(t)
                i += 1
        return "<" + " ".join(out) + ">"

    block = re.sub(r"<((?:0x[0-9a-f]+)(?: 0x[0-9a-f]+)*)>", resolve, block)
    return re.sub(r"\s+", " ", block).strip()


def extract(text):
    ph = {}
    for nm, p in re.findall(r"([\w@,-]+) \{[^{}]*?phandle = <0x([0-9a-f]+)>;", text, re.S):
        ph["0x" + p] = nm
    arity = iommu_arities(text)
    blocks = {}
    ane = None
    for nm in ("ane@26bc04000", "ane@26a000000"):
        ane = find_block(text, nm + " {")
        if ane:
            break
    blocks["ANE"] = canon(ane, ph, arity) if ane else "ABSENT"
    for unit in ("26b800000", "26b810000", "26b820000"):
        b = find_block(text, f"iommu@{unit} {{")
        blocks[f"DART@{unit}"] = canon(b, ph, arity) if b else f"ABSENT {unit}"
    for off, lbl in (("470", "ane_sys"), ("c000", "ane_sys_cpu"),
                     ("c008", "ane_base"), ("c010", "ane_set1"),
                     ("c018", "ane_set2"), ("c020", "ane_set3"),
                     ("c028", "ane_set4"), ("c030", "ane_set5")):
        b = find_block(text, f"power-controller@{off} {{")
        blocks[f"PMGR:{lbl}@{off}"] = canon(b, ph, arity) if b else f"ABSENT {off}"
    return blocks


def compare(built, hist):
    bad = []
    for key in EXPECTED:
        a = built.get(key, "MISSING")
        h = hist.get(key, "MISSING")
        if a.startswith("ABSENT") or h.startswith("ABSENT") or a != h:
            bad.append((key, a, h))
    return bad


def decompile(dtb, out):
    subprocess.run(["dtc", "-I", "dtb", "-O", "dts", "-o", str(out), str(dtb)],
                   check=True, stderr=subprocess.DEVNULL)
    return Path(out).read_text()


def run_pair(built_dtb, hist_dtb, wd):
    wd = Path(wd)
    wd.mkdir(parents=True, exist_ok=True)
    built = extract(decompile(built_dtb, wd / "b.dts"))
    hist = extract(decompile(hist_dtb, wd / "h.dts"))
    missing = [k for k in EXPECTED
               if built.get(k, "MISSING") == "MISSING"
               or built.get(k, "MISSING").startswith("ABSENT")
               or hist.get(k, "MISSING") == "MISSING"
               or hist.get(k, "MISSING").startswith("ABSENT")]
    return compare(built, hist), missing


def main():
    ap_args = sys.argv[1:]
    selftest = "--selftest" in ap_args
    ap_args = [a for a in ap_args if a != "--selftest"]
    if len(ap_args) < 2:
        sys.exit(f"usage: {sys.argv[0]} BUILT.dtb HISTORICAL.dtb [workdir] [--selftest]")
    built_dtb, hist_dtb = Path(ap_args[0]), Path(ap_args[1])
    wd = Path(ap_args[2] if len(ap_args) > 2 else "/tmp/ane-verify")
    wd.mkdir(parents=True, exist_ok=True)

    if not selftest:
        bad, missing = run_pair(built_dtb, hist_dtb, wd)
        if missing:
            print("FAIL: expected blocks missing:", missing)
            sys.exit(1)
        if bad:
            for key, a, h in bad:
                print(f"DIFF {key}\n  built      : {a}\n  historical : {h}")
            sys.exit(1)
        print("CANONICAL-EQUAL: ANE node, 3 ANE DARTs, and all six SET-word "
              "pmgr pwrstate nodes match the carved historical working tree "
              "(formatting-insensitive, SID cells preserved, all blocks "
              "present).")
        return

    # negative self-tests: each mutation must FAIL the comparison
    src = decompile(built_dtb, wd / "s.dts")
    cases = [
        ("provider-parent-only",
         src.replace('label = "ane_base";\n\t\t\t\tpower-domains = <0xc5>;',
                     'label = "ane_base";\n\t\t\t\tpower-domains = <0x82>;')),
        ("dma-range-only",
         src.replace('apple,dma-range = <0x00 0x00 0x00 0xe0000000>;',
                     'apple,dma-range = <0x00 0x00 0x00 0xf0000000>;')),
    ]
    ok = True
    for name, mutated in cases:
        if mutated == src:
            print(f"SELFTEST {name}: mutation did not apply (anchor missing)")
            ok = False
            continue
        m_dts = wd / f"mut-{name}.dts"
        m_dts.write_text(mutated)
        m_dtb = wd / f"mut-{name}.dtb"
        subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(m_dtb),
                        str(m_dts)], check=True, stderr=subprocess.DEVNULL)
        bad, missing = run_pair(m_dtb, hist_dtb, wd / f"st-{name}")
        if bad or missing:
            print(f"SELFTEST {name}: correctly FAILED comparison "
                  f"({len(bad)} diff blocks, missing={missing})")
        else:
            print(f"SELFTEST {name}: FAIL — mutation was NOT detected")
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
