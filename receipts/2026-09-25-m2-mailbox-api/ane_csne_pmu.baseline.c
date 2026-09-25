// SPDX-License-Identifier: GPL-2.0-only OR MIT
/*
 * ane_csne_pmu.c — cold-start command sequence via the ASC mailbox.
 *
 * Packets per KextRe FINDINGS (AppleH11ANEInterface 9.512.0):
 *   slot 0x00: PRINT_ENABLE  (0x04, 12B)
 *   slot 0x10: START         (0x00, 12B)
 *   slot 0x20: SET_SNE_PMU_BASE2 (0x29, 16B, u64 pmu_base 0x28e08c000)
 *   slot 0x30: CONFIG_GET    (0x03, 16B)
 * Wire format: {u32 0, u16 opcode, u16 0, payload}.
 * Each send: cursor|len to A2I_SEND0, (1<<ep_bit) to 0x1844000.
 * Stop at the first reply (recv, scratch7, or slot flags byte).
 */
#include <linux/module.h>
#include <linux/iommu.h>
#include <linux/io.h>
#include <linux/delay.h>
#include <linux/platform_device.h>
#include <linux/slab.h>
#include <linux/gfp.h>

#define CMD_IOVA	0x1fb08000ULL
#define CMD_SIZE	(256 * 1024)
#define ENGINE_PHYS	0x284000000ULL
#define A2I_SEND0	0x1408800
#define I2A_CTRL	0x1408114
#define I2A_RECV0	0x1408830
#define DOORBELL	0x1844000
#define SCRATCH7	0x1840064
#define CPU_STATUS	0x1400048

static int ep_bit = 1;
module_param(ep_bit, int, 0444);

static void *cmd_buf;

static int __init ane_csne_pmu_init(void)
{
	struct device *dev;
	struct iommu_domain *dom;
	void __iomem *eng;
	u64 o, pa;
	u32 scratch, status, i2a;
	u64 recv;
	int ret, i, c;
	static const struct { u16 id; u16 len; u64 extra; int is64; } cmds[4] = {
		{ 0x04, 12, 0, 0 },
		{ 0x00, 12, 0, 0 },
		{ 0x29, 16, 0x28e08c000ULL, 1 },
		{ 0x03, 16, 0, 1 },
	};

	dev = bus_find_device_by_name(&platform_bus_type, NULL,
				      "284000000.ane");
	if (!dev)
		return -ENODEV;
	dom = iommu_get_domain_for_dev(dev);
	if (!dom) {
		put_device(dev);
		return -ENODEV;
	}

	cmd_buf = (void *)__get_free_pages(GFP_KERNEL | __GFP_ZERO,
					   get_order(CMD_SIZE));
	if (!cmd_buf) {
		put_device(dev);
		return -ENOMEM;
	}
	pa = virt_to_phys(cmd_buf);

	for (o = 0; o < CMD_SIZE; o += 0x4000) {
		if (iommu_iova_to_phys(dom, CMD_IOVA + o))
			continue;
		ret = iommu_map(dom, CMD_IOVA + o, pa + o, 0x4000,
				IOMMU_READ | IOMMU_WRITE | IOMMU_CACHE,
				GFP_KERNEL);
		if (ret) {
			pr_err("csne-pmu: map %#llx: %d\n", CMD_IOVA + o, ret);
			put_device(dev);
			return ret;
		}
	}
	pr_emerg("csne-pmu: mapped %#llx -> %016llx\n", CMD_IOVA, pa);

	for (c = 0; c < 4; c++) {
		u8 *p = (u8 *)cmd_buf + c * 0x10;
		*(u32 *)p = 0;
		*((u16 *)p + 2) = cmds[c].id;
		*((u16 *)p + 3) = 0;
		if (cmds[c].is64)
			*((u64 *)p + 1) = cmds[c].extra;
		else
			*((u32 *)p + 2) = 0;
	}
	dma_wmb();
	for (c = 0; c < 4; c++) {
		u8 *p = (u8 *)cmd_buf + c * 0x10;
		pr_emerg("csne-pmu: slot %#x id=%#x len=%d bytes: %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x\n",
			 c * 0x10, cmds[c].id, cmds[c].len,
			 p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7],
			 p[8], p[9], p[10], p[11], p[12], p[13], p[14], p[15]);
	}

	eng = ioremap_np(ENGINE_PHYS, 0x2000000);
	if (!eng) {
		put_device(dev);
		return -ENOMEM;
	}

	for (c = 0; c < 4; c++) {
		u8 *slot = (u8 *)cmd_buf + c * 0x10;
		u64 db = ((u64)(u32)(c * 0x10) & GENMASK_ULL(23, 0)) |
			 ((u64)(u32)cmds[c].len << 24);
		writeq(db, eng + A2I_SEND0);
		wmb();
		writel(1 << ep_bit, eng + DOORBELL);
		wmb();
		pr_emerg("csne-pmu: sent slot %#x id=%#x db=%016llx bit=%#x\n",
			 c * 0x10, cmds[c].id, db, 1 << ep_bit);
		for (i = 0; i < 150; i++) {
			scratch = readl(eng + SCRATCH7);
			status = readl(eng + CPU_STATUS);
			i2a = readl(eng + I2A_CTRL);
			recv = readq(eng + I2A_RECV0);
			if ((i % 50) == 0 || scratch || recv || slot[6])
				pr_emerg("csne-pmu: cmd%d t=%d scratch7=%08x status=%08x i2a=%08x recv=%016llx flags=%02x\n",
					 c, i, scratch, status, i2a, recv,
					 slot[6]);
			if (recv || scratch || slot[6])
				break;
			msleep(100);
		}
		if (recv || scratch || slot[6]) {
			pr_emerg("csne-pmu: REPLY on cmd%d (id=%#x) t=%d recv=%016llx scratch=%08x flags=%02x slot8=%016llx\n",
				 c, cmds[c].id, i, recv, scratch, slot[6],
				 *(u64 *)(slot + 8));
			break;
		}
	}
	pr_emerg("csne-pmu: done last_cmd=%d\n", c);

	iounmap(eng);
	put_device(dev);
	return 0;
}

static void __exit ane_csne_pmu_exit(void) { }
module_init(ane_csne_pmu_init);
module_exit(ane_csne_pmu_exit);
MODULE_LICENSE("GPL");
