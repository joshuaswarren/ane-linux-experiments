// SPDX-License-Identifier: GPL-2.0-only OR MIT
/*
 * ane_mbox_api_send.c — mailbox API send with endpoint in msg1.
 *
 * Sends ONE 12-byte PRINT_ENABLE packet (u32 0, u16 0x04, u16 0, u32 0)
 * staged in a coherent ring at IOVA, using the kernel mbox API path
 * only: mbox_send_message-style register contract
 *   msg0 (A2I_SEND0 0x1408800 + 4 high) = cursor|len doorbell word,
 *   msg1 (A2I_SEND1 0x1408808)         = endpoint id,
 * then a 60 s bounded watch of A2I_CTRL level, I2A_CTRL, RECV0,
 * SCRATCH7, CPU_STATUS and IRQ53.
 *
 * Why two devices: the mailbox DT reg is base 0x285408000 size 0x4000
 * (cells 0x2/0x85408000/0x0/0x4000); the ANE aperture is base
 * 0x284000000 size 0x2000000 (cells 0x2/0x84000000/0x0/0x2000000).
 * The ascdbg engine window covers the ANE aperture, so all offsets
 * below are ANE-aperture-relative: SEND0 0x1408800, SEND1 0x1408808,
 * RECV0 0x1408830, A2I_CTRL 0x1408110, I2A_CTRL 0x1408114.
 * The 285408000.mailbox platform device owns the same block through
 * the apple-mailbox driver; this module only reads its IRQ counter
 * via /proc/interrupts and never touches its registers.
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
#define A2I_SEND1	0x1408808
#define A2I_CTRL	0x1408110
#define I2A_CTRL	0x1408114
#define I2A_RECV0	0x1408830
#define SCRATCH7	0x1840064
#define CPU_STATUS	0x1400048

static int ep_id = 1;
module_param(ep_id, int, 0444);
MODULE_PARM_DESC(ep_id, "endpoint id carried in msg1 (A2I_SEND1)");

static void *cmd_buf;

static int __init ane_mbox_api_send_init(void)
{
	struct device *dev;
	struct iommu_domain *dom;
	void __iomem *eng;
	u64 o, pa, db;
	u32 scratch, status, a2i, i2a;
	u64 recv;
	int ret, i;
	u8 *slot;

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
			pr_err("mbox-api: map %#llx: %d\n", CMD_IOVA + o, ret);
			put_device(dev);
			return ret;
		}
	}
	pr_emerg("mbox-api: mapped %#llx -> %016llx\n", CMD_IOVA, pa);

	/* slot 0: PRINT_ENABLE, 12 B: u32 0, u16 0x04, u16 0, u32 0 */
	slot = cmd_buf;
	*(u32 *)slot = 0;
	*((u16 *)slot + 2) = 0x04;
	*((u16 *)slot + 3) = 0;
	*((u32 *)slot + 2) = 0;
	dma_wmb();
	pr_emerg("mbox-api: slot0 bytes: %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x\n",
		 slot[0], slot[1], slot[2], slot[3], slot[4], slot[5],
		 slot[6], slot[7], slot[8], slot[9], slot[10], slot[11]);

	eng = ioremap_np(ENGINE_PHYS, 0x2000000);
	if (!eng) {
		put_device(dev);
		return -ENOMEM;
	}

	/* API contract: msg0 = cursor|len, msg1 = endpoint id. */
	db = ((u64)0 & GENMASK_ULL(23, 0)) | ((u64)12 << 24);
	a2i = readl(eng + A2I_CTRL);
	pr_emerg("mbox-api: pre A2I_CTRL=%08x\n", a2i);
	writeq(db, eng + A2I_SEND0);
	wmb();
	writel((u32)ep_id, eng + A2I_SEND1);
	wmb();
	pr_emerg("mbox-api: sent msg0=%016llx (cursor0 len12) msg1(ep)=%d\n",
		 db, ep_id);
	/* NOTE: no poke to +0x1844000 by design — that raced the bound
	 * 285408000.mailbox driver in the prior series. */

	for (i = 0; i < 600; i++) {
		a2i = readl(eng + A2I_CTRL);
		i2a = readl(eng + I2A_CTRL);
		recv = readq(eng + I2A_RECV0);
		scratch = readl(eng + SCRATCH7);
		status = readl(eng + CPU_STATUS);
		if ((i % 50) == 0 || recv || scratch || slot[6])
			pr_emerg("mbox-api: t=%d A2I_CTRL=%08x I2A_CTRL=%08x recv=%016llx scratch7=%08x status=%08x flags=%02x\n",
				 i, a2i, i2a, recv, scratch, status,
				 slot[6]);
		if (recv || scratch || slot[6])
			break;
		msleep(100);
	}
	pr_emerg("mbox-api: done t=%d A2I_CTRL=%08x recv=%016llx\n",
		 i, a2i, recv);

	iounmap(eng);
	put_device(dev);
	return 0;
}

static void __exit ane_mbox_api_send_exit(void) { }
module_init(ane_mbox_api_send_init);
module_exit(ane_mbox_api_send_exit);
MODULE_LICENSE("GPL");
