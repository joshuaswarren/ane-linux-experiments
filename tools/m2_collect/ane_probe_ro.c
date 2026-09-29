// SPDX-License-Identifier: GPL-2.0
/*
 * ane_probe_ro - one-shot read-only T6021 ANE state probe.
 *
 * Consolidates the proven-safe one-shot probes from /tmp/dart-walk/
 * (dart_tq4.c, dart_bell.c, dart_evt.c, dart_ps.c, dart_one.c,
 * dart_desc.c): ioremap + readl of individually named words, one pr_info
 * line per register, tag "aprobe:".
 *
 * FORBIDDEN (would kick or wedge hardware) -- this module contains none of:
 *   - ANY register write: no store of any kind reaches MMIO (grep proves
 *     it: not one write mnemonic appears in this file). Above all a host
 *     doorbell write: the TQ doorbells 0x285c20818+q*0x2c (q5 =
 *     0x285c208f4) advance hardware state when written. We only read them.
 *   - A whole-TM-page read: never sweep 0x285c20000..+0x1000 word by
 *     word. Only the enumerated words below are touched, straight-line,
 *     no loops.
 *   - /dev/mem, or the ANE engine window 0x284000000 (reads there while
 *     unpowered have wedged the M2). This module never maps it.
 *
 * Addresses are the 13.5-firmware layout (sha256 a9c4b771...):
 *   TQEn word      0x285c20420  (TQEn = bit 13)
 *   gate           0x285c2048c
 *   event FIFO cnt 0x285c20428  (single word only)
 *   qN cfg         0x285c20810 + q*0x2c, q = 0..7
 *   qN doorbell    0x285c20818 + q*0x2c, q = 0..7   (q5 = 0x285c208f4)
 *   host PS        0x28e084000 .. 0x28e084030 (7 words, stride 8)
 *   DART stream 0  TCR 0x285801000, TTBR 0x285801400
 */
#include <linux/io.h>
#include <linux/module.h>

static void rd(const char *name, void __iomem *p)
{
	pr_info("aprobe: %s = %#010x\n", name, readl(p));
}

static int __init aprobe_init(void)
{
	void __iomem *t = ioremap(0x285c20000ull, 0x1000);
	void __iomem *ps = ioremap(0x28e084000ull, 0x40);
	void __iomem *d = ioremap(0x285800000ull, 0x2000);

	if (!t || !ps || !d)
		goto out;

	/* TM control block. */
	rd("tqen_0x285c20420", t + 0x420);
	pr_info("aprobe: tqen_bit13 = %u\n", (readl(t + 0x420) >> 13) & 1);
	rd("gate_0x285c2048c", t + 0x48c);
	rd("evt_fifo_cnt_0x285c20428", t + 0x428);

	/* Per-queue cfg and doorbell words, unrolled, q = 0..7. */
	rd("q0_cfg_0x285c20810", t + 0x810);
	rd("q0_bell_0x285c20818", t + 0x818);
	rd("q1_cfg_0x285c2083c", t + 0x83c);
	rd("q1_bell_0x285c20844", t + 0x844);
	rd("q2_cfg_0x285c20868", t + 0x868);
	rd("q2_bell_0x285c20870", t + 0x870);
	rd("q3_cfg_0x285c20894", t + 0x894);
	rd("q3_bell_0x285c2089c", t + 0x89c);
	rd("q4_cfg_0x285c208c0", t + 0x8c0);
	rd("q4_bell_0x285c208c8", t + 0x8c8);
	rd("q5_cfg_0x285c208ec", t + 0x8ec);
	rd("q5_bell_0x285c208f4", t + 0x8f4);
	rd("q6_cfg_0x285c20918", t + 0x918);
	rd("q6_bell_0x285c20920", t + 0x920);
	rd("q7_cfg_0x285c20944", t + 0x944);
	rd("q7_bell_0x285c2094c", t + 0x94c);

	/* Host power state, 0x28e084000..0x28e084030. */
	rd("ps_0x28e084000", ps + 0x00);
	rd("ps_0x28e084008", ps + 0x08);
	rd("ps_0x28e084010", ps + 0x10);
	rd("ps_0x28e084018", ps + 0x18);
	rd("ps_0x28e084020", ps + 0x20);
	rd("ps_0x28e084028", ps + 0x28);
	rd("ps_0x28e084030", ps + 0x30);

	/* DART stream 0 translation controls. */
	rd("dart_tcr_0x285801000", d + 0x1000);
	rd("dart_ttbr_0x285801400", d + 0x1400);

out:
	if (d)
		iounmap(d);
	if (ps)
		iounmap(ps);
	if (t)
		iounmap(t);
	return t && ps && d ? 0 : -ENOMEM;
}

static void __exit aprobe_exit(void)
{
}

module_init(aprobe_init);
module_exit(aprobe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("T6021 ANE read-only register probe (single words only)");
