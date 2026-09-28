// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* T6021 (H14 / J414c) ANE platform driver skeleton.
 *
 * Architecture (W1/W2/W4-fix receipts; this is NOT the H13 ane driver
 * model): the fw owns the task manager and the 8 task queues
 * (CSneTMDrvH14 — the kext never programs the H13-style host TM/TQ
 * window and first touch on it external-aborted, proven twice
 * 2026-09-18), so the host brings up the MBI transport (SCRATCH wake
 * -> fw channel table -> per-channel doorbell bits at +0x1844000; the
 * m1n1 ASC mailbox analogy at +0x1608xxx is falsified and SError-fatal)
 * and talks CSNE_CMD over RTBuddy app endpoints. Submission is gated on
 * the channel-table dump pinning the INIT doorbell bit; this skeleton
 * probes, maps, attaches power and captures the handshake.
 *
 * Probe makes no engine-window write and no SET write. First-touch
 * reads at resume are the phase-1-proven ASC status region plus the
 * kext-evidenced MBI registers (SCRATCH/message pair — the kext reads
 * and writes these at runtime on this silicon; the +0x1608xxx family
 * the kext never touches is what aborted the machine). The first
 * on-device run must ride netconsole with the named-stage dev_info
 * lines as the flush points.
 */

#include <linux/io.h>
#include <linux/interrupt.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>

#include "ane_t6021.h"

/*
 * Repo tier discipline (ane/src/ane_drv.c): the constants for this SoC
 * are complete and static-decode proven, but nothing has ever run on
 * t6021 silicon under Linux, so the skeleton binds only behind
 * allow_unqualified=1 — loudly, and never half-probing: the gate fires
 * before any power domain, MMIO or IRQ interaction.
 */
static bool allow_unqualified;
module_param(allow_unqualified, bool, 0444);
MODULE_PARM_DESC(allow_unqualified,
		 "Bind the unqualified T6021 skeleton (W3: no execution proven on silicon)");

/* The MBI transport stays OFF by default: the m1n1 ASC-mailbox analogy
 * (+0x1608xxx) is falsified and SError-fatal on t6021 (read abort on
 * CPU1 2026-09-19; phase1 hang 09-18) and the kext text has no such
 * registers.  The kext-evidenced transport is MBI: SCRATCH0/1 command
 * buffer, SCRATCH7 wake 0xf7fbdff9 -> fw channel table (ack
 * 0x08042006), per-channel doorbell bits at +0x1844000.  Opt-in runs
 * the handshake capture-only (no doorbell ring until the table pins
 * the channel bits).  Status-only bring-up performs the phase-1
 * read-only whitelist and reports the honest state split
 * (power_gated/cpu_started/fw_alive/booted); it does NOT establish a
 * running coprocessor. */
static bool rtkit_transport;
module_param(rtkit_transport, bool, 0444);
MODULE_PARM_DESC(rtkit_transport,
		 "OPT-IN: MBI SCRATCH handshake + fw channel-table capture (kext-evidenced registers; no doorbell writes)");

/* RTBuddy-mode TX arm (provider decode 2026-09-19): the gate send is
 * the 48-bit MBI word to +0x1850000 followed by write32(1 << ep) to
 * the +0x1844000 doorbell (bit = endpoint id: EP0 management, EP1
 * INIT/CSNE, EP2..6 fw->host).  Default off — the first live ring is
 * the next lane's W5 work; arming this only lifts the driver-side
 * fence, it does not make the sequence safe (EP0/EP1 validity on
 * selene is kext-evidenced but not yet device-proven). */
static bool mbi_doorbell;
module_param(mbi_doorbell, bool, 0444);
MODULE_PARM_DESC(mbi_doorbell,
		 "OPT-IN: run the EP0 MGMT session (HELLO/EPMAP/STARTEP, W6) then allow EP1 rings. LIVE 2026-09-19: W5-live EP1 ring (0xbe000000) AND W6 EP0 HELLO with 32-bit a2i halves (0xbe000000, same class 25 us) — every host write into the ANE control aperture aborts; wall is upstream of protocol (fabric/fw write-grant). Silent session fences the PING (soft wall)");

/* pmgr island words this device consumes, inside the "pmgr" window:
 * ane_cpu@2e0, ane_sys_mpm@4000, ane_td@4008, ane_base@4010,
 * ane_set1..4@4018-4030 (overlay phandle chain). */
static const unsigned int ane_t6021_pmgr_words[] = {
	0x2e0, 0x4000, 0x4008, 0x4010, 0x4018, 0x4020, 0x4028, 0x4030
};

static const char *const ane_t6021_reg_names[ANE_T6021_REG_COUNT] = {
	"engine", "pmgr", "set"
};

/* ps-word policy (fields in ane_t6021.h; h14_bringup.py PS_*).
 * W3 death discriminator (receipt
 * 2026-09-19-h14-init-sequence-kext-trace): engine-window access while
 * any island word is below ACTUAL=0xf, or with ane_cpu AUTO_ENABLE
 * set, hard-resets t6021. The driver NEVER writes a ps word: the raise
 * belongs to the genpd chain, the AUTO_ENABLE clear on the
 * already-on ane_cpu to the device-proven userspace RMW
 * (h14_bringup.py --stage 1) — the identical kernel-context write
 * froze the machine at pmgr+0x2e0 on 2026-09-19 09:39 (watchdog +62 s)
 * where the userspace RMW of the same word, same value, was clean. */

static void ane_t6021_detach_genpd(struct ane_t6021 *ane)
{
	for (int i = ane->pd_count - 1; i >= 0; i--) {
		if (ane->pd_link[i])
			device_link_del(ane->pd_link[i]);
		if (!IS_ERR_OR_NULL(ane->pd_dev[i]))
			dev_pm_domain_detach(ane->pd_dev[i], true);
	}
	ane->pd_count = 0;
}

static int ane_t6021_attach_genpd(struct ane_t6021 *ane)
{
	struct device *dev = ane->dev;
	int count;

	count = of_count_phandle_with_args(dev->of_node, "power-domains",
					   "#power-domain-cells");
	if (count < 1)
		return count < 0 ? count : -EINVAL;
	if (count == 1)
		return dev->pm_domain ? 0 : -EPROBE_DEFER;

	ane->pd_dev = devm_kcalloc(dev, count, sizeof(*ane->pd_dev),
				   GFP_KERNEL);
	ane->pd_link = devm_kcalloc(dev, count, sizeof(*ane->pd_link),
				    GFP_KERNEL);
	if (!ane->pd_dev || !ane->pd_link)
		return -ENOMEM;

	for (ane->pd_count = 0; ane->pd_count < count; ane->pd_count++) {
		ane->pd_dev[ane->pd_count] =
			dev_pm_domain_attach_by_id(dev, ane->pd_count);
		if (IS_ERR(ane->pd_dev[ane->pd_count])) {
			int err = PTR_ERR(ane->pd_dev[ane->pd_count]);

			ane_t6021_detach_genpd(ane);
			return err;
		}

		ane->pd_link[ane->pd_count] =
			device_link_add(dev, ane->pd_dev[ane->pd_count],
					DL_FLAG_STATELESS |
					DL_FLAG_PM_RUNTIME |
					DL_FLAG_RPM_ACTIVE);
		if (!ane->pd_link[ane->pd_count]) {
			dev_pm_domain_detach(ane->pd_dev[ane->pd_count],
					     true);
			ane_t6021_detach_genpd(ane);
			return -EINVAL;
		}
	}

	return 0;
}

/* First-resume bring-up in phase1 order; every stage logs before it
 * runs so netconsole pins any stall, and the whole engine-window walk
 * sits behind the eight-word power gate. */
static int ane_t6021_first_resume(struct ane_t6021 *ane)
{
	void __iomem *eng = ane->base[ANE_T6021_REG_ENGINE];
	void __iomem *pmgr = ane->base[ANE_T6021_REG_PMGR];
	unsigned int i;
	u32 cpu;

	/* Stage 1: pmgr reads only (proven-safe read class on every
	 * raise state).  The genpd chain raised the islands parent-first
	 * (list order, ane_cpu last); the userspace bring-up RMW
	 * (h14_bringup.py --stage 1, run before insmod) cleared
	 * AUTO_ENABLE on the already-on ane_cpu. */
	dev_info(ane->dev,
		 "ANE-resume: genpd raise complete; pmgr island words next\n");
	for (i = 0; i < ARRAY_SIZE(ane_t6021_pmgr_words); i++)
		dev_info(ane->dev, "ANERD pmgr+%#05x act=%08x\n",
			 ane_t6021_pmgr_words[i],
			 readl(pmgr + ane_t6021_pmgr_words[i]));

	/* Stage 2: the ane_cpu shape — the W3 death discriminator.  The
	 * kernel's apple-pmgr-pwrstate re-sets AUTO_ENABLE on every
	 * domain it finds on at boot, and the hardware only consumes the
	 * bit on a transition, so the untouched ane_cpu keeps it.  A
	 * kernel-context flag-clear write to this word froze the box
	 * (2026-09-19); refuse instead of writing. */
	cpu = readl(pmgr + 0x2e0);
	if (FIELD_GET(ANE_PS_ACTUAL, cpu) != ANE_PS_ON ||
	    (cpu & (ANE_PS_BUSY | ANE_PS_AUTO_ENABLE))) {
		dev_err(ane->dev,
			"ANEGATE ane_cpu=%08x (want act=0xf busy=0 auto=0) — refusing block access; run h14_bringup.py --stage 1 (userspace RMW) before insmod\n",
			cpu);
		return -EIO;
	}
	dev_info(ane->dev, "ANERD ane_cpu=%08x auto_enable clear\n", cpu);

	/* Stage 3: the gate — all eight islands ACTUAL=0xf, BUSY clear,
	 * before anything inside the engine aperture or the SET window
	 * is touched. */
	for (i = 0; i < ARRAY_SIZE(ane_t6021_pmgr_words); i++) {
		u32 v = readl(pmgr + ane_t6021_pmgr_words[i]);

		if (FIELD_GET(ANE_PS_ACTUAL, v) != ANE_PS_ON ||
		    (v & ANE_PS_BUSY)) {
			dev_err(ane->dev,
				"ANEGATE pmgr+%#05x act=%08x not on — refusing block access\n",
				ane_t6021_pmgr_words[i], v);
			return -EIO;
		}
	}

	/* Stage 4: SET word 0 (read-only by repo rule; proven-safe read
	 * in W2 and W3), then the phase1-proven ASC status whitelist
	 * ONLY (S2 read clean under the full eight-word raise).
	 * CPU_CONTROL/+0x160xxx stay out of this walk: the h14g cpu
	 * block is +0x1400000 (kext config), and the MBI transport
	 * exercises its own registers. */
	dev_info(ane->dev, "ANEGATE pass; ASC status whitelist next\n");
	dev_info(ane->dev, "ANERD set+0 act=%08x\n",
		 readl(ane->base[ANE_T6021_REG_SET]));
	dev_info(ane->dev, "ANERD rvbar=%08x\n", readl(eng + ANE_ASC_RVBAR));
	dev_info(ane->dev, "ANERD edprcr=%08x\n", readl(eng + ANE_ASC_EDPRCR));
	dev_info(ane->dev, "ANERD vers=%08x\n", readl(eng + ANE_ASC_VERS));
	dev_info(ane->dev, "ANERD rtb_status=%08x rtb_7c=%08x\n",
		 readl(eng + ANE_ASC_RTB_STATUS),
		 readl(eng + ANE_ASC_RTB_STATUS_UNK7C));
	/* +0x1840048..+0x1840064 = MBI SCRATCH0-7 (h14g config blob
	 * @0x…7503a40; phase-1 S2 read all-zero pre-attach) */
	for (i = 0; i < 8; i++)
		dev_info(ane->dev, "ANERD scratch%u=%08x\n", i,
			 readl(eng + ANE_MBI_SCRATCH0 + 4 * i));

	ane->power_gated = true;
	return 0;
}

/* One teardown for every path (W15 review: the old shutdown label
 * freed rings under a still-registered threaded IRQ and never freed
 * the fw surface; remove() duplicated a different order). Order:
 * IRQ first — its thread reads MMIO and drains the rings and must not
 * outlive them or the power domains — then rings + mutex, then the fw
 * surface, then power. Safe on partially-probed state: every step
 * checks what actually exists. */
static void ane_t6021_cleanup(struct ane_t6021 *ane)
{
	/* H13 wedged-pin pattern (ane/src/ane_drv.c
	 * ane_gem_free_object: "leak the mapping ... Reboot reclaims
	 * them"): once the ASC CPU started there is NO verified
	 * quiescence path — hold the WHOLE lifetime. The fw surface,
	 * endpoint rings, IRQ and the power-domain links stay exactly
	 * as they are; nothing under a possibly-fetching CPU is torn
	 * down. Reboot is the cleanup. */
	if (ane->cpu_started || ane->hybrid_pinned) {
		dev_err(ane->dev,
			"wedged-pin: remove held — fw surface, rings, IRQ and power-domain links preserved until reboot (no verified quiescence; never tear down under a started CPU)\n");
		return;
	}
	if (ane->irq_requested) {
		devm_free_irq(ane->dev, ane->irq, ane);
		ane->irq_requested = false;
	}
	ane_t6021_rtkit_shutdown(ane);
	ane_t6021_fwload_remove(ane);
	ane_t6021_detach_genpd(ane);
}

static int ane_t6021_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct resource *res;
	struct ane_t6021 *ane;
	int err;

	if (!allow_unqualified) {
		dev_err(dev,
			"apple,t6021-ane: skeleton binds only behind ane_t6021.allow_unqualified=1 (W3: no execution proven on this silicon; W4 submission pending)\n");
		return -ENODEV;
	}
	dev_warn(dev,
		 "UNQUALIFIED T6021 bind forced by allow_unqualified: RTKit bring-up path only, CSNE_CMD submission is W4\n");

	if (!ane_t6021_fwload_options_ok(rtkit_transport || mbi_doorbell)) {
		dev_err(dev, "invalid laboratory firmware marker options; refusing before power access\n");
		return -EINVAL;
	}

	ane = devm_kzalloc(dev, sizeof(*ane), GFP_KERNEL);
	if (!ane)
		return -ENOMEM;
	ane->dev = dev;
	platform_set_drvdata(pdev, ane);

	/* Managed power first: the eight-island pmgr chain raises
	 * parent-first (sys_mpm→td→base→set1..4, ane_cpu last — the
	 * overlay list order) through the supplier links before any
	 * register is touched. */
	err = ane_t6021_attach_genpd(ane);
	if (err < 0) {
		dev_err(dev, "failed to attach power domains: %d\n", err);
		return err;
	}

	/* One coherent DMA mask for every allocation (W15 review): the
	 * rings used to allocate in rtkit_init BEFORE fwload set the
	 * 64-bit mask, so early coherent allocations could land under a
	 * default narrower mask. */
	err = dma_set_mask_and_coherent(dev, DMA_BIT_MASK(64));
	if (err) {
		dev_err(dev, "dma mask: %d\n", err);
		goto out;
	}

	ane->irq = platform_get_irq_byname(pdev, "ane");
	if (ane->irq < 0) {
		err = ane->irq;
		goto out;
	}

	/* All three windows map by address outside the resource API:
	 * the ADT puts the dart-ane0 windows inside the 32 MiB engine
	 * aperture (block-relative W3 architecture) and the pmgr island
	 * inside the PMGR syscon block, so region requests collide
	 * with the bound darts / pmgr driver (-EBUSY, live probe
	 * 2026-09-19). SET additionally stays read-only by repo rule
	 * (direct SET writes external-abort; H13 precedent); no
	 * engine-window write exists in this driver either. */
	for (unsigned int i = 0; i < ANE_T6021_REG_COUNT; i++) {
		res = platform_get_resource_byname(pdev, IORESOURCE_MEM,
						   ane_t6021_reg_names[i]);
		if (!res) {
			err = -EINVAL;
			goto out;
		}
		ane->base[i] = devm_ioremap(dev, res->start,
					    resource_size(res));
		if (!ane->base[i]) {
			err = -ENOMEM;
			goto out;
		}
	}

	ane->transport = rtkit_transport;
	ane->doorbell = mbi_doorbell;
	if (ane->doorbell && !ane->transport)
		dev_warn(dev,
			 "mbi_doorbell=1 without rtkit_transport=1: TX armed but the drain/capture path is off\n");

	err = ane_t6021_rtkit_init(ane);
	if (err < 0)
		goto out;

	/* W13a: the gate + whitelist run EXPLICITLY here, with device
	 * runtime PM never enabled — rpm_callback can therefore never
	 * cache an error that hides this walk (the -22 trap), and the
	 * whitelist always executes before any engine-window use.  The
	 * pmgr islands are held on by the DL_FLAG_RPM_ACTIVE supplier
	 * links from attach_genpd(), independent of consumer runtime
	 * state. */
	err = ane_t6021_first_resume(ane);
	if (err)
		goto out;	/* cleanup frees rings + surface + genpd */

	/* After power: AIC2 ANE interrupt (raw 884; dart-ane0's 885
	 * belongs to the dart driver and is never requested here).  Only
	 * with the transport opted in — its thread drains the MBI
	 * message registers. */
	if (ane->transport) {
		err = devm_request_threaded_irq(dev, ane->irq, NULL,
						ane_t6021_rtkit_irq_thread,
						IRQF_ONESHOT, "ane_t6021",
						ane);
		if (err < 0) {
			dev_err(dev, "failed to request ane irq: %d\n", err);
			goto out;
		}
		ane->irq_requested = true;
	}

	/* W15 order repair (Main review): staging and boot precede any
	 * transport use. The old probe order ran the EP0/EP1 session
	 * BEFORE fwload — the W10-proven pointless class (no fw running
	 * behind the send surfaces) that SError'd W5/W6 live. */
	err = ane_t6021_fwload_probe(ane);
	if (err) {
		if (ane_t6021_boot_requested() || ane_t6021_fw_diag_requested()) {
			/* Boot and diagnostic requests require successful staging:
			 * fail with the ACTUAL staging error, not a
			 * deferred generic one from boot_probe. */
			dev_err(dev,
				"fwload failed (%d) — boot/diagnostic requested, failing probe\n",
				err);
			goto out;
		}
		dev_err(dev,
			"fwload failed (%d) — status-only continue, boot stays fenced\n",
			err);
	}

	/* W15 boot state resolution (ane_t6021_boot.c; fw_boot=1). With
	 * fw_boot=1 the preboot engine table fires (pass5: REQUIRED
	 * every power-up), then the probe FAILS at the named-prerequisite
	 * block (-ENODATA) — RVBAR, CPU_CONTROL and publication stay
	 * blocked. With fw_boot=0 everything boot-side is fenced and
	 * this returns 0 (status-only bind). */
	err = ane_t6021_boot_probe(ane);
	if (err)
		goto out;

	dev_info(dev,
		 "loaded ane_t6021 %s (power_gated=%u cpu_started=%u fw_alive=%u booted=%u; transport %s, CSNE TX %s)\n",
		 ANE_T6021_MODULE_VERSION,
		 ane->power_gated, ane->cpu_started, ane->fw_alive,
		 ane->booted,
		 ane->transport ? "ON" : "off",
		 ane->doorbell ? "ARMED (mbi_doorbell=1)" :
				 "fenced (mbi_doorbell=0)");

	/* W15: the PING additionally fences on ane->booted inside
	 * csne_ping_attempt. The W5/W6 sends failed while no valid fw
	 * was staged or running; this driver treats a live fw as a
	 * prerequisite for sending — a conservative gate, not a claimed
	 * exclusive cause of those aborts. */
	ane_t6021_csne_ping_attempt(ane);
	return 0;

out:
	ane_t6021_cleanup(ane);
	return err;
}

static void ane_t6021_remove(struct platform_device *pdev)
{
	struct ane_t6021 *ane = platform_get_drvdata(pdev);

	/* Same single teardown as every probe failure path (W15):
	 * IRQ first, then rings, then the fw surface, then power. */
	ane_t6021_cleanup(ane);
}

static const struct of_device_id ane_t6021_of_match[] = {
	{ .compatible = "apple,t6021-ane" },
	{ }
};
MODULE_DEVICE_TABLE(of, ane_t6021_of_match);

static struct platform_driver ane_t6021_driver = {
	.probe = ane_t6021_probe,
	.remove = ane_t6021_remove,
	.driver = {
		.name = "ane_t6021",
		.suppress_bind_attrs = true,
		.of_match_table = ane_t6021_of_match,
	},
};
module_platform_driver(ane_t6021_driver);

MODULE_AUTHOR("Joshua Warren");
MODULE_DESCRIPTION("Apple Neural Engine driver, T6021/H14 (RTKit skeleton)");
MODULE_VERSION(ANE_T6021_MODULE_VERSION);
MODULE_LICENSE("Dual MIT/GPL");
