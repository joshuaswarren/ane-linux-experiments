// SPDX-License-Identifier: GPL-2.0-only OR MIT
/*
 * Experiment module: report the ANE_SYS power state to the PMP through
 * the T600x PMP v2 report SRAM, the same interface and offsets the
 * in-tree apple-pmp-report driver already drives on this boot for its
 * enabled entries (pmdomain/apple/pmp-report.c, apple_pmp_offsets_t600x).
 * The DT carries the ANE entry (report@a, "pmp-ane-sys") with status
 * disabled, so nothing on Linux tells the PMP that the ANE is powered.
 *
 * report=0: read-only dump of tgt_read/actual/status.
 * report=1: set the ANE bit (only if clear), poll the PMP ack; the bit
 *           is cleared again on unload.
 */
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/pm_runtime.h>

#define TGT_READ	0xf80
#define TGT_WRITE	0x107c0
#define ACTUAL		0x1000
#define STATUS		0x10
#define READY		0x1

static bool report;
module_param(report, bool, 0444);

static void __iomem *base;
static u64 bit;
static bool owned;

static void dump(const char *when)
{
	pr_info("pmp_ane: %s tgt_read=%#llx actual=%#llx status=%#llx\n", when,
		readq(base + TGT_READ), readq(base + ACTUAL),
		readq(base + STATUS));
}

static int set_bit_state(bool on)
{
	u64 val = readq(base + TGT_READ);
	ktime_t t0;
	int err;

	val = on ? (val | bit) : (val & ~bit);
	writeq(val, base + TGT_WRITE);
	if (!(readq(base + STATUS) & READY)) {
		pr_info("pmp_ane: pmp not ready, no ack expected\n");
		return 0;
	}
	t0 = ktime_get();
	err = readq_poll_timeout(base + ACTUAL, val, !!(val & bit) == on, 100,
				 50000);
	pr_info("pmp_ane: %s -> %d after %lld us\n", on ? "on" : "off", err,
		ktime_us_delta(ktime_get(), t0));
	return err;
}

static struct platform_device *bound(struct device_node *np, const char *drv)
{
	struct platform_device *pdev = of_find_device_by_node(np);

	if (pdev && pdev->dev.driver && !strcmp(pdev->dev.driver->name, drv))
		return pdev;
	if (pdev)
		put_device(&pdev->dev);
	return NULL;
}

static int __init pmp_ane_init(void)
{
	struct device_node *ent = NULL, *parent, *ane;
	struct platform_device *rep, *anedev;
	struct resource *res;
	const char *label;
	u32 id;
	int err = -ENODEV;

	while ((ent = of_find_compatible_node(ent, NULL,
					      "apple,t6000-pmp-v2-report-entry")))
		if (!of_property_read_string(ent, "label", &label) &&
		    !strcmp(label, "pmp-ane-sys"))
			break;
	if (!ent || of_property_read_u32(ent, "reg", &id) || id > 63)
		goto out;
	bit = BIT_ULL(id);

	parent = of_get_parent(ent);
	if (!of_device_is_compatible(parent, "apple,t6000-pmp-v2-report")) {
		of_node_put(parent);
		goto out;
	}
	/* Only touch the SRAM the in-tree driver has already bound and
	 * mapped on this boot. */
	rep = bound(parent, "apple-pmp-report");
	of_node_put(parent);
	if (!rep) {
		pr_err("pmp_ane: apple-pmp-report not bound, refusing\n");
		goto out;
	}

	ane = of_find_compatible_node(NULL, NULL, "apple,t6000-ane");
	anedev = ane ? bound(ane, "ane") : NULL;
	of_node_put(ane);
	if (anedev) {
		if (pm_runtime_active(&anedev->dev))
			err = 0;
		put_device(&anedev->dev);
	}
	if (err) {
		pr_err("pmp_ane: ane not bound and active, refusing\n");
		goto put;
	}
	err = -ENODEV;

	/* Same mapping attributes the in-tree driver's
	 * devm_platform_ioremap_resource() picks for this resource. */
	res = platform_get_resource(rep, IORESOURCE_MEM, 0);
	if (!res || resource_size(res) < TGT_WRITE + 8)
		goto put;
	base = (res->flags & IORESOURCE_MEM_NONPOSTED) ?
		       ioremap_np(res->start, resource_size(res)) :
		       ioremap(res->start, resource_size(res));
	if (!base) {
		err = -ENOMEM;
		goto put;
	}
	pr_info("pmp_ane: %pR nonposted=%d entry %u\n", res,
		!!(res->flags & IORESOURCE_MEM_NONPOSTED), id);

	dump("before");
	if (report) {
		if (readq(base + TGT_READ) & bit) {
			pr_info("pmp_ane: bit already set, leaving it\n");
		} else {
			/* Written means owned: unload clears it even if the
			 * PMP never acked. */
			set_bit_state(true);
			owned = true;
		}
		dump("after");
	}
	err = 0;
put:
	put_device(&rep->dev);
out:
	of_node_put(ent);
	return err;
}

static void __exit pmp_ane_exit(void)
{
	if (owned)
		set_bit_state(false);
	dump("exit");
	iounmap(base);
}

module_init(pmp_ane_init);
module_exit(pmp_ane_exit);
MODULE_DESCRIPTION("PMP ANE_SYS power-report experiment");
MODULE_LICENSE("Dual MIT/GPL");
