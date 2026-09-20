#!/usr/bin/env python3
"""Patch decompiled t8103-j293.dts with the T8103 ANE node set.

Every value traces to the j293 Apple ADT (offline IPSW extraction) or the
in-tree dtb itself. No guessing; see receipts/2026-09-20-jwm1-ane-dt-derivation.
"""
import re, sys

SRC = "/tmp/dtbo-parse/j293.dts"
DST = "/tmp/dtbo-parse/j293.ane.dts"

dts = open(SRC).read()

# 1) ane_sys_cpu gets a phandle so the ane node can reference it.
anchor = '''label = "ane_sys_cpu";
				power-domains = <0x82>;
			};'''
assert dts.count(anchor) == 1
dts = dts.replace(anchor, '''label = "ane_sys_cpu";
				power-domains = <0x82>;
				phandle = <0xc5>;
			};''')

# 2) New nodes under /soc: three ANE DARTs + the ANE engine.
anchor2 = "\t\tiommu@228304000 {"
assert dts.count(anchor2) == 1
new_nodes = '''\t\tiommu@26b800000 {
\t\t\tcompatible = "apple,t8103-dart";
\t\t\treg = <0x02 0x6b800000 0x00 0x4000>;
\t\t\tinterrupt-parent = <0x0f>;
\t\t\tinterrupts = <0x00 0x1a1 0x04>;
\t\t\t#iommu-cells = <0x01>;
\t\t\tpower-domains = <0x82>;
\t\t\tstatus = "okay";
\t\t\tphandle = <0xc6>;
\t\t};

\t\tiommu@26b810000 {
\t\t\tcompatible = "apple,t8103-dart";
\t\t\treg = <0x02 0x6b810000 0x00 0x4000>;
\t\t\tinterrupt-parent = <0x0f>;
\t\t\tinterrupts = <0x00 0x1a1 0x04>;
\t\t\t#iommu-cells = <0x01>;
\t\t\tpower-domains = <0x82>;
\t\t\tstatus = "okay";
\t\t\tphandle = <0xc7>;
\t\t};

\t\tiommu@26b820000 {
\t\t\tcompatible = "apple,t8103-dart";
\t\t\treg = <0x02 0x6b820000 0x00 0x4000>;
\t\t\tinterrupt-parent = <0x0f>;
\t\t\tinterrupts = <0x00 0x1a1 0x04>;
\t\t\t#iommu-cells = <0x01>;
\t\t\tpower-domains = <0x82>;
\t\t\tstatus = "okay";
\t\t\tphandle = <0xc8>;
\t\t};

\t\tane@26a000000 {
\t\t\tcompatible = "apple,t8103-ane";
\t\t\treg-names = "engine";
\t\t\treg = <0x02 0x6bc04000 0x00 0x24000>;
\t\t\tinterrupt-parent = <0x0f>;
\t\t\tinterrupt-names = "ane";
\t\t\tinterrupts = <0x00 0x1a0 0x04>;
\t\t\tiommus = <0xc6 0x00>, <0xc7 0x00>, <0xc8 0x00>;
\t\t\tpower-domains = <0x82>, <0xc5>;
\t\t\tstatus = "okay";
\t\t};

'''
dts = dts.replace(anchor2, new_nodes + anchor2)

open(DST, "w").write(dts)
print("patched ->", DST)
