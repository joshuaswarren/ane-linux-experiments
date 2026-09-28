// SPDX-License-Identifier: GPL-2.0-only OR MIT
/*
 * ane_t6021_rtclient.c — T6021 (H14 / M2) ANE RTKit CLIENT.
 *
 * This is the t6021 bring-up path that uses mainline RTKit instead of
 * the H13 host-MMIO model: genpd power-up -> devm_apple_rtkit_init on
 * the ANE ASC mailbox (drivers/soc/apple/rtkit.c) -> apple_rtkit_boot
 * (HELLO / EPMAP / STARTEP / IOP power state) -> first CSNE_CMD.
 *
 * Division of labor (receipts/2026-09-22-t6021-rtkit-port):
 *  - CPU start belongs to a quiesce context (m1n1/iBoot). This box's
 *    RVBAR latch is sticky with mode bits 55/48 missing
 *    (2026-09-22-t6021-power-dart-fwload, s23/s24); kernel-context
 *    RVBAR and ps@2e0 writes are fatal. By default this driver
 *    therefore never programs RVBAR or CPU_CONTROL: it refuses to bind
 *    unless the firmware is already alive (CPU_STATUS RUNNING);
 *    fw_start=1 is the fenced exception below.
 *  - genpd/pmgr: Runtime PM + the DT power-domains binding owns the
 *    raise; probe verifies ACTUAL on ane_cpu (pmgr window) before the
 *    first engine read (gate G1). fw_start then puts the islands in the
 *    form macOS runs the ANE in: ane_sys_mpm off, ane_sys/ane_cpu on
 *    with AUTO_ENABLE, td/base/set1-4 on (fw_start_mpm_off).
 *  - Mailbox: apple,asc-mailbox-v4 child node at engine+0x1408000
 *    (a2i/i2a controls 0x285408110/0x285408114 live-read clean, W10).
 *    One AIC line only (ADT ane0 interrupts len 4: raw 0x374) ->
 *    recv-not-empty = that line; TX polls (mailbox.c poll_tx).
 *  - non-posted MMIO everywhere in the ANE aperture (posted writel
 *    froze the box, same receipt): the DT nodes carry
 *    "nonposted-mmio", which of_mmio_is_nonposted turns into
 *    IORESOURCE_MEM_NONPOSTED -> ioremap_np.
 *
 * Post-HELLO protocol (static, selene t602x_ane0_fw_selene_rc4x +
 * kext 26A428; ane-linux-experiments
 * receipts/2026-09-24-m2-post-hello-protocol):
 *  - RTKit protocol v12 only: fw HELLO = min 12 / max 12 (@0x971e0);
 *    mainline rtkit.c accepts 11..12.
 *  - fw RTKit endpoint table (vm 0xed0a0): 0 management, 1 crashlog,
 *    2 syslog, 0x20 "user1". EP1 is the RTKit crashlog endpoint, not
 *    an ANE command channel. The command endpoint is the app endpoint
 *    (>= 0x20) that EPMAP announces; this driver never assumes it.
 *  - fw buffer word (builder 0x982b4, decoder 0x98fc8): addr[43:0] |
 *    size_code[51:44] | unit[53:52], unit 1 = 4 KiB, 2 = 1 MiB,
 *    3 = 2 MiB. App-endpoint word: offset[23:0] | len[47:24] (fw
 *    0x6330/0x64b4, kext rtbuddyEndpointSendMessage).
 *  - The ANE data channels are ChMan rings that the fw lays out in the
 *    host 'IPC ' surface before DONE (fw 0x5348): a table of
 *    0x100-byte descriptors at IPC+0, rings after it.
 *  - CSNE header {u32 rsvd, u16 id, u8 flags, u8 rsvd}; ids from the
 *    selene id->name table (PING 0x11, BUILDINFO 0x06).
 */

#include <linux/completion.h>
#include <linux/crc32.h>
#include <linux/debugfs.h>
#include <linux/dev_printk.h>
#include <linux/delay.h>
#include <linux/dma-mapping.h>
#include <linux/firmware.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/iommu.h>
#include <linux/jiffies.h>
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/ktime.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include <linux/reset.h>
#include <linux/soc/apple/rtkit.h>
#include <linux/workqueue.h>
#include <linux/unaligned.h>

#include "ane_t6021.h"
#include "ane_t6021_diag_marker.h"

/* pmgr ane_cpu ACTUAL word (ane0 reg1 window, pmgr+0x2e0) */
#define ANE_RTCLIENT_PS_CPU_ACTUAL_OFF	0x2e0

/* CPU_STATUS bits (m1n1 ASCRegs shape) */
#define ANE_ASC_CPU_STATUS_RUNNING	BIT(0)
#define ANE_ASC_CPU_STATUS_STOPPED	BIT(1)

/* rtkit.c routes endpoints below this to its own handlers
 * (rtkit-internal.h APPLE_RTKIT_APP_ENDPOINT_START) */
#define ANE_RTKIT_APP_EP_START		0x20

#define ANE_RTCLIENT_RING_SIZE		SZ_64K	/* csne_ping host ring */

#define ANE_LEGACY_ALLOCS 128
#define ANE_LEGACY_FW_ALLOCS 32
#define ANE_LEGACY_BYTES SZ_16M

struct ane_legacy_buffer {
	void *cpu;
	dma_addr_t dma;
	size_t size;
};

struct ane_rtclient {
	struct device *dev;
	void __iomem *engine;
	void __iomem *pmgr;
	struct apple_rtkit *rtk;
	/* ane_cpu reset (DT resets = <&ane_cpu>, ps RESET bit 31). */
	struct reset_control *cpu_rst;

	/* fw_start=1: view over this device for the shared boot/fwload
	 * contract units (ane_t6021_boot.c/ane_t6021_fwload.c). */
	struct ane_t6021 *fw;
	/* A CPU we released is (or may be) running: state is HELD —
	 * surfaces/rings/IRQ/power links preserved, no unwind, reboot
	 * is the only reclamation (wedged-pin rule). */
	bool held;

	struct delayed_work poll_work;

	bool boot_done;

	/* Lowest app endpoint (>= 0x20) the fw announced in EPMAP and we
	 * STARTEPed; 0 = none. The ANE command endpoint candidate. */
	u8 cmd_ep;
	/* ChMan descriptor table validated in the 'IPC ' surface. */
	bool chman_ok;
	struct ane_legacy_buffer legacy_buffers[ANE_LEGACY_ALLOCS];
	u32 legacy_allocated;
	size_t legacy_bytes;
	u32 legacy_malloc_cursor;
	u32 legacy_cmd_cursor[ANE_T6021_CHMAN_COUNT];
	u64 legacy_ack_ns;

	dma_addr_t ring_iova;
	void *ring;

	bool csne_setup_done;
	u32 csne_cursor;	/* K14 wrap-semantics write cursor */
};

/* Each rtkit.c boot-handshake wait (EPMAP, IOP power ack, AP power ack)
 * is 1 s, and the fw sends HELLO only after its ChMan DONE, so the
 * client retries -ETIME waits up to this bound. */
static unsigned int hello_wait_ms = 10000;
module_param(hello_wait_ms, uint, 0444);
MODULE_PARM_DESC(hello_wait_ms,
		 "Upper bound for the RTKit boot handshake (HELLO/EPMAP/power acks), retried in 1 s rtkit.c waits (default 10000)");

static bool start_app_eps = true;
module_param(start_app_eps, bool, 0444);
MODULE_PARM_DESC(start_app_eps,
		 "After the handshake, STARTEP every fw-announced app endpoint (>= 0x20; fw mgmt type 5, flag bit 1). Default on");

static bool scratch3_ack = true;
module_param(scratch3_ack, bool, 0444);
MODULE_PARM_DESC(scratch3_ack,
		 "fw_start=1 only: after DONE, write the host ack SCRATCH3 = 0x08042006 the fw spins on before starting RTKit (selene 0x7edc; kext 0x95eaee4). Default on; 0 withholds it to bisect");

static bool legacy_only;
module_param(legacy_only, bool, 0444);
MODULE_PARM_DESC(legacy_only,
		 "EXPERIMENTAL, default off: pinned 13.5 legacy ChMan handshake without RTKit; requires fw_start=1 and fw_start_rtb_mode=0. Validates and initializes host rings before ACK. All DMA and power remain held until reboot; no inference qualification.");

static bool legacy_query;
module_param(legacy_query, bool, 0444);
MODULE_PARM_DESC(legacy_query,
		 "EXPERIMENTAL: service bounded startup allocations and CONFIG_GET for 15 seconds; requires legacy_only and scratch3_ack. DMA stays held until reboot.");
static bool legacy_load;
module_param(legacy_load, bool, 0444);
MODULE_PARM_DESC(legacy_load, "Load the pinned H14 convolution after CONFIG_GET; retain all DMA until reboot.");
static bool legacy_seq;
module_param(legacy_seq, bool, 0444);
MODULE_PARM_DESC(legacy_seq,
		 "After CONFIG_GET (and legacy_load), run apple/ane/seq/NN.bin command files in order.");
static bool legacy_t2h_ack = true;
module_param(legacy_t2h_ack, bool, 0444);
MODULE_PARM_DESC(legacy_t2h_ack,
		 "In legacy_seq, return each drained target-to-host slot to the firmware.");
static bool legacy_resource;
module_param(legacy_resource, bool, 0444);
MODULE_PARM_DESC(legacy_resource,
		 "After CONFIG_GET, send kext opcode 0x22 RESOURCE_INFO_GET, len 0x64, same channel. Requires legacy_query.");


static bool legacy_silent;
module_param(legacy_silent, bool, 0444);
MODULE_PARM_DESC(legacy_silent,
		 "Diagnostic: suppress query-window console output; dump buffered event timestamps after service ends.");
static bool legacy_notify_ack;
module_param(legacy_notify_ack, bool, 0444);
MODULE_PARM_DESC(legacy_notify_ack,
		 "Diagnostic: acknowledge observed firmware notifications before servicing shared rings.");

static bool legacy_fast_poll;
module_param(legacy_fast_poll, bool, 0444);
MODULE_PARM_DESC(legacy_fast_poll,
		 "Diagnostic: service shared rings every 50 us instead of sleeping 1-2 ms.");

static bool csne_ping;
module_param(csne_ping, bool, 0444);
MODULE_PARM_DESC(csne_ping,
		 "GATED [INFERENCE]: after the handshake, announce a 64 KiB host ring on the command endpoint with the fw buffer word, then send CSNE_CMD_PING (0x11) and BUILDINFO (0x06) as offset|len words. Default off");

static bool fw_start;
module_param(fw_start, bool, 0444);
MODULE_PARM_DESC(fw_start,
		 "OPT-IN: fenced Linux-context firmware start — stage selene (fw_load=1 required), alias it at the latched RVBAR entry, then run the contract-pinned scratch/RUN/READY/publish/wake sequence and continue into the RTKit handshake. Default off = refuse at the CPU gate (evidence-backed: the proven-safe starter is a quiesce-context write-arm; kernel-context start is the open discriminator). Bounded: <=1 s polls, no retry, no ps@2e0 writes.");

/*
 * fw-start-debug (2026-09-22): fwstart#2 hard-crashed with no capture.
 * Two knobs make every attempt observable and bounded:
 *   fw_start_state_report=1 — stage fwload + alias (IOMMU only, no
 *     engine writes), dump the whitelisted ASC state via dev_emerg,
 *     then unwind CLEANLY. Zero-risk observability proof.
 *   fw_start_stop_after=N — run the boot sequence only through step N
 *     (1 grant tunables, 2 scratch clear+pulse, 3 rvbar decision,
 *     4 cpu release + poll A), then stop with -ECANCELED. While no
 *     CPU started the stop unwinds cleanly (rmmod-able, no reboot
 *     needed); step 4 leaves the HELD wedged-pin state. 0 = full run.
 * Smallest crashing N localizes the fatal write; per-write dev_emerg
 * phases (30 ms drain) beat the write to every console.
 */
static int fw_start_stop_after;
module_param(fw_start_stop_after, int, 0444);
MODULE_PARM_DESC(fw_start_stop_after,
		 "fw-start-debug bisect: 0 = full sequence; 1..4 = stop after that step (-ECANCELED). Steps: 1 tunables, 2 scratch, 3 rvbar, 4 RUN+pollA");

static bool fw_start_state_report;
module_param(fw_start_state_report, bool, 0444);
static bool fw_start_skip_genpd;
module_param(fw_start_skip_genpd, bool, 0444);
MODULE_PARM_DESC(fw_start_skip_genpd,
		 "fw-start-debug: skip pm_runtime_resume_and_get in probe and run the static sequence directly. Use only when the islands already read on (recorded 'available' devlinks); the wedged-bind evidence shows the raise hangs the writer on this box.");
MODULE_PARM_DESC(fw_start_state_report,
		 "fw-start-debug: stage firmware + alias, dump ASC state (reads only), then clean unwind — no boot writes");

/*
 * fw_start_table_mode: the pre-CPU engine table block
 * (eng+0xB38/0xB98/0xBF8 <- 0x01FF01FF, kext-sourced, run EVERY
 * EnableANEClocksAndPower per pass4/pass5). 0 = abort before any
 * write, 1 = write the table, 2 = skip it (the 2026-09-20-era
 * diagnostic; the B3 run proved RUN itself is wedge-free with the
 * repaired dtb, so the table is the next discriminator, not a
 * live-fault gate). Default 2 keeps the shipped behavior.
 */
static int fw_start_table_mode = 2;
module_param(fw_start_table_mode, int, 0444);
MODULE_PARM_DESC(fw_start_table_mode,
		 "pre-CPU table block: 0 abort, 1 write (kext-faithful), 2 skip (default)");

static bool fw_start_rtb_mode;
module_param(fw_start_rtb_mode, bool, 0444);
MODULE_PARM_DESC(fw_start_rtb_mode,
		 "fw-start-debug: S1 writes SCRATCH6=0 (RTBuddy/RTKit-app-endpoint select) instead of 1 (legacy). In RTBuddy mode listen for HELLO, do not gate on READY.");
static bool fw_start_venc_gates = true;
module_param(fw_start_venc_gates, bool, 0444);
MODULE_PARM_DESC(fw_start_venc_gates,
		 "Raise the VENC rails the ANE clock-ids need (VENC_SYS 0x2902803e0, then PIPE4/PIPE5/ME0 at 0x290288008/10/18), kext order, parents first. The ANE complex sits behind VENC rails on T6021; Linux claims none of them. Disable only to bisect.");

static bool fw_start_mpm_off = true;
module_param(fw_start_mpm_off, bool, 0444);
MODULE_PARM_DESC(fw_start_mpm_off,
		 "fw_start=1: before the boot sequence's first engine write, power ane_sys_mpm@4000 down to TARGET 0 (the macOS working state) and refuse the sequence unless ane_sys/ane_cpu read the macOS AUTO_ENABLE on-form and td/base/set1-4 read ACTUAL 0xf. 0 keeps the boot-raised ane_sys_mpm on, to bisect.");

/* 0 = off. Nonzero is the CNTFRQ value written to the patchbay before
 * CPU_CONTROL release. The module refuses the write unless the live
 * 36 bytes still match the pinned pattern. */
static u32 patch_timer_freq;
module_param(patch_timer_freq, uint, 0444);
MODULE_PARM_DESC(patch_timer_freq,
		 "fw_start=1: before CPU release, write this to patchbay armv8_timer_frequency at PA 0x10001406880. 0 = off. Refuses unless islands read ACTUAL=0xf, fw_alias_reserved=1, and the 36 bytes at PA 0x10001406870 match (value 0, next tag LRSD).");

static bool fw_start_mbox_ctrl_bit19;
module_param(fw_start_mbox_ctrl_bit19, bool, 0444);
MODULE_PARM_DESC(fw_start_mbox_ctrl_bit19,
		 "fw_start=1: write 0x000a0001 (macOS working-state value, bit 19 set) to A2I_CTRL (0x1408110) and I2A_CTRL (0x1408114) before CPU release, logging before/after reads. Default 0 (off).");

static bool fw_start_dart_single_stream;
module_param(fw_start_dart_single_stream, bool, 0444);
MODULE_PARM_DESC(fw_start_dart_single_stream,
		 "fw_start=1: configure all three ANE DARTs to macOS working-state single-stream form (stream 0 only via DISABLE_STREAMS 0xc20, dart0 PROTECT 0x6) before CPU release, logging before/after reads. Default 0 (off).");

static bool fw_start_core1_run;
module_param(fw_start_core1_run, bool, 0444);
MODULE_PARM_DESC(fw_start_core1_run,
		 "fw_start=1: write 0x10 (RUN) to secondary core control engine+0x1400444 before CPU release, logging before/after reads. Default 0 (off).");

static bool fw_start_wrapper_b80_unmask;
module_param(fw_start_wrapper_b80_unmask, bool, 0444);
MODULE_PARM_DESC(fw_start_wrapper_b80_unmask,
		 "fw_start=1: write 0xffffffff to KIC interrupt registers engine+0x1400b80..b94 and +0x1400bfc before CPU release, logging before/after reads. Default 0 (off).");

static bool fw_start_dapf;
module_param(fw_start_dapf, bool, 0444);
MODULE_PARM_DESC(fw_start_dapf,
		 "fw_start=1: before CPU release, program the dart-ane0 DAPF (PA 0x285804000, ADT reg[3] DAPFLLT) with the five J414c ADT dapf-instance-0 windows, as XNU does, logging before/after reads. Default 0 (off).");

/*
 * Raise the VENC rails the ADT wires as ane0 clock-ids, kext order,
 * parents first. Plain TARGET write + low-byte-0xff poll, exactly the
 * validatePSReg semantics: write 0xf, wait until (val & 0xff) == 0xff
 * (TARGET nibble 0xf AND ACTUAL nibble 0xf). NOTE: no BIT(28)/BIT(31)
 * munging — the earlier code added AUTO_ENABLE and cleared bit 31,
 * which the kext never does, and which can put 0xf0003ff-class values
 * on words whose AUTO-enable semantics are unowned here. Never a
 * TARGET=0 write.
 */
static int ane_rtclient_venc_gates(struct device *dev)
{
	static const struct {
		u32 off;
		u32 id;
		const char *name;
	} gates[4] = {
		{ 0x008, 318, "VENC_PIPE4" },
		{ 0x010, 319, "VENC_PIPE5" },
		{ 0x018, 320, "VENC_ME0" },
		{ 0x020, 321, "VENC_ME1" },
	};
	void __iomem *base;
	void __iomem *root;
	unsigned int i;
	int ret_all = 0;

	/* VENC_SYS (299) at +3e0 of window 0x290280000. DEPENDENCY
	 * UNPROVEN — receipt conflict on record (entry-alias pass-3:
	 * gate 473 virtual/no-op, clock-ids an ADT artifact; vs
	 * csne-cmd-path live: leaves grant only with the bit28 parent
	 * form; vs t602x-pmgr.dtsi:1920: leaves' parent is venc_dma
	 * @+8000, which this helper does not raise). Live 2026-09-26
	 * refusal (before 300 -> after 30f, ACTUAL 0) is consistent
	 * with the missing-parent reading. No raise form is changed
	 * here pending that proof; hardware write form belongs to the
	 * genpd-supported route if the dependency is proven. */
	root = ioremap_np(0x290280000ull, 0x1000);
	if (!root) {
		dev_emerg(dev, "VENC-ROOT: ioremap FAILED\n");
		return -ENOMEM;
	}
	{
		u32 before = readl(root + 0x3e0);
		u32 after;
		int ret;

		dev_emerg(dev, "VENC-ROOT VENC_SYS @+3e0 before=%08x\n",
			  before);
		if ((before & 0xff) != 0xff) {
			writel(before | 0xf, root + 0x3e0);
			ret = readl_poll_timeout(root + 0x3e0, after,
						 ((after & 0xff) == 0xff),
						 10, 50 * 1000);
			after = readl(root + 0x3e0);
			dev_emerg(dev,
				  "VENC-ROOT after=%08x ret=%pe\n",
				  after, ERR_PTR(ret));
			if (ret) {
				iounmap(root);
				return -ETIMEDOUT;
			}
		} else {
			dev_emerg(dev, "VENC-ROOT already on\n");
		}
	}
	iounmap(root);

	base = ioremap_np(0x290288000ull, 0x40);
	if (!base) {
		dev_emerg(dev, "VENC-GATES: ioremap FAILED\n");
		return -ENOMEM;
	}

	/* Read-scan the whole ps-regs[15] block first (reads are safe):
	 * which words are on (ACTUAL[7:4]==0xf, ON signature 0x3ff) vs
	 * idle (0x300)? B5: 0x008 read 0x300, TARGET took, ACTUAL stuck
	 * at 0 -> a parent rail in this block (or above) is down. */
	for (i = 0; i < 8; i++)
		dev_emerg(dev, "VENC-SCAN +%03x = %08x\n", i * 8,
			  readl(base + i * 8));

	/* Only the REAL ps words the kext touches: VENC_DMA at +000 must
	 * already read 0x3ff (VENC_SYS granted it), and the three leaves
	 * PIPE4/PIPE5/ME0 at +008/+010/+018. Never a TARGET=0 write. */
	for (i = 1; i <= 3; i++) {
		void __iomem *reg = base + i * 8;
		u32 before = readl(reg);
		u32 after;
		int ret;

		if ((before & 0xff) == 0xff)
			continue;
		dev_emerg(dev, "VENC-GATES +%03x before=%08x\n", i * 8,
			  before);
		writel(before | 0xf, reg);
		ret = readl_poll_timeout(reg, after,
					 ((after & 0xff) == 0xff),
					 10, 50 * 1000);
		after = readl(reg);
		dev_emerg(dev, "VENC-GATES +%03x after=%08x ret=%pe\n",
			  i * 8, after, ERR_PTR(ret));
		if (ret)
			ret_all = ret;
	}

	for (i = 0; i < 3; i++) {
		u32 v = readl(base + gates[i].off);

		dev_emerg(dev, "VENC-GATES %u %s final=%08x\n",
			  gates[i].id, gates[i].name, v);
		if ((v & 0xff) != 0xff)
			ret_all = -ETIMEDOUT;
	}

	iounmap(base);
	return ret_all;
}

static bool poll_rx;
module_param(poll_rx, bool, 0444);
MODULE_PARM_DESC(poll_rx,
		 "Drive RX by apple_rtkit_poll from a workqueue even though a recv IRQ exists (fallback if raw 0x374 is not the recv line)");

/* ---- RTKit callbacks ---- */

static void ane_rtclient_recv(void *cookie, u8 ep, u64 message)
{
	struct ane_rtclient *ane = cookie;

	/* App endpoints only reach here (rtkit.c owns 0..0x1f). Both
	 * wire shapes the fw uses are decoded side by side; which one a
	 * message is gets pinned on sight. */
	dev_info(ane->dev,
		 "rtkit app msg: ep=%#x msg=%016llx | as offset|len: off=%#llx len=%#llx | as buffer word: addr=%#llx size=%#x unit=%llu\n",
		 ep, message,
		 (u64)FIELD_GET(ANE_MBI_MSG48_OFF, message),
		 (u64)FIELD_GET(ANE_MBI_MSG48_LEN, message),
		 message & ANE_EP_DOORBELL_OFFSET,
		 ane_ep_doorbell_size(message),
		 (u64)FIELD_GET(ANE_EP_DOORBELL_UNIT, message));
}

static void ane_rtclient_crashed(void *cookie, const void *crashlog,
				 size_t size)
{
	struct ane_rtclient *ane = cookie;

	dev_err(ane->dev, "rtkit: coprocessor crashed (crashlog %zu bytes)\n",
		size);
	print_hex_dump(KERN_ERR, "ANE crashlog: ", DUMP_PREFIX_OFFSET, 16, 1,
		       crashlog, min_t(size_t, size, 256), false);
}

/* System-endpoint buffer grants (crashlog EP1, syslog EP2): rtkit.c
 * decodes the fw request (unit-1 buffer word, addr 0 = host allocates)
 * and replies with the same word carrying our IOVA. The fw asks for
 * the crashlog buffer with addr 0 (0x98e44) and for the syslog buffer
 * with addr 0 unless its own-buffer flag is set (0x98128), in which
 * case it does not wait for a reply — so a fw-provided address is
 * refused (mainline behavior) and only logged. The host allocation
 * must honor the fw entry-alias invariant (W16). */
static int ane_rtclient_shmem_setup(void *cookie,
				    struct apple_rtkit_shmem *bfr)
{
	struct ane_rtclient *ane = cookie;

	if (bfr->iova) {
		dev_warn(ane->dev,
			 "rtkit: fw-provided shmem iova=%pad size=%#zx — refused (unmapped by design)\n",
			 &bfr->iova, bfr->size);
		return -EINVAL;
	}

	bfr->buffer = dma_alloc_coherent(ane->dev, bfr->size, &bfr->iova,
					 GFP_KERNEL);
	if (!bfr->buffer)
		return -ENOMEM;
	if (ane->fw && !ane_t6021_fw_alias_iova_ok(ane->fw, bfr->iova,
						    bfr->size)) {
		dev_err(ane->dev,
			"rtkit: shmem grant %pad+%#zx overlaps the fw alias — refusing\n",
			&bfr->iova, bfr->size);
		dma_free_coherent(ane->dev, bfr->size, bfr->buffer, bfr->iova);
		bfr->buffer = NULL;
		return -EBUSY;
	}
	dev_info(ane->dev, "rtkit: shmem grant iova=%pad size=%#zx\n",
		 &bfr->iova, bfr->size);
	return 0;
}

static void ane_rtclient_shmem_destroy(void *cookie,
				       struct apple_rtkit_shmem *bfr)
{
	struct ane_rtclient *ane = cookie;

	if (!bfr->buffer)
		return;
	if (ane->held) {
		/* wedged-pin: a running ASC may still write here */
		dev_warn(ane->dev,
			 "rtkit: shmem %pad HELD (CPU started) — not freed\n",
			 &bfr->iova);
		return;
	}
	dma_free_coherent(ane->dev, bfr->size, bfr->buffer, bfr->iova);
}

static const struct apple_rtkit_ops ane_rtclient_rtkit_ops = {
	.crashed = ane_rtclient_crashed,
	.recv_message = ane_rtclient_recv,
	.shmem_setup = ane_rtclient_shmem_setup,
	.shmem_destroy = ane_rtclient_shmem_destroy,
};

/* ---- poll worker: RX fallback while the recv line is unproven ---- */

static void ane_rtclient_post_boot(struct work_struct *w)
{
	struct ane_rtclient *ane =
		container_of(to_delayed_work(w), struct ane_rtclient,
			     poll_work);

	apple_rtkit_poll(ane->rtk);

	if (!ane->boot_done) {
		schedule_delayed_work(&ane->poll_work, msecs_to_jiffies(10));
		return;
	}

	if (poll_rx)
		schedule_delayed_work(&ane->poll_work, HZ);
}

/* ---- ChMan descriptor table: the control-command validation step ----
 * Contract and static layout: ane_t6021_boot.h (ane_t6021_chman_*),
 * checked offline by tools/h14_boot_regression.c. In legacy_only mode a
 * failed check withholds the legacy P8 host ack (the fw must not see an
 * ACK over a table the host could not verify). */
static_assert(sizeof(struct ane_t6021_chman_desc) == ANE_T6021_CHMAN_ENTRY_SIZE);

static void ane_rtclient_validate_chman(struct ane_rtclient *ane)
{
	struct ane_t6021 *a = ane->fw;
	const struct ane_t6021_chman_desc *t;
	unsigned int i, bad;

	if (!a || !a->boot_ipc) {
		dev_info(ane->dev,
			 "chman: no host IPC surface (firmware not started by this driver) — table not validated\n");
		return;
	}
	if (a->boot_ipc_size < ANE_T6021_CHMAN_TOTAL) {
		dev_warn(ane->dev,
			 "chman: IPC surface %#llx bytes < fw layout %#x — table not validated\n",
			 a->boot_ipc_size, ANE_T6021_CHMAN_TOTAL);
		return;
	}

	dma_rmb();
	t = a->boot_ipc;
	dev_info(ane->dev,
		 "chman: IPC dva=%pad size=%#llx booted=%u scratch_result=%016llx (low32 = fw VA of its IPC mapping, 0x77a4)\n",
		 &a->boot_ipc_iova, a->boot_ipc_size, a->booted,
		 a->boot_scratch_result);

	bad = ane_t6021_chman_check(t, a->boot_ipc_iova);
	for (i = 0; i < ANE_T6021_CHMAN_COUNT; i++) {
		const struct ane_t6021_chman_desc *d = &t[i];
		const struct ane_t6021_chman_static *s = &ane_t6021_chman_layout[i];

		dev_info(ane->dev,
			 "chman[%u]: name=\"%.*s\" type=%u bit=%u size=%#llx ring=%#llx %s (static: %s/%u/%u/%#llx/ipc+%#x)\n",
			 i, ANE_T6021_CHMAN_NAME_LEN, d->name, d->type, d->bit,
			 d->size, d->ring, (bad & BIT(i)) ? "MISMATCH" : "OK",
			 s->name, s->type, s->bit, s->size, s->off);
		/* Ring head dump (first 32 bytes of the ring the
		 * descriptor names) for the receipt. */
		if (d->ring >= a->boot_ipc_iova &&
		    d->ring + 0x20 <= a->boot_ipc_iova + a->boot_ipc_size)
			print_hex_dump(KERN_INFO, "chman ring head: ",
				       DUMP_PREFIX_OFFSET, 16, 4,
				       a->boot_ipc + (d->ring - a->boot_ipc_iova),
				       0x20, false);
	}

	ane->chman_ok = !bad;
	dev_info(ane->dev, "chman: table %s (mismatch mask %#x)\n",
		 bad ? "NOT VALIDATED" : "VALIDATED", bad);
}

static struct ane_legacy_buffer *ane_rtclient_legacy_alloc(struct ane_rtclient *ane, u64 size)
{
	struct ane_legacy_buffer *buffer;

	if (!size || !IS_ALIGNED(size, SZ_16K) || size > SZ_2M ||
	    ane->legacy_allocated == ANE_LEGACY_ALLOCS ||
	    size > ANE_LEGACY_BYTES - ane->legacy_bytes)
		return ERR_PTR(-E2BIG);
	buffer = &ane->legacy_buffers[ane->legacy_allocated];
	buffer->cpu = dma_alloc_coherent(ane->dev, size, &buffer->dma, GFP_KERNEL);
	if (!buffer->cpu)
		return ERR_PTR(-ENOMEM);
	if (!IS_ALIGNED(buffer->dma, SZ_16K) ||
	    !ane_t6021_fw_alias_iova_ok(ane->fw, buffer->dma, size)) {
		dma_free_coherent(ane->dev, size, buffer->cpu, buffer->dma);
		buffer->cpu = NULL;
		return ERR_PTR(-ERANGE);
	}
	memset(buffer->cpu, 0, size);
	buffer->size = size;
	ane->legacy_bytes += size;
	ane->legacy_allocated++;
	return buffer;
}

static void ane_rtclient_legacy_state(struct ane_rtclient *ane, const char *phase, bool quiet)
{
	u32 control = readl(ane->engine + ANE_ASC_CPU_CONTROL);
	u32 status = readl(ane->engine + ANE_ASC_CPU_STATUS);
	u32 mask = readl(ane->engine + 0x1400a00);
	u32 power = readl(ane->pmgr + ANE_RTCLIENT_PS_CPU_ACTUAL_OFF);

	if (!quiet)
		dev_info(ane->dev,
			 "LEGACY state %s control=%08x status=%08x pic_mask=%08x ps=%08x\n",
			 phase, control, status, mask, power);
}

/* Selene 13.5 VM 0x75b0: physical channel bit maps to logical IRQ 112+channel. */
static int ane_rtclient_legacy_exchange(struct ane_rtclient *ane,
				       struct ane_legacy_buffer *command, size_t length, u16 opcode,
				       unsigned int channel, unsigned int timeout_ms)
{
	struct ane_t6021 *a = ane->fw;
	u64 *io, *malloc_ring, *slot, header, size, tag;
	u64 *t2h_buf, *t2h_ioq, b4_before[8], b6_before[8];
	unsigned int k;
	void __iomem *ipi;
	unsigned int cursor = ane->legacy_malloc_cursor;
	unsigned long deadline;
	u32 *reply, control = U32_MAX;
	int result = -ETIMEDOUT;
	u64 allocation_ns[ANE_LEGACY_FW_ALLOCS][4] = {};
	u64 query_ns[3] = {};
	u64 exit_ns;
	unsigned int observed = 0, i;
	u64 first_notify_ns = 0;
	u32 first_pending = 0, first_after = 0, notify_count = 0;

	if (!ane->held || !ane->chman_ok ||
	    ane_t6021_chman_check(a->boot_ipc, a->boot_ipc_iova))
		return -EPROTO;
	ipi = ioremap_np(0x285844000ull, 0xc004);
	if (!ipi)
		return -ENOMEM;
	if (length < 8 || length > command->size ||
	    channel >= ANE_T6021_CHMAN_COUNT) {
		result = -EINVAL;
		goto out;
	}
	io = a->boot_ipc + ane_t6021_chman_layout[channel].off +
	     (size_t)ane->legacy_cmd_cursor[channel] * 64;
	dev_info(ane->dev, "LEGACY cmd slot ch=%u slot=%u hdr=%016llx\n", channel,
		 ane->legacy_cmd_cursor[channel], READ_ONCE(io[0]));
	malloc_ring = a->boot_ipc + ane_t6021_chman_layout[5].off;
	t2h_buf = a->boot_ipc + ane_t6021_chman_layout[4].off;
	t2h_ioq = a->boot_ipc + ane_t6021_chman_layout[6].off;
	for (k = 0; k < 8; k++) {
		b4_before[k] = READ_ONCE(t2h_buf[k]);
		b6_before[k] = READ_ONCE(t2h_ioq[k]);
	}
	if (!(READ_ONCE(io[0]) & 1)) {
		result = -EBUSY;
		goto out;
	}
	reply = command->cpu;
	((u16 *)reply)[2] = opcode;
	WRITE_ONCE(io[1], length);
	WRITE_ONCE(io[2], length);
	dma_wmb();
	query_ns[0] = ktime_get_ns();
	WRITE_ONCE(io[0], command->dma);
	dma_wmb();
	query_ns[1] = ktime_get_ns();
	writel(BIT(ane_t6021_chman_layout[channel].bit), ipi);
	query_ns[2] = ktime_get_ns();
	if (!legacy_silent)
		dev_info(ane->dev, "LEGACY command published dma=%pad size=%zu cmd=%#x channel=%s irq=%u\n",
			 &command->dma, length, opcode, ane_t6021_chman_layout[channel].name,
			 112 + ane_t6021_chman_layout[channel].bit);
	deadline = jiffies + msecs_to_jiffies(timeout_ms);
	while (time_before(jiffies, deadline)) {
		u32 current_control, pending = readl(ipi + 0x8000);

		if (pending) {
			u64 notify_ns = ktime_get_ns();
			u32 after;

			if (legacy_notify_ack) {
				writel(pending, ipi + 0xc000);
				mb();
			}
			after = readl(ipi + 0x8000);
			if (!notify_count) {
				first_notify_ns = notify_ns;
				first_pending = pending;
				first_after = after;
			}
			notify_count++;
		}
		current_control = readl(ane->engine + ANE_ASC_CPU_CONTROL);

		if (current_control != control) {
			ane_rtclient_legacy_state(ane, "query-transition", legacy_silent);
			control = current_control;
		}
		slot = malloc_ring + cursor * 8;
		header = READ_ONCE(slot[0]);
		if (!(header & 1)) {
			struct ane_legacy_buffer *buffer;
			u64 *times;

			if (observed == ARRAY_SIZE(allocation_ns)) {
				result = -EOVERFLOW;
				goto out;
			}
			times = allocation_ns[observed++];
			times[0] = ktime_get_ns();

			dma_rmb();
			size = READ_ONCE(slot[1]);
			tag = READ_ONCE(slot[2]);
			if (!legacy_silent)
				dev_info(ane->dev, "LEGACY allocation slot=%u hdr=%#llx size=%#llx tag=%#llx\n",
					 cursor, header, size, tag);
			ane_rtclient_legacy_state(ane, "allocation-request", legacy_silent);
			if (header || tag > U32_MAX) {
				result = -EOPNOTSUPP;
				goto out;
			}
			buffer = ane_rtclient_legacy_alloc(ane, size);
			if (IS_ERR(buffer)) {
				result = PTR_ERR(buffer);
				goto out;
			}
			WRITE_ONCE(slot[1], 0);
			WRITE_ONCE(slot[2], ane->legacy_allocated);
			times[1] = ktime_get_ns();
			dma_wmb();
			WRITE_ONCE(slot[0], buffer->dma | 1);
			dma_wmb();
			times[2] = ktime_get_ns();
			writel(BIT(5), ipi);
			times[3] = ktime_get_ns();
			if (!legacy_silent)
				dev_info(ane->dev, "LEGACY allocation reply dma=%pad bytes=%zu irq=117\n",
					 &buffer->dma, buffer->size);
			ane_rtclient_legacy_state(ane, "allocation-reply", legacy_silent);
			cursor = (cursor + 1) % ane_t6021_chman_layout[5].size;
		}
		header = READ_ONCE(io[0]);
		if (header & 1) {
			dma_rmb();
			if (!legacy_silent)
				dev_info(ane->dev,
					 "LEGACY query reply hdr=%#llx len=%#llx tag=%#llx words=%08x,%08x,%08x,%08x\n",
					 header, READ_ONCE(io[1]), READ_ONCE(io[2]),
					 READ_ONCE(reply[0]), READ_ONCE(reply[1]),
					 READ_ONCE(reply[2]), READ_ONCE(reply[3]));
			result = (header == (command->dma | 1) && READ_ONCE(io[1]) == length &&
				  READ_ONCE(io[2]) == 0 && ((u16 *)reply)[2] == opcode &&
				  ((u16 *)reply)[3] == 0) ? 0 : -EPROTO;
			ane->legacy_cmd_cursor[channel] = (ane->legacy_cmd_cursor[channel] + 1) %
				ane_t6021_chman_layout[channel].size;
			goto out;
		}
		if (legacy_fast_poll)
			udelay(50);
		else
			usleep_range(1000, 2000);
	}
	dev_info(ane->dev, "LEGACY mailbox final ch=%u io=%016llx %016llx %016llx\n",
		 channel, READ_ONCE(io[0]), READ_ONCE(io[1]), READ_ONCE(io[2]));
	dev_info(ane->dev, "LEGACY T2H BUF %016llx %016llx %016llx %016llx | %016llx %016llx %016llx %016llx\n",
		 b4_before[0], b4_before[1], b4_before[2], b4_before[3],
		 READ_ONCE(t2h_buf[0]), READ_ONCE(t2h_buf[1]), READ_ONCE(t2h_buf[2]), READ_ONCE(t2h_buf[3]));
	dev_info(ane->dev, "LEGACY T2H IOT %016llx %016llx %016llx %016llx | %016llx %016llx %016llx %016llx\n",
		 b6_before[0], b6_before[1], b6_before[2], b6_before[3],
		 READ_ONCE(t2h_ioq[0]), READ_ONCE(t2h_ioq[1]), READ_ONCE(t2h_ioq[2]), READ_ONCE(t2h_ioq[3]));
 out:
	ane->legacy_malloc_cursor = cursor;
	exit_ns = ktime_get_ns();
	ane_rtclient_legacy_state(ane, "query-exit", false);
	dev_info(ane->dev, "LEGACY timing silent=%u ack=%llu publish_before=%llu irq_before=%llu irq_after=%llu exit=%llu\n",
		 legacy_silent, ane->legacy_ack_ns, query_ns[0], query_ns[1], query_ns[2], exit_ns);
	dev_info(ane->dev, "LEGACY notify ack=%u count=%u first_ns=%llu pending=%08x after=%08x\n",
		 legacy_notify_ack, notify_count, first_notify_ns, first_pending, first_after);
	for (i = 0; i < observed; i++)
		dev_info(ane->dev, "LEGACY timing allocation=%u observed=%llu publish_before=%llu irq_before=%llu irq_after=%llu\n",
			 i, allocation_ns[i][0], allocation_ns[i][1], allocation_ns[i][2], allocation_ns[i][3]);
	iounmap(ipi);
	if (a->boot_ipc) {
		u64 *t2h = a->boot_ipc + ane_t6021_chman_layout[6].off;
		dev_info(ane->dev, "LEGACY IO_T2H %016llx %016llx %016llx %016llx\n",
			 READ_ONCE(t2h[0]), READ_ONCE(t2h[1]), READ_ONCE(t2h[2]), READ_ONCE(t2h[3]));
	}
	dev_info(ane->dev, "LEGACY service stopped result=%d channel=%u allocations=%u held_bytes=%zu\n",
		 result, channel, ane->legacy_allocated, ane->legacy_bytes);
	return result;
}

#include "ane_t6021_legacy_load.h"
#include "ane_t6021_legacy_seq.h"

static int ane_rtclient_legacy_resource_info(struct ane_rtclient *ane)
{
	struct ane_legacy_buffer *command;
	struct ane_t6021 *a = ane->fw;
	u64 *io;
	u32 *words;
	u32 before[3];
	void __iomem *ipi;
	unsigned long deadline;
	int result = -ETIMEDOUT;

	if (!a || !a->boot_ipc)
		return -EPROTO;
	command = ane_rtclient_legacy_alloc(ane, SZ_16K);
	if (IS_ERR(command))
		return PTR_ERR(command);
	words = command->cpu;
	memset(words, 0, 0x0c);
	((u16 *)words)[2] = 0x04;
	before[0] = words[0];
	before[1] = words[1];
	before[2] = words[2];
	io = a->boot_ipc + ane_t6021_chman_layout[1].off;
	WRITE_ONCE(io[8], command->dma | 1);
	WRITE_ONCE(io[9], 0x0c);
	WRITE_ONCE(io[10], 0x0c);
	dma_wmb();
	dev_info(ane->dev,
		 "LEGACY SLOT1 dma=%pad opcode=0x04 phase=1\n",
		 &command->dma);
	ipi = ioremap_np(0x285844000ull, 0xc004);
	if (!ipi)
		return -ENOMEM;
	writel(BIT(1), ipi);
	deadline = jiffies + msecs_to_jiffies(3000);
	while (time_before(jiffies, deadline)) {
		if (READ_ONCE(words[0]) != before[0] ||
		    READ_ONCE(words[1]) != before[1] ||
		    READ_ONCE(words[2]) != before[2]) {
			result = 0;
			break;
		}
		usleep_range(1000, 2000);
	}
	dev_info(ane->dev,
		 "LEGACY SLOT1 result=%d words=%08x %08x %08x\n",
		 result, READ_ONCE(words[0]), READ_ONCE(words[1]),
		 READ_ONCE(words[2]));
	iounmap(ipi);
	return result;
}

static int ane_rtclient_legacy_query(struct ane_rtclient *ane)
{
	struct ane_legacy_buffer *command = ane_rtclient_legacy_alloc(ane, SZ_16K);
	int result;

	if (IS_ERR(command))
		return PTR_ERR(command);
	result = ane_rtclient_legacy_exchange(ane, command, 16, 3, 1, 3000);
	dev_info(ane->dev, "LEGACY CONFIG_GET words %08x %08x %08x %08x\n",
		 READ_ONCE(((u32 *)command->cpu)[0]), READ_ONCE(((u32 *)command->cpu)[1]),
		 READ_ONCE(((u32 *)command->cpu)[2]), READ_ONCE(((u32 *)command->cpu)[3]));
	if (!result && !READ_ONCE(((u32 *)command->cpu)[2]))
		return -EPROTO;
	if (!result && legacy_resource)
		return ane_rtclient_legacy_resource_info(ane);
	return result;
}

/* ---- app endpoints ---- */

/* STARTEP every announced app endpoint. Mainline apple_rtkit_start_ep
 * sends mgmt type 5 with flag bit 1; the fw mgmt dispatcher (0x97364
 * case 5 -> 0x973b4) reads ep from [47:32] and starts it on flag == 2
 * (0x974bc). Same call every Asahi RTKit client makes (SMC on 0x20). */
static void ane_rtclient_start_app_eps(struct ane_rtclient *ane)
{
	int ep;

	for (ep = ANE_RTKIT_APP_EP_START; ep < 0x100; ep++) {
		int ret;

		if (!apple_rtkit_has_endpoint(ane->rtk, ep))
			continue;
		ret = apple_rtkit_start_ep(ane->rtk, ep);
		dev_info(ane->dev, "rtkit: STARTEP app ep %#x -> %pe\n", ep,
			 ERR_PTR(ret));
		if (!ret && !ane->cmd_ep)
			ane->cmd_ep = ep;
	}
	if (!ane->cmd_ep)
		dev_warn(ane->dev,
			 "rtkit: fw announced no app endpoint (static table predicts 0x20 \"user1\")\n");
}

/* GATED [INFERENCE] CSNE submit with K14 rtbuddyEndpointSendMessage
 * wrap semantics (W4 receipt 2026-09-19-h14-w4-csne-submission): the
 * slot cursor is kept only when cursor+size fits strictly below the
 * ring size (an exact fit wraps to 0), the command is memcpy'd into
 * the coherent ring, and the 48-bit offset|len doorbell follows a
 * dma_wmb. Oversized commands fail fast at the fw's own bound
 * (0x4d134: work items >= 0x1b89 rejected). Returns the slot cursor
 * used, or a negative error. What remains unproven: that the app
 * endpoint takes a buffer word to set its ring base ([obj+0x28])
 * before offset|len words. Everything sent is logged; a wrong guess
 * can crash the fw (crashlog is captured), never the host. */
static int ane_rtclient_csne_submit(struct ane_rtclient *ane,
				    const void *cmd, size_t size)
{
	u32 cursor = ane->csne_cursor;
	u64 msg;
	int ret;

	if (size < sizeof(struct ane_csne_hdr) ||
	    size > ANE_CSNE_CMD_MAX_SIZE)
		return -EINVAL;
	if (size > ANE_RTCLIENT_RING_SIZE)
		return -E2BIG;
	if (cursor + size >= ANE_RTCLIENT_RING_SIZE)
		cursor = 0;

	memcpy(ane->ring + cursor, cmd, size);
	dma_wmb();

	msg = ane_mbi_msg48_encode(cursor, size);
	ret = apple_rtkit_send_message(ane->rtk, ane->cmd_ep, msg, NULL,
				       false);
	dev_info(ane->dev,
		 "csne: submit ep=%#x cursor=%u len=%zu word=%016llx -> %pe\n",
		 ane->cmd_ep, cursor, size, msg, ERR_PTR(ret));
	if (ret)
		return ret;
	ane->csne_cursor = cursor + size;
	return cursor;
}

static int ane_rtclient_csne_submit(struct ane_rtclient *ane,
				    const void *cmd, size_t size);

static void ane_rtclient_csne_ping(struct ane_rtclient *ane)
{
	u64 word;
	int ret;

	if (!ane->cmd_ep) {
		dev_info(ane->dev, "csne: no command endpoint; no ping\n");
		return;
	}

	if (!ane->csne_setup_done) {
		/* Never devm/dmam: under the wedged pin a started ASC may
		 * still read this ring after unbind; remove() frees it
		 * only when not held. */
		ane->ring = dma_alloc_coherent(ane->dev, ANE_RTCLIENT_RING_SIZE,
					       &ane->ring_iova, GFP_KERNEL);
		if (!ane->ring)
			return;
		if (ane->fw && !ane_t6021_fw_alias_iova_ok(ane->fw, ane->ring_iova,
							    ANE_RTCLIENT_RING_SIZE)) {
			dev_err(ane->dev, "csne: ring overlaps the fw alias — no ping\n");
			return;
		}
		word = ane_ep_doorbell_encode(ane->ring_iova,
					      ANE_RTCLIENT_RING_SIZE);
		ret = apple_rtkit_send_message(ane->rtk, ane->cmd_ep, word,
					       NULL, false);
		dev_info(ane->dev,
			 "csne: ring announce ep=%#x iova=%pad size=%#x word=%016llx -> %pe [INFERENCE]\n",
			 ane->cmd_ep, &ane->ring_iova, ANE_RTCLIENT_RING_SIZE,
			 word, ERR_PTR(ret));
		if (ret)
			return;
		ane->csne_setup_done = true;
		ane->csne_cursor = 0;
	}

	{
		struct ane_csne_hdr hdr;
		int slot;

		ane_csne_hdr_init(&hdr, CSNE_CMD_PING);
		slot = ane_rtclient_csne_submit(ane, &hdr, sizeof(hdr));
		if (slot >= 0) {
			ane_csne_hdr_init(&hdr, CSNE_CMD_BUILDINFO);
			ane_rtclient_csne_submit(ane, &hdr, sizeof(hdr));
		}
	}

}

/* ---- probe ---- */
/* Pinned live pattern at PA 0x10001406870, 9 words. Word 4 is the
 * frequency value (must be 0); word 5 is the LRSD tag. Confirmed by
 * read on the M2, 2026-09-25. */
static const u32 ane_patchbay_expect[9] = {
	0x00000000, 0x00000000, 0x76384671, 0x00000004, 0x00000000,
	0x4453524c, 0x00000001, 0x53565300, 0x00000844,
};

static int ane_rtclient_patch_timer_freq(struct ane_rtclient *ane, u32 freq)
{
	static const unsigned int islands[] = {
		0x2e0, 0x4000, 0x4008, 0x4010, 0x4018, 0x4020, 0x4028, 0x4030
	};
	struct device *dev = ane->dev;
	void __iomem *win;
	unsigned int i;
	u32 before, after;

	for (i = 0; i < ARRAY_SIZE(islands); i++) {
		u32 v = readl(ane->pmgr + islands[i]);

		if (FIELD_GET(ANE_PS_ACTUAL, v) != ANE_PS_ON) {
			dev_emerg(dev,
				  "timer-freq: pmgr+%#x=%08x ACTUAL != 0xf — refusing\n",
				  islands[i], v);
			return -EIO;
		}
	}
	if (!ane_t6021_fw_alias_is_reserved()) {
		dev_emerg(dev,
			  "timer-freq: fw_alias_reserved=0 — core would not fetch this PA; refusing\n");
		return -EINVAL;
	}
	/* Same non-posted map the observer used to confirm these bytes.
	 * Not memremap: a second memremap of this DRAM EXEC-faults. */
	win = ioremap_np(0x10001406870ull, 36);
	if (!win)
		return -ENOMEM;
	for (i = 0; i < 9; i++) {
		u32 got = readl(win + 4 * i);

		if (got != ane_patchbay_expect[i]) {
			dev_emerg(dev,
				  "timer-freq: word[%u]=%08x want %08x — not writing\n",
				  i, got, ane_patchbay_expect[i]);
			iounmap(win);
			return -EIO;
		}
	}
	before = readl(win + 16);
	writel(freq, win + 16);
	after = readl(win + 16);
	iounmap(win);
	dev_emerg(dev,
		  "timer-freq: PA 0x10001406880 before=%08x wrote=%08x readback=%08x\n",
		  before, freq, after);
	return after == freq ? 0 : -EIO;
}

/*
 * macOS runs the ANE with ane_sys_mpm@4000 off: it reads 0x300 in all 14
 * samples of ane-linux-experiments receipt 2026-09-25-macos-ane-pstable,
 * including those at 4.8 W encoder load. In the same samples ane_sys@260 and
 * ane_cpu@2e0 read 0x1f0003ff (AUTO_ENABLE, ACTUAL and TARGET 0xf) and the
 * six compute islands read 0x3ff. Linux raises ane_sys_mpm at boot because
 * the stock DTB marks it apple,always-on, and genpd never lowers an
 * always-on domain. Power it down with the write apple_pmgr_ps_set()
 * issues for PWRGATE, then confirm the rest of the macOS form.
 */
static int ane_rtclient_ps_macos_form(struct ane_rtclient *ane)
{
	static const struct {
		u32 off;
		bool auto_enable;
		const char *name;
	} on[] = {
		{ 0x260, true, "ane_sys" },	{ 0x2e0, true, "ane_cpu" },
		{ 0x4008, false, "ane_td" },	{ 0x4010, false, "ane_base" },
		{ 0x4018, false, "ane_set1" },	{ 0x4020, false, "ane_set2" },
		{ 0x4028, false, "ane_set3" },	{ 0x4030, false, "ane_set4" },
	};
	struct device *dev = ane->dev;
	void __iomem *mpm = ane->pmgr + 0x4000;
	unsigned int i;
	int ret;
	bool ok;
	u32 v;

	v = readl(mpm);
	dev_emerg(dev, "PS-FORM ane_sys_mpm@4000 before=%08x\n", v);
	if (v & (ANE_PS_TARGET | ANE_PS_ACTUAL)) {
		writel(v & ~(ANE_PS_AUTO_ENABLE | ANE_PS_WAS_GATED |
			     ANE_PS_TARGET), mpm);
		ret = readl_poll_timeout(mpm, v,
					 !FIELD_GET(ANE_PS_ACTUAL, v),
					 10, 100 * 1000);
		dev_emerg(dev, "PS-FORM ane_sys_mpm@4000 after=%08x ret=%pe\n",
			  v, ERR_PTR(ret));
		if (ret)
			return ret;
	}

	ret = 0;
	for (i = 0; i < ARRAY_SIZE(on); i++) {
		v = readl(ane->pmgr + on[i].off);
		ok = FIELD_GET(ANE_PS_ACTUAL, v) == ANE_PS_ON &&
		     FIELD_GET(ANE_PS_TARGET, v) == ANE_PS_ON &&
		     (!on[i].auto_enable || (v & ANE_PS_AUTO_ENABLE));
		dev_emerg(dev, "PS-FORM %s@%#x=%08x %s\n", on[i].name,
			  on[i].off, v, ok ? "macOS form" : "NOT macOS form");
		if (!ok)
			ret = -EIO;
	}
	return ret;
}

static void ane_rtclient_apply_mbox_ctrl_bit19(struct ane_rtclient *ane)
{
	u32 a2i_before, a2i_after;
	u32 i2a_before, i2a_after;

	a2i_before = readl(ane->engine + ANE_ASC_MBOX_A2I_CTRL);
	i2a_before = readl(ane->engine + ANE_ASC_MBOX_I2A_CTRL);

	/* macOS working-state value: 0x000a0001 (bit 19 + bit 17 EMPTY + bit 0 ENABLE) */
	writel(0x000a0001, ane->engine + ANE_ASC_MBOX_A2I_CTRL);
	writel(0x000a0001, ane->engine + ANE_ASC_MBOX_I2A_CTRL);

	mb();
	a2i_after = readl(ane->engine + ANE_ASC_MBOX_A2I_CTRL);
	i2a_after = readl(ane->engine + ANE_ASC_MBOX_I2A_CTRL);

	dev_emerg(ane->dev,
		  "BOOT-PHASE mbox-ctrl-bit19: A2I_CTRL %08x -> %08x (wrote 000a0001), I2A_CTRL %08x -> %08x (wrote 000a0001)\n",
		  a2i_before, a2i_after, i2a_before, i2a_after);
}

static void ane_rtclient_apply_dart_single_stream(struct ane_rtclient *ane)
{
	static const struct {
		u64 base;
		const char *name;
	} darts[3] = {
		{ 0x285800000ull, "inst0-LLT" },
		{ 0x285810000ull, "inst1-BRD" },
		{ 0x285820000ull, "inst2-BWR" },
	};
	unsigned int di;

	for (di = 0; di < 3; di++) {
		void __iomem *d = ioremap_np(darts[di].base, 0x2000);
		u32 en_before, prot_before;
		u32 en_after, prot_after, tcr_after, ttbr_after;
		int w;

		if (!d) {
			dev_emerg(ane->dev,
				  "BOOT-PHASE dart-single-stream %s: ioremap FAILED\n",
				  darts[di].name);
			continue;
		}

		en_before = readl(d + 0xc00);
		prot_before = readl(d + 0x200);

		/* Disable streams 1..255 via DISABLE_STREAMS (0xc20..0xc3c):
		 * stream 0 kept enabled, streams 1..31 disabled by ~1U,
		 * streams 32..255 disabled by U32_MAX in words 1..7. */
		writel(~1U, d + 0xc20);
		for (w = 1; w < 8; w++)
			writel(U32_MAX, d + 0xc20 + 4 * w);

		/* Ensure stream 0 is enabled in ENABLE_STREAMS (0xc00) */
		writel(1U, d + 0xc00);

		/* On dart0 (inst0-LLT), macOS working state reads PROTECT = 0x6
		 * (LOCK_REG_4xx | _BIT2; TCR/TTBR unlocked). dart1 and dart2
		 * have PROTECT = 0. */
		if (di == 0)
			writel(0x6U, d + 0x200);

		mb();
		en_after = readl(d + 0xc00);
		prot_after = readl(d + 0x200);
		tcr_after = readl(d + 0x1000);
		ttbr_after = readl(d + 0x1400);

		dev_emerg(ane->dev,
			  "BOOT-PHASE dart-single-stream %s: ENABLE %08x -> %08x, PROTECT %08x -> %08x, TCR0=%08x, TTBR0=%08x\n",
			  darts[di].name,
			  en_before, en_after,
			  prot_before, prot_after,
			  tcr_after, ttbr_after);

		iounmap(d);
	}
}

/*
 * dart-ane0 DAPF: the filter on the ANE's physical (bypass-stream) MMIO
 * accesses. XNU programs it from the ADT property dapf-instance-0; m1n1
 * programs DAPF only for aop/mtp/pmp/isp and ANE tunables only on T8103,
 * so on T6021 nothing opens these windows for the ANE firmware. The first
 * window is the ANE pmgr ps block (ane_sys_mpm..set4). Values are the
 * J414cAP ADT entries (52-byte t8110 form), written in m1n1
 * dapf_init_t8110a register order: r4, start, end, r0 = r0h << 4 | r0l,
 * r20.
 */
static void ane_rtclient_apply_dapf(struct ane_rtclient *ane)
{
	static const struct {
		u64 start;
		u64 end;
	} win[] = {
		{ 0x28e084000ull, 0x28e084033ull },
		{ 0x28e080260ull, 0x28e080263ull },
		{ 0x38545c000ull, 0x38545c003ull },
		{ 0x406468000ull, 0x406468003ull },
		{ 0x228545c000ull, 0x228545c003ull },
	};
	void __iomem *d = ioremap_np(0x285804000ull, 0x4000);
	unsigned int i;

	if (!d) {
		dev_emerg(ane->dev, "BOOT-PHASE dapf: ioremap FAILED\n");
		return;
	}

	for (i = 0; i < ARRAY_SIZE(win); i++) {
		void __iomem *e = d + i * 0x40;
		u32 r0 = readl(e), r4 = readl(e + 0x04), r20 = readl(e + 0x20);
		u64 start = readq(e + 0x08), end = readq(e + 0x10);

		writel(0, e + 0x04);
		writeq(win[i].start, e + 0x08);
		writeq(win[i].end, e + 0x10);
		writel(0x31, e + 0x00);
		writel(0x1, e + 0x20);
		mb();
		dev_emerg(ane->dev,
			  "BOOT-PHASE dapf[%u]: r0 %08x -> %08x, r4 %08x -> %08x, start %llx -> %llx, end %llx -> %llx, r20 %08x -> %08x\n",
			  i, r0, readl(e), r4, readl(e + 0x04),
			  start, readq(e + 0x08), end, readq(e + 0x10),
			  r20, readl(e + 0x20));
	}
	dev_emerg(ane->dev, "BOOT-PHASE dapf[%zu] (unused): r0 %08x start %llx end %llx\n",
		  ARRAY_SIZE(win), readl(d + ARRAY_SIZE(win) * 0x40),
		  readq(d + ARRAY_SIZE(win) * 0x40 + 0x08),
		  readq(d + ARRAY_SIZE(win) * 0x40 + 0x10));
	iounmap(d);
}

static void ane_rtclient_apply_core1_run(struct ane_rtclient *ane)
{
	u32 before, after;

	before = readl(ane->engine + 0x1400444);
	writel(0x10, ane->engine + 0x1400444);
	mb();
	after = readl(ane->engine + 0x1400444);
	dev_emerg(ane->dev,
		  "BOOT-PHASE core1-run: +0x1400444 %08x -> %08x (wrote 0x10)\n",
		  before, after);
}

static void ane_rtclient_apply_wrapper_b80_unmask(struct ane_rtclient *ane)
{
	static const u32 offs[] = {
		0x1400b80, 0x1400b84, 0x1400b88, 0x1400b8c,
		0x1400b90, 0x1400b94, 0x1400bfc
	};
	unsigned int i;

	for (i = 0; i < ARRAY_SIZE(offs); i++) {
		u32 before = readl(ane->engine + offs[i]);
		writel(U32_MAX, ane->engine + offs[i]);
		mb();
		dev_emerg(ane->dev,
			  "BOOT-PHASE wrapper-b80 +%x: %08x -> %08x (wrote ffffffff)\n",
			  offs[i], before, readl(ane->engine + offs[i]));
	}
}

/*
 * Read-only snapshot of the engine words that differ between macOS's
 * working state and anything Linux writes (ane-linux-experiments receipt
 * 2026-09-25-macos-ane-engine-dump, wrapper map). Logged before and after
 * the CPU release so one run yields the Linux side of that diff. The list
 * holds no pop-on-read word (+0x1400818/81c/820, +0x1408810/818/830/838)
 * and nothing in CoreSight.
 */
static void ane_rtclient_log_wrapper(struct ane_rtclient *ane, const char *tag)
{
	static const u32 words[] = {
		0x1400000, 0x1400008, 0x1400040, 0x1400044, 0x1400048,
		0x1400444,
		0x1400a00, 0x1400a04, 0x1400a08, 0x1400a0c, 0x1400a10, 0x1400a14,
		0x1400b80, 0x1400b84, 0x1400b88, 0x1400b8c, 0x1400b90, 0x1400b94,
		0x1400bfc, 0x1401008,
		0x1404110, 0x1404114, 0x1408110, 0x1408114, 0x140c110, 0x1410110,
		0x1840048, 0x184004c, 0x1840050, 0x1840054, 0x1840058, 0x184005c,
		0x1840060, 0x1840064, 0x1840068, 0x184006c,
	};
	unsigned int i;

	for (i = 0; i < ARRAY_SIZE(words); i++)
		dev_emerg(ane->dev, "WRAPPER %s +%#09x = %08x\n", tag, words[i],
			  readl(ane->engine + words[i]));
}


static int ane_rtclient_fwbuf_audit(struct ane_t6021 *a, const char *tag)
{
	const u64 *pt;
	unsigned int i, nz = 0;
	u32 vm0 = 0;

	if (ane_t6021_fw_alias_is_reserved()) {
		void __iomem *window = ioremap_np(0x1000141c000ull, 0x8000);
		u64 first = 0, second = 0;

		if (!window) {
			dev_err(a->dev, "RESERVED-PT %s mapping failed\n", tag);
			return -ENOMEM;
		}
		for (i = 0; i < 0x8000 / 8; i++) {
			u64 value = readl(window + i * 8);

			value |= (u64)readl(window + i * 8 + 4) << 32;
			if (i == 0)
				first = value;
			if (i == 1)
				second = value;
			if (value) {
				nz++;
				dev_emerg(a->dev, "RESERVED-PT %s +%#x=%016llx\n",
					  tag, i * 8, value);
			}
		}
		iounmap(window);
		dev_emerg(a->dev,
			  "RESERVED-PT %s first=%016llx second=%016llx nonzero=%u/4096\n",
			  tag, first, second, nz);
		window = ioremap_np(0x10001836000ull, 0x1000);
		if (!window) {
			dev_err(a->dev, "RESERVED-C %s mapping failed\n", tag);
			return -ENOMEM;
		}
		for (i = 0x490; i < 0xfd8; i += 8) {
			u64 value;

			if (!(i >= 0x490 && i <= 0x4a8) && i != 0x4e0 &&
			    !(i >= 0xb60 && i <= 0xbc0) && !(i >= 0xa20 && i < 0xa38) &&
			    !(i >= 0xd50 && i < 0xd90) && i < 0xe10)
				continue;
			value = readl(window + i);
			value |= (u64)readl(window + i + 4) << 32;
			dev_emerg(a->dev, "RESERVED-C %s vm=%#x value=%016llx\n",
				  tag, 0x4fa000 + i, value);
		}
		{
			u64 frame = readq(window + 0xbb8);

			iounmap(window);
			if (frame >= 0xc4000 && frame <= 0x4fc000 - 0x340 && !(frame & 7)) {
				window = ioremap_np(0x10001400000ull + frame - 0xc4000, 0x340);
				if (!window)
					return -ENOMEM;
				for (i = 0; i < 0x340; i += 8)
					dev_emerg(a->dev, "RESERVED-FRAME %s vm=%#llx value=%016llx\n",
						  tag, frame + i, readq(window + i));
				iounmap(window);
			} else if (frame >= 0x20004fc000ull &&
				   frame < 0x2000000000ull + a->fw_size &&
				   a->fw_size - (frame - 0x2000000000ull) >= 0x340 &&
				   !(frame & 7) && a->fw_buf) {
				u64 offset = frame - 0x2000000000ull;
				const u64 *saved = a->fw_buf + offset;

				dma_rmb();
				for (i = 0; i < 0x340 / sizeof(*saved); i++)
					dev_emerg(a->dev,
						  "OWNED-CONTEXT %s va=%#llx offset=%#llx value=%016llx\n",
						  tag, frame + i * sizeof(*saved),
						  offset + i * sizeof(*saved), READ_ONCE(saved[i]));
			}
		}
		window = ioremap_np(0x10001414000ull, 0x3000);
		if (!window) {
			dev_err(a->dev, "RESERVED-STACK %s mapping failed\n", tag);
			return -ENOMEM;
		}
		nz = 0;
		for (i = 0; i < 0x3000; i += 4) {
			u32 value = readl(window + i);

			if (value != ((i & 4) ? 0x4b434154 : 0x534b5452)) {
				nz++;
				dev_emerg(a->dev, "RESERVED-STACK %s vm=%#x value=%08x\n",
					  tag, 0xd8000 + i, value);
			}
		}
		iounmap(window);
		dev_emerg(a->dev, "RESERVED-STACK %s nonpattern=%u/3072\n", tag, nz);
		window = ioremap_np(0x10001400000ull + 0x4a84e8 - 0xc4000, 0x50000);
		if (!window)
			return -ENOMEM;
		nz = 0;
		for (i = 0; i < 0x2000; i++) {
			u64 link = readq(window + i * 0x28 + 0x18);

			if (link)
				nz++;
			if (i < 4 || i >= 0x1ffc || (i % 0x100) == 0)
				dev_emerg(a->dev, "RESERVED-NODES %s node=%u link=%016llx\n", tag, i, link);
		}
		iounmap(window);
		dev_emerg(a->dev, "RESERVED-NODES %s nonzero-links=%u/8192\n", tag, nz);
		window = ioremap_np(0x10001400000ull + 0x4f8500 - 0xc4000, 0x300);
		if (!window)
			return -ENOMEM;
		for (i = 0; i < 0x300; i += 8)
			dev_emerg(a->dev, "RESERVED-APP %s vm=%#x value=%016llx\n",
				  tag, 0x4f8500 + i, readq(window + i));
		iounmap(window);
		/* env-relative ctor-boundary rows (Main, 2026-09-27): the
		 * CPlatformEnvironment instance is a static-DATA object
		 * (live-verified VM 0xc95f8), so env+0x278 (CSharedMemory
		 * instance, stored at 6d10 right after ctor1 returns) vs
		 * env+0x290 (CDebugAgent instance, stored at 6d64 right
		 * after ctor2 returns) separates ctor1-return from
		 * ctor2-return. env+0x298 = the 0x1b3d4440 ctor constant
		 * (683c..6844) as the translation validator. Fail-closed
		 * DATA-window bounds; same non-posted mapping style; no
		 * /dev/mem. */
		{
			u64 env = 0;
			void __iomem *w = ioremap_np(0x10001400000ull +
						     0x4f8528 - 0xc4000, 8);

			if (w) {
				env = readq(w);
				iounmap(w);
			}
			if (env >= 0xc4000 && env + 0x2a8 <= 0x4fc000) {
				w = ioremap_np(0x10001400000ull + env - 0xc4000,
					       0x2a8);
				if (!w)
					return -ENOMEM;
				dev_emerg(a->dev,
					  "RESERVED-ENV %s vm=%#llx sm278=%016llx dbg290=%016llx const298=%016llx\n",
					  tag, env, readq(w + 0x278),
					  readq(w + 0x290), readq(w + 0x298));
				iounmap(w);
			} else {
				dev_emerg(a->dev,
					  "RESERVED-ENV %s env=%016llx out-of-window — refused\n",
					  tag, env);
			}
		}
		return 0;
	}
	if (!a->fw_buf)
		return -EINVAL;
	memcpy(&vm0, a->fw_buf, 4);
	pt = (const u64 *)(a->fw_buf + 0xe0000);
	for (i = 0; i < 0x8000 / 8; i++)
		if (pt[i])
			nz++;
	dev_emerg(a->dev,
		  "BUFAUDIT %s vm0=%08x patch=%*phN pthead=%016llx pt_nonzero=%u/4096\n",
		  tag, vm0, 32, a->fw_buf + 0x204, pt[0], nz);
	return 0;
}

/*
 * Fenced Linux-context firmware start (fw_start=1). Evidence chain:
 *  - iBoot latches ANE RVBAR = entry | 1 (live reads 0x10000000001:
 *    bit0 valid, entry bits = dart-ane0 vm-base 0x10000000000; ADT
 *    "pre-loaded" = 1). The kext law (ANE_Init, tbnz-skip) and this
 *    latch mean the driver NEVER writes RVBAR on this box.
 *  - Starting the CPU = CPU_CONTROL 0 -> 0x10 (RUN) — exactly what
 *    m1n1 does (ASC.boot(): RUN=1, no RVBAR anywhere) and what the
 *    kext does after its RVBAR skip. The open discriminator is
 *    whether the ASC fetch at the latched entry translates through
 *    dart-ane0 (mode bits 55/48 absent from the iBoot latch); with
 *    the selene alias mapped at the entry (fwload) a READY on
 *    SCRATCH7 proves translation; a dart translation fault names the
 *    stream; silence parks the core. Every outcome is bounded.
 * The sequence itself is the contract-pinned core in
 * ane_t6021_boot.h (ane_t6021_boot_run), exercised here through the
 * kernel io backend in ane_t6021_boot.c: W8 grant tunables, scratch
 * clear + stale-pulse, RVBAR skip-or-fold, RUN, poll A (READY
 * 0x08042006, <=1000 x 1 ms), publish (pinned pool sources) + wake,
 * poll B (DONE). Table block skipped (mode 2, authorized
 * diagnostic). No ps@2e0 write anywhere; no power_off/power_on
 * retry on timeout.
 */
#include "ane_t6021_dart_observer.h"

static int ane_rtclient_fw_start(struct ane_rtclient *ane)
{
	struct device *dev = ane->dev;
	struct ane_t6021 *a;
	u32 cpu_status;
	int ret;

	if (!ane_t6021_fwload_requested()) {
		dev_err(dev, "fw_start: requires fw_load=1 (no staged firmware)\n");
		return -EINVAL;
	}
	if (ane_t6021_fw_diag_requested()) {
		/* Marker mode (Main 2026-09-26): staged-copy execution
		 * probe. The VM 0x204 patch is meaningful ONLY when the
		 * staged copy is what the ASC executes; the options
		 * guard in the legacy drv.c does not run on this
		 * module, so the invariants are enforced here. */
		if (ane_t6021_fw_alias_is_reserved()) {
			dev_err(dev,
				"marker: fw_alias_reserved=1 maps the reserved windows — the patched staged copy would not execute; refusing (run with fw_alias_reserved=0)\n");
			return -EINVAL;
		}
		if (ane_t6021_fw_stamp_requested()) {
			dev_err(dev,
				"marker: fw_load_stamp_base co-patch refused\n");
			return -EINVAL;
		}
		if (fw_start_rtb_mode) {
			dev_err(dev,
				"marker: rtb_mode proceeds into the RTKit handshake; refusing\n");
			return -EINVAL;
		}
		dev_warn(dev,
			 "MARKER mode: staged copy VM 0x204 patched (SCRATCH7 <- 0x4d325431 + self-loop); existing fw_start staging + safe release reused; bounded SCRATCH7 report follows; state HELD until reboot\n");
	}
	if (!device_iommu_mapped(dev)) {
		dev_err(dev,
			"fw_start: device not IOMMU-mapped — a staged DVA/entry alias would be untranslated; refusing\n");
		return -EINVAL;
	}

	a = devm_kzalloc(dev, sizeof(*a), GFP_KERNEL);
	if (!a)
		return -ENOMEM;
	a->dev = dev;
	a->base[ANE_T6021_REG_ENGINE] = ane->engine;
	a->irq = -1;
	a->power_gated = true;	/* the eight-island G1 gate passed above */
	ane->fw = a;

	/* Stage selene + alias it at the latched RVBAR entry
	 * (request_firmware + sha-pin + exact-image validation +
	 * per-page iommu_map with roundtrip verification). */
	dev_emerg(dev, "BOOT-PHASE fwload stage+alias begin\n");
	ret = ane_t6021_fwload_probe(a);
	if (ret) {
		dev_err_probe(dev, ret, "fw_start: staging failed\n");
		ane->fw = NULL;
		return ret;
	}
	dev_emerg(dev, "BOOT-PHASE fwload stage+alias done (fw_iova=%pad)\n",
		  &a->fw_iova);

	if (!ane_t6021_rvbar_entry_ok(a->fw_iova)) {
		dev_err(dev,
			"fw_start: staged iova %pad sets bits the entry fold drops — refusing\n",
			&a->fw_iova);
		ane_t6021_fwload_remove(a);
		ane->fw = NULL;
		return -EINVAL;
	}

	if (fw_start_state_report) {
		/* Zero-write observability run: reads only, then a CLEAN
		 * unwind (fwload removed, module unpinned, insmod fails
		 * with -ECANCELED). */
		u64 rv = readq(ane->engine + ANE_ASC_RVBAR);
		int s;

		ane_rtclient_dart_observe(dev);
		/* power-dart-fwload preflight item 2/§2.2: dart-ane0
		 * instances 0/1/2 state — translate on, no bypass, TTBR
		 * valid, stream-0 enabled. Must run HERE: dart1/2 sit on
		 * the ane_cpu domain, only powered while genpd holds. */
		{
			static const struct {
				u64 base;
				const char *name;
			} darts[3] = {
				{ 0x285800000ull, "inst0-LLT" },
				{ 0x285810000ull, "inst1-BRD" },
				{ 0x285820000ull, "inst2-BWR" },
			};
			unsigned int di;

			for (di = 0; di < 3; di++) {
				void __iomem *d = ioremap_np(darts[di].base,
							     0x2000);

				if (!d) {
					dev_emerg(dev,
						  "DART %s: ioremap FAILED\n",
						  darts[di].name);
					continue;
				}
				dev_emerg(dev,
					  "DART %s: TCR=%08x TTBR=%08x ENABLE=%08x PROTECT=%08x %s%s\n",
					  darts[di].name,
					  readl(d + 0x1000),
					  readl(d + 0x1400),
					  readl(d + 0xc00),
					  readl(d + 0x200),
					  (readl(d + 0x1000) & BIT(1)) ?
						"BYPASS-DART!" : "translate",
					  (readl(d + 0x1400) & BIT(0)) ?
						"" : " TTBR-INVALID!");
				iounmap(d);
			}
		}

		dev_emerg(dev,
			  "BOOT-REPORT rvbar=%016llx cpu_status=%08x scratch=%08x %08x %08x %08x %08x %08x %08x %08x a2i=%08x i2a=%08x\n",
			  rv, readl(ane->engine + ANE_ASC_CPU_STATUS),
			  readl(ane->engine + ANE_MBI_SCRATCH0 + 4 * 0),
			  readl(ane->engine + ANE_MBI_SCRATCH0 + 4 * 1),
			  readl(ane->engine + ANE_MBI_SCRATCH0 + 4 * 2),
			  readl(ane->engine + ANE_MBI_SCRATCH0 + 4 * 3),
			  readl(ane->engine + ANE_MBI_SCRATCH0 + 4 * 4),
			  readl(ane->engine + ANE_MBI_SCRATCH0 + 4 * 5),
			  readl(ane->engine + ANE_MBI_SCRATCH0 + 4 * 6),
			  readl(ane->engine + ANE_MBI_SCRATCH0 + 4 * 7),
			  readl(ane->engine + ANE_ASC_MBOX_A2I_CTRL),
			  readl(ane->engine + ANE_ASC_MBOX_I2A_CTRL));
		ane_rtclient_log_wrapper(ane, "state-report");
		for (s = 0; s < 30; s++)
			msleep(10);	/* let the report hit every sink */
		ane_t6021_fwload_remove(a);
		ane->fw = NULL;
		return -ECANCELED;
	}

	if (fw_start_venc_gates) {
		/* Zero-engine-write precondition: VENC rails before the
		 * sequence (kext provider order). On failure: abort
		 * BEFORE any engine write, clean unwind. */
		int vg = ane_rtclient_venc_gates(dev);

		if (vg) {
			dev_emerg(dev,
				  "BOOT-PHASE venc-gates FAILED (%pe) — refusing sequence\n",
				  ERR_PTR(vg));
			ane_t6021_fwload_remove(a);
			ane->fw = NULL;
			return vg;
		}
		dev_emerg(dev, "BOOT-PHASE venc-gates raised\n");
	}
	if (patch_timer_freq) {
		int pr = ane_rtclient_patch_timer_freq(ane, patch_timer_freq);

		if (pr) {
			dev_emerg(dev,
				  "BOOT-PHASE timer-freq FAILED (%pe) — refusing CPU release\n",
				  ERR_PTR(pr));
			ane_t6021_fwload_remove(a);
			ane->fw = NULL;
			return pr;
		}
	}

	if (fw_start_mpm_off) {
		int pf = ane_rtclient_ps_macos_form(ane);

		if (pf) {
			dev_emerg(dev,
				  "BOOT-PHASE ps-form FAILED (%pe) — refusing sequence\n",
				  ERR_PTR(pf));
			ane_t6021_fwload_remove(a);
			ane->fw = NULL;
			return pf;
		}
		dev_emerg(dev, "BOOT-PHASE ps-form: ane_sys_mpm off, macOS form\n");
	}

	if (fw_start_dart_single_stream)
		ane_rtclient_apply_dart_single_stream(ane);

	if (fw_start_mbox_ctrl_bit19)
		ane_rtclient_apply_mbox_ctrl_bit19(ane);

	if (fw_start_core1_run)
		ane_rtclient_apply_core1_run(ane);

	if (fw_start_wrapper_b80_unmask)
		ane_rtclient_apply_wrapper_b80_unmask(ane);

	if (fw_start_dapf)
		ane_rtclient_apply_dapf(ane);

	ane_rtclient_log_wrapper(ane, "pre-release");

	ret = ane_rtclient_fwbuf_audit(a, "PRE");
	if (ret) {
		ane_t6021_fwload_remove(a);
		ane->fw = NULL;
		return ret;
	}

	ret = ane_t6021_boot_start(a, fw_start_stop_after, fw_start_table_mode,
				 fw_start_rtb_mode);
	if (ret == -ENODATA || ret == -EAGAIN || ret == -EBUSY ||
	    ret == -ECANCELED) {
		/* Refused/stopped before any CPU start: normal unwind is
		 * safe (-ECANCELED = bisect stop, state clean). */
		ane_t6021_fwload_remove(a);
		ane->fw = NULL;
		return ret;
	}

	/* From here a CPU may be running: HELD. No unwind, ever. */
	ane->held = true;
	cpu_status = readl(ane->engine + ANE_ASC_CPU_STATUS);
	dev_emerg(dev,
		  "BOOT-PHASE sequence returned %pe (cpu_started=%u fw_alive=%u booted=%u) CPU_STATUS=0x%x\n",
		  ERR_PTR(ret), a->cpu_started, a->fw_alive, a->booted,
		  cpu_status);
	ane_rtclient_log_wrapper(ane, "post-release");

	ane_rtclient_fwbuf_audit(a, "POST");

	/* Boot-PT / marker readback (13.5 boot-PT window at staged offset
	 * 0xe0000; M2StartupRecovery decode). Meaningful only when the
	 * staged copy is what executes (fw_alias_reserved=0):
	 *  - normal run: nonzero descriptors after a timeout mean the fw
	 *    reached the bootstrap PT construction;
	 *  - marker mode (fw_diag_marker=1): the FIRST qword is the marker
	 *    store (0x000000004d325431) — the execution proof itself;
	 *    remaining entries staying zero is EXPECTED (the marker
	 *    self-loops before any PT build).
	 * Host-side read of the owned coherent staging buffer — no extra
	 * hardware access. */
	if (a->fw_buf && !ane_t6021_fw_alias_is_reserved()) {
		const u64 *tt = a->fw_buf + 0xe0000;
		unsigned int n, nonzero = 0, count = 0x8000 / 8;

		for (n = 0; n < count; n++)
			if (tt[n])
				nonzero++;
		dev_emerg(dev,
			  "FW-PT region 0xe0000: first=%016llx second=%016llx nonzero=%u/%u\n",
			  tt[0], tt[1], nonzero, count);
		if (ane_t6021_fw_diag_requested())
			dev_emerg(dev,
				  "MARKER-BUFFER first qword = %016llx (marker word %08x at offset 0)%s\n",
				  tt[0], ANE_T6021_DIAG_MARKER_WORD,
				  tt[0] == 0x4d325431 ?
				  " — MARKER PRESENT: ASC fetched and executed" :
				  " — MARKER ABSENT");
	}

	if (fw_start_stop_after) {
		/* Bisect stop or poll-A timeout reached the HELD state:
		 * never continue into the handshake — publish/wake were
		 * withheld, so the fw HELLO cannot come. */
		dev_emerg(dev,
			  "BOOT-PHASE bisect stop (stop_after=%d r=%pe): binding fenced-HELD; reboot reclaims\n",
			  fw_start_stop_after, ERR_PTR(ret));
		return 0;
	}

	if (!a->fw_alive && !fw_start_rtb_mode) {
		/* Poll A timeout: RUN released, no READY. State held, module
		 * pinned, RTKit handshake skipped. CAUSE NOT LOCALIZED: a
		 * missing READY does not distinguish fetch failure from a
		 * RAM/MMIO write that did not land (Main 2026-09-27) — do
		 * not read this message as a fetch verdict. */
		dev_err(dev,
			"fw_start: poll A timeout, no READY — cause not localized; HELD until reboot, RTKit handshake skipped\n");
		return 0;	/* bind fenced */
	}

	if (fw_start_rtb_mode)
		dev_emerg(dev,
			  "BOOT-PHASE RTBuddy mode: READY not required — proceeding to RTKit handshake (HELLO-gated, bounded by hello_wait_ms=%u)\n",
			  hello_wait_ms);

	/* READY (and usually DONE) observed: the fetch DID translate.
	 * RTKit handshake follows in probe. */
	return 0;
}

static void ane_rtclient_unmap_engine(void *data)
{
	iounmap(((struct ane_rtclient *)data)->engine);
}

/*
 * restart_probe answers whether this box can restart the firmware
 * without a reboot. It stops the core (CPU_CONTROL <- 0, bounded wait for
 * STOPPED), cycles it through the framework ane_cpu reset (the domain
 * stays powered), and reports RVBAR and CPU_STATUS before and after: the
 * iBoot RVBAR latch must survive the reset, because kernel RVBAR writes
 * are fatal here. It never sets RUN again and keeps the module pin and
 * every DMA surface, so a reboot still reclaims. Raw ps writes froze the
 * box three times (W16 pass-2): write this only as the last act before a
 * planned reboot.
 */
static ssize_t restart_probe_store(struct device *dev,
				   struct device_attribute *attr,
				   const char *buf, size_t count)
{
	struct ane_rtclient *ane = dev_get_drvdata(dev);
	u64 rv0, rv1;
	u32 st0, st1, st2;
	int ret;

	if (!ane->cpu_rst)
		return -ENODEV;

	rv0 = readq(ane->engine + ANE_ASC_RVBAR);
	st0 = readl(ane->engine + ANE_ASC_CPU_STATUS);
	writel(0, ane->engine + ANE_ASC_CPU_CONTROL);
	ret = readl_poll_timeout(ane->engine + ANE_ASC_CPU_STATUS, st1,
				 st1 & ANE_ASC_CPU_STATUS_STOPPED, 10, 100000);
	dev_emerg(dev,
		  "RESTART-PROBE stop: CPU_STATUS %08x -> %08x (%pe), RVBAR %016llx\n",
		  st0, st1, ERR_PTR(ret), rv0);
	if (ret)
		return ret;

	ret = reset_control_assert(ane->cpu_rst);
	if (!ret) {
		fsleep(2);
		ret = reset_control_deassert(ane->cpu_rst);
	}
	rv1 = readq(ane->engine + ANE_ASC_RVBAR);
	st2 = readl(ane->engine + ANE_ASC_CPU_STATUS);
	dev_emerg(dev,
		  "RESTART-PROBE reset %pe: CPU_STATUS %08x, RVBAR %016llx -> %016llx (%s)\n",
		  ERR_PTR(ret), st2, rv0, rv1,
		  rv1 == rv0 ? "latch survives" : "latch LOST");
	return ret ?: count;
}
static DEVICE_ATTR_WO(restart_probe);

static struct attribute *ane_rtclient_attrs[] = {
	&dev_attr_restart_probe.attr,
	NULL,
};

static const struct attribute_group ane_rtclient_group = {
	.attrs = ane_rtclient_attrs,
};

/* Multi-domain genpd attach, ownership-correct and idempotent.
 *
 * The core attaches and raises a domain ONLY for single-domain nodes
 * (genpd_dev_pm_attach returns 0 with nothing attached otherwise);
 * here every index gets dev_pm_domain_attach_by_id + an RPM_ACTIVE
 * stateless link, the ane_t6021_drv.c pattern.
 *
 * Lifetime: the registry below is keyed by consumer device and owned
 * for the module's lifetime — NOT devm — so -EPROBE_DEFER retries
 * reuse the same virtual devices/links instead of attaching new ones
 * per retry. An interrupted attach is resumed at the first missing
 * index. Retention contract: links and device refs are never
 * released by this driver, so no intentional subsequent power-down
 * exists. NOT an absolute no-off-write guarantee: attach_by_id
 * itself enables runtime PM and queues genpd power-off work before
 * returning the virtual device (pmdomain/core.c:3398), so the
 * attach window carries a bounded controlled-hardware risk; live
 * attempts require camera+USB recovery and the noCPU state-report.
 */
struct ane_rtclient_pd {
	struct list_head list;
	struct device *dev;
	struct device **pd_dev;
	struct device_link **pd_link;
	int count;
};
static LIST_HEAD(ane_rtclient_pd_list);
static DEFINE_MUTEX(ane_rtclient_pd_lock);
static bool ane_rtclient_pinned;

static void ane_rtclient_pd_free(struct ane_rtclient_pd *pd)
{
	list_del(&pd->list);
	kfree(pd->pd_dev);
	kfree(pd->pd_link);
	kfree(pd);
}

static int ane_rtclient_attach_genpd(struct ane_rtclient *ane)
{
	struct device *dev = ane->dev;
	struct ane_rtclient_pd *pd = NULL;
	int count, i, err = 0;

	count = of_count_phandle_with_args(dev->of_node, "power-domains",
					   "#power-domain-cells");
	if (count == -ENOENT)
		return 0; /* no list: inert node, the G1 gate governs */
	if (count < 0)
		return count;
	if (count <= 1)
		return 0; /* single domain: core attached and raised it */

	mutex_lock(&ane_rtclient_pd_lock);
	list_for_each_entry(pd, &ane_rtclient_pd_list, list)
		if (pd->dev == dev)
			goto found;

	pd = kzalloc(sizeof(*pd), GFP_KERNEL);
	if (!pd) {
		err = -ENOMEM;
		goto out;
	}
	INIT_LIST_HEAD(&pd->list); /* safe pd_free even before list_add */
	pd->dev = dev;
	pd->pd_dev = kcalloc(count, sizeof(*pd->pd_dev), GFP_KERNEL);
	pd->pd_link = kcalloc(count, sizeof(*pd->pd_link), GFP_KERNEL);
	if (!pd->pd_dev || !pd->pd_link) {
		ane_rtclient_pd_free(pd);
		pd = NULL;
		err = -ENOMEM;
		goto out;
	}
	list_add_tail(&pd->list, &ane_rtclient_pd_list);

found:
	for (i = pd->count; i < count; i++) {
		/* A slot may hold a virtual device whose link add failed
		 * on an earlier retry: reuse it instead of attaching a
		 * fresh one. */
		if (!pd->pd_dev[i]) {
			pd->pd_dev[i] = dev_pm_domain_attach_by_id(dev, i);
			/* attach_by_id can also return NULL
			 * (pmdomain/core.c). */
			if (IS_ERR_OR_NULL(pd->pd_dev[i])) {
				err = IS_ERR(pd->pd_dev[i]) ?
					      PTR_ERR(pd->pd_dev[i]) : -ENODEV;
				pd->pd_dev[i] = NULL;
				goto out;
			}
		}

		if (!pd->pd_link[i]) {
			/* Once-only permanent pin before the first raised
			 * link: after a power mutation this driver must
			 * not unload (rmmod -EBUSY); reboot reclaims. */
			if (!ane_rtclient_pinned) {
				if (!try_module_get(THIS_MODULE)) {
					err = -ENODEV;
					goto out;
				}
				ane_rtclient_pinned = true;
			}
			pd->pd_link[i] =
				device_link_add(dev, pd->pd_dev[i],
						DL_FLAG_STATELESS |
						DL_FLAG_PM_RUNTIME |
						DL_FLAG_RPM_ACTIVE);
			if (!pd->pd_link[i]) {
				/* Keep the virtual device in its slot for
				 * the next retry; never put_device here —
				 * the attached state must stay tracked and
				 * owned. */
				err = -EINVAL;
				goto out;
			}
		}
		pd->count = i + 1;
	}

	dev_emerg(dev, "BOOT-PHASE genpd domains attached: %d\n", count);
out:
	mutex_unlock(&ane_rtclient_pd_lock);
	return err;
}

static int ane_rtclient_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct resource *res;
	struct ane_rtclient *ane;
	u32 cpu_status, ps_cpu;
	u64 rvbar;
	bool fw_alive;
	int ep;
	int ret;

	/* Early, BEFORE any allocation/power: shared probe-top predicate
	 * (drv.c:375 / rtclient 1366, refactored — fw_extra_ram bound +
	 * alignment + reserved-alias coupling + diag gate, all in one
	 * helper). The late check in ane_t6021_fwload.c alloc path stays
	 * as defense in depth. Anything path-restricted (legacy_only,
	 * rtbuddy mode, transport-only, etc.) is checked right after. */
	if (!ane_t6021_fwload_options_ok(false)) {
		dev_err(dev,
			"invalid laboratory firmware marker / RAM-grant options; refusing before power access\n");
		return -EINVAL;
	}

	/* Early, BEFORE any allocation/power: legacy_only must never be
	 * rejected after the CPU release, where a devm teardown could
	 * unwind domains under a running ASC (Main, 2026-09-27). */
	if (legacy_only && (!fw_start || fw_start_rtb_mode)) {
		dev_err(dev,
			"legacy_only=1 requires fw_start=1 and fw_start_rtb_mode=0\n");
		return -EINVAL;
	}
	if (legacy_query && (!legacy_only || !scratch3_ack)) {
		dev_err(dev, "legacy_query requires legacy_only=1 and scratch3_ack=1\n");
		return -EINVAL;
	}
	if (legacy_load && !legacy_query) {
		dev_err(dev, "legacy_load requires legacy_query=1\n");
		return -EINVAL;
	}
	if (legacy_resource && !legacy_query) {
		dev_err(dev, "legacy_resource requires legacy_query=1\n");
		return -EINVAL;
	}

	ane = devm_kzalloc(dev, sizeof(*ane), GFP_KERNEL);
	if (!ane)
		return -ENOMEM;
	ane->dev = dev;
	platform_set_drvdata(pdev, ane);
	INIT_DELAYED_WORK(&ane->poll_work, ane_rtclient_post_boot);

	res = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!res)
		return -ENODEV;
	/* "nonposted-mmio" (inherited from /soc) sets IORESOURCE_MEM_NONPOSTED;
	 * all ANE aperture access is non-posted (posted writel froze the box). */
	if (!(res->flags & IORESOURCE_MEM_NONPOSTED))
		dev_warn(dev, "engine window is not flagged non-posted; refusing\n");
	/* No exclusive request_mem_region: the ASC mailbox child device
	 * (0x285408000) lives inside this window and its region is
	 * already claimed in the iomem tree, so an exclusive request of
	 * the parent span would conflict with our own child. */
	ane->engine = ioremap_np(res->start, resource_size(res));
	if (!ane->engine)
		return -ENOMEM;
	ret = devm_add_action_or_reset(dev, ane_rtclient_unmap_engine, ane);
	if (ret)
		return ret;

	ane->cpu_rst = devm_reset_control_get_optional_exclusive(dev, NULL);
	if (IS_ERR(ane->cpu_rst))
		return dev_err_probe(dev, PTR_ERR(ane->cpu_rst),
				     "ane_cpu reset control\n");
	ret = devm_device_add_group(dev, &ane_rtclient_group);
	if (ret)
		return ret;

	/* Selene 13.5 channel setup loads ring DVA as u32 at VM 0x60b0. */
	ret = dma_set_mask_and_coherent(dev, DMA_BIT_MASK(32));
	if (ret)
		return ret;

	/* Power: the DT power-domain list. For multi-domain nodes the
	 * core attaches nothing (genpd_dev_pm_attach returns 0 without
	 * attaching), so attach_genpd raises every domain by id. On this
	 * box the always-on islands report off at boot and resume_and_get
	 * hangs the bind writer; when the islands already read on,
	 * fw_start_skip_genpd=1 skips the attach so nothing is raised. */
	if (!fw_start_skip_genpd) {
		ret = ane_rtclient_attach_genpd(ane);
		if (ret)
			return dev_err_probe(dev, ret,
					     "extra genpd attach\n");
	}
	pm_runtime_enable(dev);
	dev_emerg(dev, "BOOT-PHASE core genpd resume begin\n");
	if (fw_start_skip_genpd) {
		dev_emerg(dev, "BOOT-PHASE genpd raise SKIPPED (fw_start_skip_genpd=1)\n");
		ret = 0;
	} else {
		ret = pm_runtime_resume_and_get(dev);
	}
	if (ret)
		return dev_err_probe(dev, ret, "genpd raise failed\n");
	dev_emerg(dev, "BOOT-PHASE genpd raise done\n");

	/* G1 gate: ane_cpu ACTUAL must be 0xf before any further MMIO. */
	ane->pmgr = devm_of_iomap(dev, dev->of_node, 1, NULL);
	if (IS_ERR(ane->pmgr)) {
		ret = PTR_ERR(ane->pmgr);
		pm_runtime_put_sync_suspend(dev);
		pm_runtime_disable(dev);
		return dev_err_probe(dev, ret,
				     "pmgr window map failed; G1 gate cannot run\n");
	}
	ps_cpu = readl(ane->pmgr + ANE_RTCLIENT_PS_CPU_ACTUAL_OFF);
	dev_emerg(dev, "ane_cpu ACTUAL = 0x%x\n", ps_cpu);
	if (FIELD_GET(ANE_PS_ACTUAL, ps_cpu) != ANE_PS_ON) {
		pm_runtime_put_sync_suspend(dev);
		pm_runtime_disable(dev);
		return -EPROBE_DEFER;
	}

	/* CPU gate. This read is the first engine access and is
	 * read-clean proven (W10) with the islands up. Default
	 * (fw_start=0): refuse unless the firmware is already alive —
	 * kernel-context RVBAR programming is fatal / sticky-latched on
	 * this box (power-dart-fwload s23/s24), start belongs to a
	 * quiesce context. fw_start=1: run the fenced start below. */
	cpu_status = readl(ane->engine + ANE_ASC_CPU_STATUS);
	rvbar = readq(ane->engine + ANE_ASC_RVBAR);
	dev_emerg(dev,
		  "BOOT-PHASE engine reads ok: CPU_STATUS = 0x%x, RVBAR = %016llx (bit0=%u entry=%0llx)\n",
		  cpu_status, rvbar, (u32)(rvbar & 1),
		  (u64)(rvbar & ANE_T6021_RVBAR_ADDR_MASK));

	if (!(cpu_status & ANE_ASC_CPU_STATUS_RUNNING)) {
		if (!fw_start) {
			dev_err(dev,
				"ANE firmware not alive (CPU_STATUS 0x%x) — start it from a quiesce context (m1n1/iBoot), or retry with fw_start=1; this driver will not program RVBAR\n",
				cpu_status);
			pm_runtime_put_sync_suspend(dev);
			pm_runtime_disable(dev);
			return -EPROBE_DEFER;
		}
		ret = ane_rtclient_fw_start(ane);
		if (ret) {
			/* Unwind through err_pm_or_hold, not here: if the
			 * boot contract already released the CPU, a power
			 * teardown on this path would drop domains under a
			 * running ASC. */
			goto err_pm_or_hold;
		}
		if (ane_t6021_fw_diag_requested()) {
			/* Marker mode fences at probe UNCONDITIONALLY
			 * (Main 2026-09-26): the staged-copy self-loop is
			 * not firmware alive, and the CPU_STATUS RUNNING
			 * bit of a parked/released core must never open
			 * the RTKit path. Keep the module pin, genpd and
			 * every DMA surface; the BUFAUDIT/FW-PT marker
			 * word is the outcome of record. */
			dev_warn(dev,
				 "MARKER run complete — binding fenced-inert before any RTKit (CPU_STATUS bit not consulted)\n");
			return 0;
		}
		cpu_status = readl(ane->engine + ANE_ASC_CPU_STATUS);
		fw_alive = cpu_status & ANE_ASC_CPU_STATUS_RUNNING ||
			   (ane->fw && ane->fw->fw_alive);
		/* HELD from here on: a CPU we released may be running.
		 * genpd must never be dropped under it — bind fenced
		 * instead of unwinding power on any later failure. */
	} else {
		fw_alive = true;
	}

	if (!fw_alive && !fw_start_rtb_mode) {
		/* fw_start ran, CPU released, but no READY: bind fenced
		 * and inert (state HELD, module pinned by the boot
		 * path, genpd stays up, no RTKit). In RTBuddy mode this
		 * gate does not apply — READY is not the contract; the
		 * RTKit handshake below is HELLO-gated and bounded by
		 * hello_wait_ms. */
		dev_warn(dev,
			 "binding fenced-inert (no firmware%s; state HELD until reboot)\n",
			 ane_t6021_fw_diag_requested() ?
			 " — marker word in BUFAUDIT/FW-PT above" : "");
		return 0;
	}

	/* 13.5 legacy ChMan transport (legacy_only=1): the fw's post-DONE
	 * sequence — parent poll GPIO3==0x08042006 (6c80..6ca4), then
	 * CSharedMemory 20e78 / CDebugAgent 13604 / CIPSynchroReal 5b98,
	 * then the GPIO3 clear 6d84..6d98 — is driven only by the ACK.
	 * Every RTKit surface stays off so the generic mailbox/RTKit
	 * path cannot touch the ASC while the legacy sequence runs.
	 * Version contract: fwload already sha-pinned a9c4b771... (13.5
	 * 22G74) and would have refused staging otherwise.
	 * Invariant (validated at probe top): legacy_only implies
	 * fw_start && !fw_start_rtb_mode — no rejection past this point. */
	if (legacy_only) {
		dev_emerg(dev,
			  "LEGACY-ONLY transport (13.5 contract): RTKit surfaces excluded; validate chman, write ACK, observe\n");
		ane_rtclient_validate_chman(ane);
		if (ane->fw && ane->fw->booted && scratch3_ack && ane->chman_ok &&
		    ane_t6021_chman_host_init(ane->fw->boot_ipc,
					    ane->fw->boot_ipc_size,
					    ane->fw->boot_ipc_iova)) {
			dma_wmb();
			dev_info(dev, "chman: H2T slots initialized host-owned before ACK\n");
			dev_emerg(dev, "LEGACY P8 host ack: SCRATCH3 <- %08x\n",
				  ANE_T6021_BOOT_ACK);
			ane_rtclient_legacy_state(ane, "before-ack", false);
			if (hello_wait_ms && !ane->rtk) {
				ane->rtk = devm_apple_rtkit_init(dev, ane, NULL, 0,
								 &ane_rtclient_rtkit_ops);
				if (IS_ERR(ane->rtk)) {
					dev_err(dev, "LEGACY hello: rtkit init %pe\n",
						ane->rtk);
					ane->rtk = NULL;
				} else {
					schedule_delayed_work(&ane->poll_work,
							      msecs_to_jiffies(10));
				}
			}
			ane->legacy_ack_ns = ktime_get_ns();
			writel(ANE_T6021_BOOT_ACK,
			       ane->engine + ANE_MBI_SCRATCH0 + 4 * 3);
			if (ane->rtk) {
				int hello_ret;
				unsigned long hello_deadline;
				int hello_ep;

				dev_emerg(dev, "LEGACY hello: boot begin (%u ms)\n",
					  hello_wait_ms);
				hello_deadline = jiffies +
					msecs_to_jiffies(hello_wait_ms);
				do {
					hello_ret = apple_rtkit_boot(ane->rtk);
				} while (hello_ret == -ETIME &&
					 time_before(jiffies, hello_deadline));
				dev_emerg(dev,
					  "LEGACY hello: boot %pe running=%d crashed=%d\n",
					  ERR_PTR(hello_ret),
					  apple_rtkit_is_running(ane->rtk),
					  apple_rtkit_is_crashed(ane->rtk));
				if (!hello_ret) {
					dev_info(dev, "LEGACY hello endpoints:");
					for (hello_ep = 0; hello_ep < 0x100; hello_ep++)
						if (apple_rtkit_has_endpoint(ane->rtk,
									     hello_ep))
							pr_cont(" %#x", hello_ep);
					pr_cont("\n");
					ane->boot_done = true;
					if (start_app_eps)
						ane_rtclient_start_app_eps(ane);
					if (csne_ping)
						ane_rtclient_csne_ping(ane);
				} else {
					cancel_delayed_work_sync(&ane->poll_work);
				}
			}
			if (legacy_query) {
				int query_result = ane_rtclient_legacy_query(ane);

				dev_info(dev, "LEGACY CONFIG_GET result=%d (DMA remains held)\n", query_result);
				if (!query_result && legacy_load)
					dev_info(dev, "LEGACY primitive load result=%d (DMA remains held)\n",
						 ane_rtclient_legacy_arm_and_load(ane));
				if (!query_result && legacy_seq)
					dev_info(dev, "LEGACY sequence result=%d (DMA remains held)\n",
						 ane_rtclient_legacy_sequence(ane));
				if (ane->fw && ane->fw->boot_ipc) {
					unsigned int ri;

					for (ri = 0; ri < ANE_T6021_CHMAN_COUNT; ri++) {
						u64 *ring = ane->fw->boot_ipc +
							ane_t6021_chman_layout[ri].off;

						dev_info(dev,
							 "LEGACY ring %s head=%016llx %016llx %016llx\n",
							 ane_t6021_chman_layout[ri].name,
							 READ_ONCE(ring[0]), READ_ONCE(ring[1]),
							 READ_ONCE(ring[2]));
					}
				}
				if (ane->fw && ane->fw->boot_ipc && ane->legacy_allocated) {
					u64 *term = ane->fw->boot_ipc +
						ane_t6021_chman_layout[0].off;
					u64 want = READ_ONCE(term[0]) & ~3ULL;
					unsigned int bi;

					for (bi = 0; bi < ane->legacy_allocated; bi++) {
						const char *p = ane->legacy_buffers[bi].cpu;
						size_t n = ane->legacy_buffers[bi].size, at, run = 0;
						unsigned int lines = 0;

						if (!p || ane->legacy_buffers[bi].dma != want)
							continue;
						dev_info(dev, "LEGACY fwlog buf=%u dma=%pad bytes=%zu\n",
							 bi, &ane->legacy_buffers[bi].dma, n);
						for (at = 0; at < n && lines < 80; at++) {
							char c = READ_ONCE(p[at]);

							if (c >= 0x20 && c < 0x7f) {
								run++;
								continue;
							}
							if (run >= 6) {
								dev_info(dev, "LEGACY fwlog +%#zx %.*s\n",
									 at - run, (int)min_t(size_t, run, 200),
									 p + at - run);
								lines++;
							}
							run = 0;
						}
					}
				}
			}
		} else {
			dev_warn(dev,
				 "LEGACY ack withheld (booted=%u scratch3_ack=%u chman_ok=%u)\n",
				 ane->fw ? ane->fw->booted : 0, scratch3_ack, ane->chman_ok);
		}
		msleep(1000);
		ane_rtclient_legacy_state(ane, "before-audit", false);
		if (ane->fw)
			ane_rtclient_fwbuf_audit(ane->fw, "post-ack");
		ane_rtclient_legacy_state(ane, "after-audit", false);
		ane_rtclient_log_wrapper(ane, "legacy-post-ack");
		dev_emerg(dev,
			  "LEGACY transport armed; state HELD (pins kept, no RTKit). If SCRATCH3 readback still shows the ack, the fw did not reach the 6d84 clear\n");
		return 0;
	}

	ane->rtk = devm_apple_rtkit_init(dev, ane, NULL, 0,
					 &ane_rtclient_rtkit_ops);
	if (IS_ERR(ane->rtk)) {
		ret = PTR_ERR(ane->rtk);
		ane->rtk = NULL;
		ret = dev_err_probe(dev, ret, "apple_rtkit_init failed\n");
		goto err_pm_or_hold;
	}

	/* RX path: the recv irq (ADT raw 0x374) is primary; the worker is
	 * the poll fallback that drives RX while the handshake runs. Armed
	 * before the host ack below so the fw's HELLO is never missed. */
	schedule_delayed_work(&ane->poll_work, msecs_to_jiffies(10));

	if (ane->fw) {
		/* Kext order after DONE (InitializeRTBuddy 0x95ead04 ->
		 * 0x95eaee4): read the channel table, then host-ack. The
		 * fw spins on SCRATCH3 == 0x08042006 right after DONE
		 * (selene 0x7edc-0x7f10) and only then creates its
		 * endpoints and starts RTKit (HELLO). Without this write
		 * HELLO never comes. SCRATCH is the host-writable family
		 * the boot sequence already writes (W9). */
		ane_rtclient_validate_chman(ane);
		dev_info(dev,
			 "fw transport mode: %s (fw 0x42c8: rtbuddyFW = (SCRATCH6 == 0))\n",
			 fw_start_rtb_mode ?
			 "S1 wrote SCRATCH6=0 -> RTBuddy/RTKit-app-endpoint mode" :
			 "S1 wrote SCRATCH6=1 -> legacy ChMan/MBI mode");
		if ((ane->fw->booted || ane->fw->fw_alive) && scratch3_ack) {
			dev_emerg(dev,
				  "BOOT-PHASE P8 host ack: SCRATCH3 <- %08x (rtb=%u)\n",
				  ANE_T6021_BOOT_ACK, fw_start_rtb_mode);
			writel(ANE_T6021_BOOT_ACK,
			       ane->engine + ANE_MBI_SCRATCH0 + 4 * 3);
		} else {
			dev_warn(dev,
				 "BOOT-PHASE P8 host ack WITHHELD (booted=%u scratch3_ack=%u): ack is post-DONE per the 27.0 decode — the 13.5 fw order is UNVERIFIED\n",
				 ane->fw->booted, scratch3_ack);
		}
	}

	/* The handshake: the fw HELLOes on MGMT (v12), rtkit.c answers,
	 * EPMAP + system-endpoint STARTEP + IOP power ack follow, then
	 * boot() sets the AP power state ON. Each rtkit.c wait is 1 s;
	 * the fw reaches HELLO only after its ChMan DONE, so -ETIME is
	 * retried within hello_wait_ms. Anything else is final. */
	dev_emerg(dev, "BOOT-PHASE apple_rtkit_boot begin (bound %u ms)\n",
		  hello_wait_ms);
	{
		unsigned long deadline = jiffies + msecs_to_jiffies(hello_wait_ms);

		do {
			ret = apple_rtkit_boot(ane->rtk);
		} while (ret == -ETIME && time_before(jiffies, deadline));
	}
	if (ret) {
		dev_err(dev, "rtkit boot handshake failed: %pe (is_running=%d crashed=%d)\n",
			ERR_PTR(ret), apple_rtkit_is_running(ane->rtk),
			apple_rtkit_is_crashed(ane->rtk));
		cancel_delayed_work_sync(&ane->poll_work);
		goto err_pm_or_hold;
	}

	ane->boot_done = true;

	/* Endpoint bitmap the firmware advertised via EPMAP. Static
	 * prediction (selene endpoint table, vm 0xed0a0): 0 1 2 0x20. */
	dev_info(ane->dev, "rtkit RUNNING; fw-advertised endpoints:");
	for (ep = 0; ep < 0x100; ep++)
		if (apple_rtkit_has_endpoint(ane->rtk, ep))
			pr_cont(" %#x", ep);
	pr_cont("\n");

	if (start_app_eps)
		ane_rtclient_start_app_eps(ane);

	if (!ane->fw)
		ane_rtclient_validate_chman(ane);

	if (csne_ping)
		ane_rtclient_csne_ping(ane);

	if (!poll_rx)
		cancel_delayed_work_sync(&ane->poll_work);

	dev_info(dev,
		 "ANE RTKit client up: handshake complete (cmd_ep=%#x chman=%s)\n",
		 ane->cmd_ep, ane->chman_ok ? "validated" : "not validated");
	return 0;

err_pm_or_hold:
	if (ane->held) {
		/* A CPU we released is running: NEVER drop genpd under
		 * it. Bind fenced; reboot is the only reclamation. */
		dev_warn(dev,
			 "probe failed after CPU start (%pe) — binding fenced; power/rings/IRQ HELD until reboot\n",
			 ERR_PTR(ret));
		return 0;
	}
	pm_runtime_put_sync_suspend(dev);
	pm_runtime_disable(dev);
	return ret;
}

static void ane_rtclient_remove(struct platform_device *pdev)
{
	struct ane_rtclient *ane = platform_get_drvdata(pdev);

	cancel_delayed_work_sync(&ane->poll_work);

	if (ane->held) {
		/* Unreachable in practice: suppress_bind_attrs blocks
		 * unbind and the permanent module pin blocks rmmod once
		 * any domain was raised. If it ever runs, claim nothing —
		 * the core frees devm state after this callback; reboot
		 * reclaims the raised hardware state. */
		dev_warn(&pdev->dev,
			 "remove HELD (CPU started): no teardown — reboot reclaims\n");
		return;
	}

	if (ane->rtk)
		apple_rtkit_shutdown(ane->rtk);
	if (ane->ring)
		dma_free_coherent(&pdev->dev, ANE_RTCLIENT_RING_SIZE, ane->ring,
				  ane->ring_iova);
	pm_runtime_put_sync_suspend(&pdev->dev);
	pm_runtime_disable(&pdev->dev);
}

static const struct of_device_id ane_rtclient_of_match[] = {
	/* The stock DTB's ane0 node. The legacy H13-path ane_t6021.ko
	 * shares this compatible and must NOT be loaded on this box. */
	{ .compatible = "apple,t6021-ane" },
	{ }
};
MODULE_DEVICE_TABLE(of, ane_rtclient_of_match);

static struct platform_driver ane_rtclient_driver = {
	.driver = {
		.name = "ane_t6021_rtclient",
		.of_match_table = ane_rtclient_of_match,
		/* Reboot-only research driver: no manual bind/unbind. */
		.suppress_bind_attrs = true,
	},
	.probe = ane_rtclient_probe,
	.remove = ane_rtclient_remove,
};
module_platform_driver(ane_rtclient_driver);

MODULE_LICENSE("Dual MIT/GPL");
MODULE_DESCRIPTION("T6021 ANE RTKit client (mainline apple_rtkit)");
