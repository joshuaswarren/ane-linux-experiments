#!/usr/bin/env python3
"""Build the T8103 ANE device tree: stock j293 dtb -> ANE-enabled dtb.

Mirrors the September proven payload node set (carved historical DTB
1a72bc81c03cf0b548e9f959a778accb60d03ba6777131c04c28ef67ec2fd1fc).
Refuses to run unless the stock input hash and phandle-collision
preconditions hold; the stock source tree is never modified.
"""
import argparse, hashlib, re, shutil, subprocess, sys
from pathlib import Path

STOCK_SHA256 = "ea32173df3b0f782bf610f38fb390f90a777c16d4a4b2822c58b924bc6088328"
EXPECTED_OUT_SHA256 = "4ec4b87f36bc9f8f17d3a8213937144277a2197ff6f352ac24482ee20c76f280"
NEW_PHANDLES = ["c5", "c9", "ca", "cb", "cc", "cd", "ce"]

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("stock_dtb", type=Path)
ap.add_argument("out_dtb", type=Path)
ap.add_argument("--workdir", type=Path, required=True)
args = ap.parse_args()

stock = args.stock_dtb.read_bytes()
got = hashlib.sha256(stock).hexdigest()
if got != STOCK_SHA256:
    sys.exit(f"FATAL: stock dtb sha256 {got} != expected {STOCK_SHA256}")

args.workdir.mkdir(parents=True, exist_ok=True)
src_dts = args.workdir / "j293.dts"
subprocess.run(["dtc", "-I", "dtb", "-O", "dts", "-o", str(src_dts),
                str(args.stock_dtb)], check=True)
dts = src_dts.read_text()

used = set(re.findall(r"phandle = <0x([0-9a-f]+)>;", dts))
clash = [p for p in NEW_PHANDLES if p in used]
assert not clash, f"phandle collision: {clash}"
assert dts.count('label = "ane_sys_cpu";') == 1, "ane_sys_cpu not in stock tree"

CPU_ANCHOR = ('label = "ane_sys_cpu";\n'
              '\t\t\t\tpower-domains = <0x82>;\n'
              '\t\t\t};')
assert dts.count(CPU_ANCHOR) == 1, "ane_sys_cpu block anchor"

dts = dts.replace(CPU_ANCHOR,
                  'label = "ane_sys_cpu";\n'
                  '\t\t\t\tpower-domains = <0x82>;\n'
                  '\t\t\t\tphandle = <0xc5>;\n'
                  '\t\t\t};')

def pwrstate(off, label, phandle, parent):
    return (f'\t\t\tpower-controller@{off} {{\n'
            f'\t\t\t\tcompatible = "apple,t8103-pmgr-pwrstate\\0apple,pmgr-pwrstate";\n'
            f'\t\t\t\treg = <0x{off} 0x04>;\n'
            f'\t\t\t\t#power-domain-cells = <0x00>;\n'
            f'\t\t\t\t#reset-cells = <0x00>;\n'
            f'\t\t\t\tlabel = "{label}";\n'
            f'\t\t\t\tpower-domains = <{parent}>;\n'
            f'\t\t\t\tphandle = <0x{phandle}>;\n'
            f'\t\t\t}};')

# insert the pmgr chain after the (now phandle-tagged) ane_sys_cpu node
marker = ('label = "ane_sys_cpu";\n'
          '\t\t\t\tpower-domains = <0x82>;\n'
          '\t\t\t\tphandle = <0xc5>;\n'
          '\t\t\t};')
assert dts.count(marker) == 1
dts = dts.replace(marker, marker + '\n\n' +
                  '\n\n'.join([pwrstate("c008", "ane_base", "c9", "0xc5"),
                               pwrstate("c010", "ane_set1", "ca", "0xc9"),
                               pwrstate("c018", "ane_set2", "cb", "0xc9"),
                               pwrstate("c020", "ane_set3", "cc", "0xc9"),
                               pwrstate("c028", "ane_set4", "cd", "0xc9"),
                               pwrstate("c030", "ane_set5", "ce", "0xc9")]))

def dart(unit, reg_hi_lo, phandle):
    return (f'\t\tiommu@{unit} {{\n'
            f'\t\t\tcompatible = "apple,t8103-dart";\n'
            f'\t\t\treg = <0x02 0x{reg_hi_lo} 0x00 0x4000>;\n'
            f'\t\t\t#iommu-cells = <0x01>;\n'
            f'\t\t\tinterrupt-parent = <0x0f>;\n'
            f'\t\t\tinterrupts = <0x00 0x1a1 0x04>;\n'
            f'\t\t\tpower-domains = <0x82>;\n'
            f'\t\t\tapple,dma-range = <0x00 0x00 0x00 0xe0000000>;\n'
            f'\t\t\tstatus = "okay";\n'
            f'\t\t\tphandle = <0x{phandle}>;\n'
            f'\t\t}};\n\n')

soc_anchor = '\t\tiommu@228304000 {'
assert dts.count(soc_anchor) == 1
dts = dts.replace(soc_anchor,
                  dart("26b800000", "6b800000", "c6") +
                  dart("26b810000", "6b810000", "c7") +
                  dart("26b820000", "6b820000", "c8") +
                  '\t\tane@26bc04000 {\n'
                  '\t\t\tcompatible = "apple,t8103-ane";\n'
                  '\t\t\treg = <0x02 0x6bc04000 0x00 0x24000>;\n'
                  '\t\t\treg-names = "engine";\n'
                  '\t\t\tinterrupt-parent = <0x0f>;\n'
                  '\t\t\tinterrupts = <0x00 0x1a0 0x04>;\n'
                  '\t\t\tinterrupt-names = "ane";\n'
                  '\t\t\tiommus = <0xc6 0x00 0xc7 0x00 0xc8 0x00>;\n'
                  '\t\t\tpower-domains = <0xca 0xcb 0xcc 0xcd 0xce>;\n'
                  '\t\t\tstatus = "okay";\n'
                  '\t\t};\n\n' + soc_anchor)

out_src = args.workdir / "j293.ane.dts"
out_src.write_text(dts)
subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(args.out_dtb),
                str(out_src)], check=True)
out_sha = hashlib.sha256(args.out_dtb.read_bytes()).hexdigest()
print(f"built {args.out_dtb} sha256 {out_sha}")
if out_sha != EXPECTED_OUT_SHA256:
    sys.exit(f"FATAL: output sha {out_sha} != expected {EXPECTED_OUT_SHA256}")
print("output hash matches the staged reviewed build")
