/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
#include <linux/mm.h>

static void ane_rtclient_dart_observe(struct device *dev)
{
	static const phys_addr_t bases[] = { 0x285800000ull, 0x285810000ull, 0x285820000ull };
	const u64 iova = 0x10000064000ull;
	unsigned int di, sid;

	for (di = 0; di < ARRAY_SIZE(bases); di++) {
		void __iomem *regs = ioremap_np(bases[di], 0x2000);

		if (!regs) {
			dev_emerg(dev, "DART-WALK instance=%u map failed\n", di);
			continue;
		}
		for (sid = 0; sid < 16; sid++) {
			u32 tcr = readl(regs + 0x1000 + 4 * sid);
			u32 ttbr = readl(regs + 0x1400 + 4 * sid);
			phys_addr_t table = ((u64)ttbr >> 2) << 14;
			int shift;

			dev_emerg(dev, "DART-WALK instance=%u sid=%u TCR=%08x TTBR=%08x ENABLE=%08x\n",
				  di, sid, tcr, ttbr, readl(regs + 0xc00));
			if (!(ttbr & 1) || !(tcr & 1) || (tcr & 2))
				continue;
			if (!(tcr & 8)) {
				dev_emerg(dev, "DART-WALK skip non-four-level table\n");
				continue;
			}
			for (shift = 36; shift >= 14; shift -= 11) {
				u64 index = (iova >> shift) & 0x7ff;
				u64 *entry;
				u64 pte;

				if (!pfn_valid(PHYS_PFN(table))) {
					dev_emerg(dev, "DART-WALK refuse non-RAM table=%pa\n", &table);
					break;
				}
				entry = phys_to_virt(table + index * sizeof(u64));
				if (!virt_addr_valid(entry)) {
					dev_emerg(dev, "DART-WALK refuse non-linear table=%pa\n", &table);
					break;
				}
				dma_rmb();
				pte = READ_ONCE(*entry);
				dev_emerg(dev, "DART-WALK instance=%u sid=%u shift=%d table=%pa index=%llu pte=%016llx\n",
					  di, sid, shift, &table, index, pte);
				if (!(pte & 1))
					break;
				table = (pte & GENMASK_ULL(37, 10)) << 4;
				if (shift == 14)
					dev_emerg(dev, "DART-WALK instance=%u sid=%u IOVA=%llx target=%pa\n",
						  di, sid, iova, &table);
			}
		}
		iounmap(regs);
	}
}
