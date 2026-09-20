#!/usr/bin/env python3
"""Patch decompiled t8103-j293.dts with the EXACT historical T8103 ANE node set.

Source of truth: the September proven payload DTB carved from
esp-audit-20260919/esp-live-1848.img (boot.bin) — node ane@26bc04000,
power-domains <ane_set1..5>, three apple,t8103-dart iommu nodes with
apple,dma-range. Every value mirrors that tree; nothing is invented.
"""
import sys

SRC = "/tmp/dtbo-parse/j293.dts"
DST = "/tmp/dtbo-parse/j293.ane.dts"

dts = open(SRC).read()

# ane_sys_cpu (in-tree @c000, fresh phandle 0xc5) gains a phandle already
# assigned below; the fresh in-tree ane_sys is phandle 0x82 (verified).

anchor = '''label = "ane_sys_cpu";
				power-domains = <0x82>;
			};'''
assert dts.count(anchor) == 1, "ane_sys_cpu anchor"
dts = dts.replace(anchor, '''label = "ane_sys_cpu";
				power-domains = <0x82>;
				phandle = <0xc5>;
			};''')

# New pmgr pwrstates inside power-management@23b700000 (after ane_sys_cpu),
# mirroring the historical working tree: ane_base @c008 (parent ane_sys_cpu),
# ane_set1..5 @c010..c030 (parent ane_base).
anchor2 = '''label = "ane_sys_cpu";
				power-domains = <0x82>;
				phandle = <0xc5>;
			};'''
assert dts.count(anchor2) == 1
new_pwrstates = anchor2 + '''

			power-controller@c008 {
				compatible = "apple,t8103-pmgr-pwrstate\\0apple,pmgr-pwrstate";
				reg = <0xc008 0x04>;
				#power-domain-cells = <0x00>;
				#reset-cells = <0x00>;
				label = "ane_base";
				power-domains = <0xc5>;
				phandle = <0xc9>;
			};

			power-controller@c010 {
				compatible = "apple,t8103-pmgr-pwrstate\\0apple,pmgr-pwrstate";
				reg = <0xc010 0x04>;
				#power-domain-cells = <0x00>;
				#reset-cells = <0x00>;
				label = "ane_set1";
				power-domains = <0xc9>;
				phandle = <0xca>;
			};

			power-controller@c018 {
				compatible = "apple,t8103-pmgr-pwrstate\\0apple,pmgr-pwrstate";
				reg = <0xc018 0x04>;
				#power-domain-cells = <0x00>;
				#reset-cells = <0x00>;
				label = "ane_set2";
				power-domains = <0xc9>;
				phandle = <0xcb>;
			};

			power-controller@c020 {
				compatible = "apple,t8103-pmgr-pwrstate\\0apple,pmgr-pwrstate";
				reg = <0xc020 0x04>;
				#power-domain-cells = <0x00>;
				#reset-cells = <0x00>;
				label = "ane_set3";
				power-domains = <0xc9>;
				phandle = <0xcc>;
			};

			power-controller@c028 {
				compatible = "apple,t8103-pmgr-pwrstate\\0apple,pmgr-pwrstate";
				reg = <0xc028 0x04>;
				#power-domain-cells = <0x00>;
				#reset-cells = <0x00>;
				label = "ane_set4";
				power-domains = <0xc9>;
				phandle = <0xcd>;
			};

			power-controller@c030 {
				compatible = "apple,t8103-pmgr-pwrstate\\0apple,pmgr-pwrstate";
				reg = <0xc030 0x04>;
				#power-domain-cells = <0x00>;
				#reset-cells = <0x00>;
				label = "ane_set5";
				power-domains = <0xc9>;
				phandle = <0xce>;
			};'''
dts = dts.replace(anchor2, new_pwrstates)

# Three ANE DARTs + the engine node under /soc — mirrors the historical tree
# including apple,dma-range (IOVA cap 0xe0000000, per m1n1 iova_range).
anchor3 = "\t\tiommu@228304000 {"
assert dts.count(anchor3) == 1
new_nodes = '''\t\tiommu@26b800000 {
\t\t\tcompatible = "apple,t8103-dart";
\t\t\treg = <0x02 0x6b800000 0x00 0x4000>;
\t\t\t#iommu-cells = <0x01>;
\t\t\tinterrupt-parent = <0x0f>;
\t\t\tinterrupts = <0x00 0x1a1 0x04>;
\t\t\tpower-domains = <0x82>;
\t\t\tapple,dma-range = <0x00 0x00 0x00 0xe0000000>;
\t\t\tstatus = "okay";
\t\t\tphandle = <0xc6>;
\t\t};

\t\tiommu@26b810000 {
\t\t\tcompatible = "apple,t8103-dart";
\t\t\treg = <0x02 0x6b810000 0x00 0x4000>;
\t\t\t#iommu-cells = <0x01>;
\t\t\tinterrupt-parent = <0x0f>;
\t\t\tinterrupts = <0x00 0x1a1 0x04>;
\t\t\tpower-domains = <0x82>;
\t\t\tapple,dma-range = <0x00 0x00 0x00 0xe0000000>;
\t\t\tstatus = "okay";
\t\t\tphandle = <0xc7>;
\t\t};

\t\tiommu@26b820000 {
\t\t\tcompatible = "apple,t8103-dart";
\t\t\treg = <0x02 0x6b820000 0x00 0x4000>;
\t\t\t#iommu-cells = <0x01>;
\t\t\tinterrupt-parent = <0x0f>;
\t\t\tinterrupts = <0x00 0x1a1 0x04>;
\t\t\tpower-domains = <0x82>;
\t\t\tapple,dma-range = <0x00 0x00 0x00 0xe0000000>;
\t\t\tstatus = "okay";
\t\t\tphandle = <0xc8>;
\t\t};

\t\tane@26bc04000 {
\t\t\tcompatible = "apple,t8103-ane";
\t\t\treg = <0x02 0x6bc04000 0x00 0x24000>;
\t\t\treg-names = "engine";
\t\t\tinterrupt-parent = <0x0f>;
\t\t\tinterrupts = <0x00 0x1a0 0x04>;
\t\t\tinterrupt-names = "ane";
\t\t\tiommus = <0xc6 0x00 0xc7 0x00 0xc8 0x00>;
\t\t\tpower-domains = <0xca 0xcb 0xcc 0xcd 0xce>;
\t\t\tstatus = "okay";
\t\t};

'''
dts = dts.replace(anchor3, new_nodes + anchor3)

open(DST, "w").write(dts)
print("patched ->", DST)
