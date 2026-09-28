// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* T6021 ANE transport core — MBI handshake (SCRATCH wake -> fw channel
 * table), capture of the fw->host message registers, MGMT decode for
 * received words, RTBuddy app-endpoint ring bookkeeping.
 *
 * W10 2026-09-19 CORRECTION to the paragraph that stood here ("the
 * h14g transport is NOT the m1n1 ASC mailbox ... the +0x1608114
 * analogy read SError-aborted jw14m2").  The ASC mailbox DOES exist
 * on this part, at ANE+0x1408000, and reads clean: a2i_control
 * 0x285408110 and i2a_control 0x285408114 both = 0x00020001
 * (ENABLE=1 EMPTY=1 FIFOCNT=0 WPTR=0 RPTR=0).  The aborting read was
 * +0x1608114 — the h16g base, i.e. the wrong address, not evidence of
 * absence; and the kext is silent about 0x1408xxx because the mailbox
 * belongs to the RTBuddy provider kext.  Both FIFO pointer pairs are
 * still at the origin, so nothing has ever crossed this mailbox, in
 * either direction, because the ASC CPU is STOPPED (CPU_CONTROL
 * 0x285400044 = 0, RVBAR entry 0).  The kext-evidenced sequence
 * (InitializeRTBuddy 0x…95e942c) is: hand a command buffer via
 * SCRATCH0/1 (+0x1840048/+0x184004c), write the wake word 0xf7fbdff9
 * to SCRATCH7 (+0x1840064), poll until the fw overwrites it with
 * 0x08042006 ("channel description table ready"), read the table base
 * back from SCRATCH0/1, then register each {type,bit,size,phys} entry
 * with the doorbell setter (write32(1 << bit) to +0x1844000).  The
 * SCRATCH handshake is the fw-sideload boot mode's init; in RTBuddy
 * mode it is SError-fatal to write and stays capture-only here.
 *
 * RTBuddy-mode TX (decoded 2026-09-19 from com.apple.driver.RTBuddy
 * 1.0.0 carved out of kernelcache.release.mac14j): K14 matches the
 * ANEEndpoint1..5 nubs, takes the gate from [svc+0x88] and calls
 * vtable+0x1e8 with the 48-bit MBI word {(ring cursor) [23:0],
 * (len) [47:24]} after memcpy'ing the command into the shared ring;
 * the gate ends in the AKF mailbox write — msg word to the a2i
 * register (+0x1850000) and write32(1 << ep) to the doorbell
 * (+0x1844000).  This driver implements exactly that sequence in
 * ane_t6021_csne_submit, fenced behind mbi_doorbell=1 (default off:
 * a wrong-bit ring on this surface is the machine-fatal class the
 * SCRATCH SError receipted 2026-09-19).
 */

#include <linux/bitmap.h>
#include <linux/dev_printk.h>
#include <linux/delay.h>
#include <linux/dma-mapping.h>
#include <linux/io.h>
#include <asm/memory.h>
#include <linux/interrupt.h>
#include <linux/iopoll.h>
#include <linux/jiffies.h>
#include <linux/minmax.h>

#include <asm/barrier.h>

#include "ane_t6021.h"

/* ---- MBI transport (capture-only; kext sites cited inline) ---- */

/* SCRATCH write history, reconciled (W15): the legacy ANE_Init
 * publication (dsb st at 0x95eaa90; low32→0x01840048, high32→
 * 0x0184004c; wake 0xf7fbdff9 → SCRATCH7 0x01840064) is kext-proven on
 * the OBSERVED provider path (AppleARMIODevice "ane" match, not
 * RTBuddyService), and W9 latched nonzero SCRATCH values behind the W8
 * grant — but a SCRATCH0 write SError-aborted CPU4 (0xbe000000) on the
 * 2026-09-19 no-grant boot, and the init structure the publication
 * names has unpinned consumer fields ([0x08], [0x10,0x38); selene fn
 * 0x71A4 read-set pending). The host therefore performs NO SCRATCH
 * write on this path: publication belongs to ane_t6021_boot.c once the
 * consumer constraints land. SCRATCH READS stay in the proven-safe
 * whitelist (first_resume dumps all eight). */

static void ane_mbi_msgregs_dump(struct ane_t6021 *ane, const char *when)
{
	void __iomem *eng = ane->base[ANE_T6021_REG_ENGINE];

	dev_info(ane->dev,
		 "MBI msgregs %s: tb=%08x_%08x a2i_rd=%08x a2i_wr=%08x (tb = +0x1170000 CNTVCT mirror, not a transport — W10)\n",
		 when,
		 readl(eng + ANE_MBI_MSG_I2A_HI),
		 readl(eng + ANE_MBI_MSG_I2A_LO),
		 readl(eng + ANE_MBI_MSG_A2I_RD),
		 readl(eng + ANE_MBI_MSG_A2I_WR));
}

/* fw->host message registers: capture-only read (kext reads the pair
 * at 0x…95ee6a8/0x…9605d20; no FIFO semantics pinned yet) */
static void ane_mbi_drain(struct ane_t6021 *ane)
{
	ane_mbi_msgregs_dump(ane, "drain");
}

void ane_t6021_rtkit_drain(struct ane_t6021 *ane)
{
	mutex_lock(&ane->mbox_lock);
	ane_mbi_drain(ane);
	mutex_unlock(&ane->mbox_lock);
}

/* ---- EP0 MGMT session (W6): the RTKit handshake that must sit in
 * front of ANY app-endpoint TX ----
 *
 * LIVE RESULT 2026-09-19 (W6, receipt
 * 2026-09-19-h14-w6-mgmt-session-serror.md): with the runbook green
 * and three silent watch seconds (i2a "ambient heartbeat", all words
 * type 0) — but see the W10 note below: that pair is a mirror of the
 * 24 MHz architectural counter, so "all words type 0" was structural
 * and the silence was total, not ambient — the
 * one-shot host opener "HELLO(host)" — 32-bit a2i halves + doorbell
 * 0x1 — SError'd CPU0 (0xbe000000) 25 us after the write pair.  Same
 * class/latency as the W5-live EP1 ring: candidate (a) (64-bit
 * writeq width) is DEAD.  The missing precondition is upstream of
 * protocol: fabric/fw write-grant or a still-unmapped transport for
 * the running-boot mode.  The session
 * code below stays as the prepared protocol half for the lane that
 * clears that wall.
 *
 * W9 2026-09-19 (receipt
 * 2026-09-19-h14-w9-hello-granted.md): the W8 grant (m1n1 static
 * tunables, led by base+0x0 <- 0x10) applied from userspace BEFORE
 * insmod did NOT clear the wall — it is PARTIAL.  The same boot
 * proved SCRATCH (+0x1840048) host writes accepted and LATCHING
 * nonzero values (0xa5a5a5a5/0x5a5a5a5a read back exact) 17 s before
 * the send, yet the MBI send class still aborted: seam
 * "MGMT TX HELLO(host): msg=00100000000c000b -> a2i(half) + doorbell
 * 0x1" then SError CPU0 0xbe000000 11 us in (W6: 25 us, no grant).
 * The aperture is therefore not one fabric gate: the grant unlocks
 * the SCRATCH/GPIO class, while a2i_wr (+0x1850000/4) and the
 * doorbell (+0x1844000) stay host-write-rejected with the grant live.
 * Candidates narrowed: a second, MBI-specific grant the 12 tunables
 * do not carry, or the running fw owning/locking its own send
 * surfaces.  No HELLO reply, and W10 explains why: there was never a
 * heartbeat and never a firmware.  The "type-0 heartbeat (hi=0x0b,
 * ~29 ticks/3 s)" is ANE+0x1170000/4 mirroring CNTVCT_EL0 — constant
 * 13-18 count absolute offset across 32 samples, 0.054 ppm drift —
 * plus a poll count.  The real receive register (i2a_control
 * 0x285408114) sat EMPTY through 600 polls over 30 s, and the ASC CPU
 * that would drive it reads RUNNING=0 STOPPED=1 with RUN never set.
 * The send class did not abort because the host spoke out of turn: it
 * aborted because +0x1850000/+0x1844000 are not the mailbox and no
 * IOP is running behind them.  Next lane: load fw, program RVBAR,
 * set CPU_CONTROL.RUN, then let the fw open the session on
 * OUTBOX0/1 (0x285408830/8) per the RTKit contract.
 *
 * W5-live proved the wall: the first EP1 ring SError'd the machine
 * (0xbe000000) because macOS never sends an EP1 command without the
 * RTBuddy management session (HELLO -> EPRollCall/PowerAck ->
 * SetupEndpoints -> STARTEP) in front of it.  This session replays
 * that handshake on EP0:
 *
 *   1. watch the fw->host message pair (+0x1170000/4, read-clean
 *     proven) for a MGMT word — type bits [59:52] nonzero.  W10:
 *     this discriminator can never fire, because that pair is the
 *     24 MHz counter and bits [59:52] of a counter below 2^52 are
 *     structurally zero (~6 years of uptime away).  The step is kept
 *     only to keep the historical log readable; the real receive
 *     poll is i2a_control EMPTY at ANE_ASC_MBOX_I2A_CTRL;
 *   2. answer HELLO (type 1) with HELLO_REPLY, versions clamped to
 *     the RTKit library range 11..12;
 *   3. if the fw stays silent, send ONE host HELLO — the W5-live
 *     receipt's follow-up item 2 names the EP0 MGMT exchange as the
 *     missing precondition and the assignment sanctions the host
 *     opener behind doorbell bit 0x1;
 *   4. echo EPMAP (type 8) replies per rtkit semantics (base +
 *     MORE/LAST bit), ACK IOP power state, and log every other MGMT
 *     word raw (EPRollCall/PowerAck decode on first sight);
 *   5. only after the fw has spoken on MGMT: announce the EP1
 *     surface (54-bit doorbell word) and STARTEP EP1.
 *
 * Every host send is two 32-bit a2i stores + the doorbell word: the
 * AKF message register is word-shaped (kext sites are 32-bit) and the
 * W5-live 64-bit writeq is the flagged SError candidate (receipt
 * follow-up item 1).  SCRATCH is host-writable behind the W8 grant
 * (W9: nonzero values latch); the a2i/doorbell send class stays
 * fatal even granted.  The session is the gate in front of
 * ane_t6021_csne_ping_attempt: no fw MGMT word -> the PING stays
 * fenced (soft wall) instead of repeating the machine-fatal class. */

static void ane_mbi_send(struct ane_t6021 *ane, u64 msg, u32 doorbell_bit,
			 const char *what)
{
	void __iomem *eng = ane->base[ANE_T6021_REG_ENGINE];

	/* The netconsole seam: printed BEFORE the first MMIO write of
	 * the send, same contract as the CSNE TX line. */
	dev_info(ane->dev, "MGMT TX %s: msg=%016llx -> a2i(half) + doorbell %#x\n",
		 what, msg, doorbell_bit);
	dma_wmb();
	writel(lower_32_bits(msg), eng + ANE_MBI_MSG_A2I_WR);
	writel(upper_32_bits(msg), eng + ANE_MBI_MSG_A2I_WR + 4);
	dma_wmb();
	writel(doorbell_bit, eng + ANE_MBI_DOORBELL);
}

/* fw->host receive = the real ASC mailbox (W10): i2a_control
 * +0x1408114 gates a 64-bit POP-ON-READ RECV0/1 +0x1408830/8 pair
 * (upstream apple mailbox semantics; W10 live read-proven clean).
 * Only read RECV when a word is pending — a blind read eats it. */
static bool ane_mbox_pending(struct ane_t6021 *ane)
{
	return !(readl(ane->base[ANE_T6021_REG_ENGINE] +
		       ANE_ASC_MBOX_I2A_CTRL) & ANE_ASC_MBOX_CTRL_EMPTY);
}

static u64 ane_mbox_recv(struct ane_t6021 *ane)
{
	void __iomem *eng = ane->base[ANE_T6021_REG_ENGINE];
	u32 lo = readl(eng + ANE_ASC_MBOX_I2A_RECV0);
	u32 hi = readl(eng + ANE_ASC_MBOX_I2A_RECV1);

	return (u64)hi << 32 | lo;
}

/* Peek: 0 when the mailbox is empty (no side effect), else the
 * pending 64-bit word (consumed — pop-on-read). */
static u64 ane_mbi_i2a_peek(struct ane_t6021 *ane)
{
	return ane_mbox_pending(ane) ? ane_mbox_recv(ane) : 0;
}

/* Poll the fw->host receive surface for @ms; log every change; stop
 * at the first word carrying nonzero MGMT type bits (already the
 * message we want) or when the window ends.
 *
 * W10 CORRECTION: this watch used to poll +0x1170000/4 — the CNTVCT
 * mirror, structurally unable to carry a MGMT word. The receive
 * surface is the real ASC mailbox: ane_mbi_i2a_peek reads RECV0/1
 * only while i2a_control reports a pending word (pop-on-read — a
 * blind read would eat the message). Runs only behind the booted
 * gate, i.e. with a live fw; the mailbox pop-read class has no
 * live-read precedent yet and is logged on first use. */
static void ane_mbi_watch(struct ane_t6021 *ane, const char *when,
			  unsigned int ms, u64 *msg, u32 *type)
{
	unsigned long start = jiffies;
	u64 prev = ane_mbi_i2a_peek(ane);

	*msg = prev;
	*type = 0;
	dev_info(ane->dev, "MGMT watch %s: mbox=%016llx (baseline)\n",
		 when, prev);
	while (time_before(jiffies, start + msecs_to_jiffies(ms))) {
		u64 cur;
		u32 t;

		msleep(100);
		cur = ane_mbi_i2a_peek(ane);
		if (cur == prev)
			continue;
		t = FIELD_GET(ANE_RTKIT_TYPE, cur);
		dev_info(ane->dev,
			 "MGMT mbox %016llx -> %016llx type=%u%s at +%ums\n",
			 prev, cur, t, t ? " [MGMT]" : "",
			 jiffies_to_msecs(jiffies - start));
		prev = cur;
		if (t) {
			*msg = cur;
			*type = t;
			return;
		}
	}
	*msg = prev;
}

static void ane_mbi_mgmt_reply_hello(struct ane_t6021 *ane, u64 fw_hello)
{
	u32 min_ver = FIELD_GET(ANE_RTKIT_HELLO_MINVER, fw_hello);
	u32 max_ver = FIELD_GET(ANE_RTKIT_HELLO_MAXVER, fw_hello);
	u32 want;

	want = clamp(max_ver, (u32)ANE_RTKIT_VER_MIN, (u32)ANE_RTKIT_VER_MAX);
	if (min_ver > ANE_RTKIT_VER_MAX || max_ver < ANE_RTKIT_VER_MIN) {
		dev_err(ane->dev,
			"MGMT HELLO version window [%u,%u] outside [%d,%d] — replying %u anyway\n",
			min_ver, max_ver, ANE_RTKIT_VER_MIN, ANE_RTKIT_VER_MAX,
			want);
	}
	ane_mbi_send(ane, FIELD_PREP(ANE_RTKIT_TYPE,
				     ANE_RTKIT_MGMT_HELLO_REPLY) |
		     FIELD_PREP(ANE_RTKIT_HELLO_MINVER, want) |
		     FIELD_PREP(ANE_RTKIT_HELLO_MAXVER, want),
		     BIT(0), "HELLO_REPLY");
}

static bool ane_t6021_mgmt_session(struct ane_t6021 *ane)
{
	bool fw_spoke = false, hello_done = false, started_ep1 = false;
	bool host_hello = false;
	unsigned int rounds = 16;	/* cap: a spamming fw must not
					 * hang probe forever */

	while (rounds--) {
		u64 msg;
		u32 type;
		const char *when = host_hello ? "post-host-HELLO" : "HELLO";

		ane_mbi_watch(ane, when, 3000, &msg, &type);

		/* Silent window: the one-shot host opener (step 3), then
		 * a final watch; a second silent window ends the session
		 * with fw_spoke=false (soft wall). */
		if (!type) {
			if (fw_spoke || host_hello)
				break;
			host_hello = true;
			ane_mbi_send(ane, FIELD_PREP(ANE_RTKIT_TYPE,
				     ANE_RTKIT_MGMT_HELLO) |
				     FIELD_PREP(ANE_RTKIT_HELLO_MINVER,
				     ANE_RTKIT_VER_MIN) |
				     FIELD_PREP(ANE_RTKIT_HELLO_MAXVER,
				     ANE_RTKIT_VER_MAX),
				     BIT(0), "HELLO(host)");
			continue;
		}
		fw_spoke = true;

		switch (type) {
		case ANE_RTKIT_MGMT_HELLO:
			ane_mbi_mgmt_reply_hello(ane, msg);
			hello_done = true;	/* our half is done */
			break;
		case ANE_RTKIT_MGMT_HELLO_REPLY:
			dev_info(ane->dev,
				 "MGMT HELLO_REPLY: min=%u max=%u\n",
				 (u32)FIELD_GET(ANE_RTKIT_HELLO_MINVER, msg),
				 (u32)FIELD_GET(ANE_RTKIT_HELLO_MAXVER, msg));
			hello_done = true;
			break;
		case ANE_RTKIT_MGMT_EPMAP:
			dev_info(ane->dev, "MGMT EPMAP base=%u bitmap=%08x last=%u\n",
				 (u32)FIELD_GET(ANE_RTKIT_EPMAP_BASE, msg),
				 (u32)FIELD_GET(ANE_RTKIT_EPMAP_BITMAP, msg),
				 msg & ANE_RTKIT_EPMAP_LAST ? 1u : 0u);
			/* rtkit echo: base + MORE/LAST reply bit */
			ane_mbi_send(ane, FIELD_PREP(ANE_RTKIT_TYPE,
				     ANE_RTKIT_MGMT_EPMAP) |
				     FIELD_PREP(ANE_RTKIT_EPMAP_BASE,
				     FIELD_GET(ANE_RTKIT_EPMAP_BASE, msg)) |
				     (msg & ANE_RTKIT_EPMAP_LAST ?
				      ANE_RTKIT_EPMAP_LAST :
				      ANE_RTKIT_EPMAP_REPLY_MORE),
				     BIT(0), "EPMAP_REPLY");
			break;
		case ANE_RTKIT_MGMT_SET_IOP_PWR_STATE:
			/* ACK echoes the fw's requested state */
			ane_mbi_send(ane, FIELD_PREP(ANE_RTKIT_TYPE,
				     ANE_RTKIT_MGMT_SET_IOP_PWR_STATE_ACK) |
				     (msg & ANE_RTKIT_PWR_STATE),
				     BIT(0), "IOP_PWR_ACK");
			hello_done = true;
			break;
		default:
			/* EPRollCall/PowerAck and anything unknown: log
			 * raw, decode on sight, no reply guesswork */
			dev_info(ane->dev, "MGMT fw word type=%llu msg=%016llx (logged, no reply)\n",
				 (u64)type, msg);
			if (type == ANE_RTKIT_MGMT_SET_AP_PWR_STATE_ACK)
				hello_done = true;
			break;
		}

		/* Step 5: once the handshake phase is answered, announce
		 * the EP1 surface then STARTEP it (kext order:
		 * SetupEndpoints -> STARTEP -> app traffic). */
		if (hello_done && !started_ep1) {
			started_ep1 = true;
			ane_mbi_send(ane, ane_ep_doorbell_encode(0, 0x10000),
				     BIT(1), "SETUPEP(EP1 surface)");
			ane_mbi_send(ane, FIELD_PREP(ANE_RTKIT_TYPE,
				     ANE_RTKIT_MGMT_STARTEP) |
				     FIELD_PREP(ANE_RTKIT_STARTEP_EP,
				     ANE_T6021_EP_INIT) |
				     ANE_RTKIT_STARTEP_FLAG,
				     BIT(0), "STARTEP(EP1)");
			ane->ep[ANE_T6021_EP_INIT].started = true;
		}
	}

	dev_info(ane->dev, "MGMT session %s: fw_spoke=%u hello_done=%u\n",
		 fw_spoke ? "exchanged" : "silent", fw_spoke, hello_done);
	return fw_spoke;
}

/* ---- RTBuddy app endpoints (W2 §3) ---- */

static const struct ane_t6021_ep ane_ep_config[ANE_T6021_EP_COUNT] = {
	[1] = { .id = 1, .name = "INIT", .fourcc = 0x494e4954,
		.ring_size = 0x10000 },
	[2] = { .id = 2, .name = "T2FC", .fourcc = 0x54324643,
		.ring_size = 0x40000 },
	[3] = { .id = 3, .name = "T2FH", .fourcc = 0x54324648,
		.ring_size = 0x40000 },
	[4] = { .id = 4, .name = "T2HS", .fourcc = 0x54324853,
		.ring_size = 0x10000 },
	[5] = { .id = 5, .name = "T2HC", .fourcc = 0x54324843,
		.ring_size = 0x20000 },
	[6] = { .id = 6, .name = "T2HT", .fourcc = 0x54324854,
		.ring_size = 0x10000 },
};

/* ---- CSNE_CMD submission on the INIT channel (W4) ---- */

int ane_t6021_csne_submit(struct ane_t6021 *ane, const void *cmd, size_t size)
{
	struct ane_t6021_ep *r = &ane->ep[ANE_T6021_EP_INIT];
	u32 cursor;
	u64 doorbell;
	void __iomem *eng = ane->base[ANE_T6021_REG_ENGINE];
	int err;

	BUILD_BUG_ON(ANE_T6021_EP_INIT != 1);

	if (!cmd || size < sizeof(struct ane_csne_hdr))
		return -EINVAL;
	if (size > ANE_CSNE_CMD_MAX_SIZE)
		return -E2BIG;
	if (!r->started)
		return -ENOTCONN;

	mutex_lock(&ane->mbox_lock);

	/* K14 rtbuddyEndpointSendMessage 0x…95f3af8-c04: size bound
	 * first, then the write cursor — kept when cursor+size fits
	 * strictly below ring_size, else the slot restarts at 0 (an
	 * exact fit wraps too: csel lo @0x…95f3b04). */
	if (size > r->ring_size) {
		err = -E2BIG;
		goto out;
	}
	cursor = r->write_cursor;
	if (cursor + size >= r->ring_size)
		cursor = 0;

	/* Ring slot is device-visible DMA memory; the MBI doorbell write
	 * (dma_wmb before it) orders this copy. */
	memcpy(r->ring + cursor, cmd, size);

	/* Provider-kext decode (2026-09-19): the gate send = the 48-bit
	 * MBI word into the a2i message register, then write32(1 << ep)
	 * to +0x1844000.  K14 orders the ring memcpy before the gate
	 * call (rtbuddyEndpointSendMessage 0x…95f3b20 -> 0x…95f3c30);
	 * dma_wmb is the Linux equivalent.  The SCRATCH family stays
	 * untouched — those writes are SError-fatal on this silicon
	 * (2026-09-19); only msgreg + doorbell are written here, and
	 * only with mbi_doorbell=1. */
	doorbell = ane_mbi_msg48_encode(cursor, size);
	if (!ane->doorbell) {
		dev_dbg(ane->dev,
			"csne ep%u: ring cursor=%u len=%zu msg48=%012llx (fenced: mbi_doorbell=0)\n",
			r->id, cursor, size, doorbell);
		err = -EOPNOTSUPP;
		goto out;
	}
	/* The netconsole seam: this line prints before the first MMIO
	 * write of the sequence (a2i word -> doorbell). */
	dev_info(ane->dev,
		 "CSNE TX ep%u: ring iova=%pad cursor=%u len=%zu msg48=%012llx -> a2i + doorbell %#lx\n",
		 r->id, &r->ring_iova, cursor, size, doorbell,
		 BIT(r->id));
	dma_wmb();
	/* 32-bit halves: the AKF message register is word-shaped (all
	 * kext sites are 32-bit stores) and the W5-live 64-bit writeq
	 * is the flagged SError candidate (receipt follow-up item 1). */
	writel(lower_32_bits(doorbell), eng + ANE_MBI_MSG_A2I_WR);
	writel(upper_32_bits(doorbell), eng + ANE_MBI_MSG_A2I_WR + 4);
	dma_wmb();
	writel(BIT(r->id), eng + ANE_MBI_DOORBELL);

	/* K14 advances the cursor only on send success (0x…95f3c70-c)
	 * and snapshots the slot into the command state (rec+0x40 /
	 * rec+0x58); this driver keeps just the cursor. */
	r->write_cursor = cursor + size;
	err = 0;
out:
	mutex_unlock(&ane->mbox_lock);
	return err;
}

/* W5-live one-shot: CSNE_CMD_PING (header-only 0x11) on EP1/INIT ->
 * doorbell 0x2.  Caller is probe, after the loaded banner: by then
 * first_resume has passed, so the eight-island gate and the ASC
 * whitelist are clean (the W3 known-good state) — the ping cannot fire
 * on a failed gate because probe unwinds before this runs.
 *
 * W6: the probe-time sequence is EP0 MGMT session (HELLO/EPMAP
 * handling, then EP1 surface announce + STARTEP) FIRST, then this
 * PING — arming mbi_doorbell=1 runs the whole thing.  If the session
 * ends with the fw silent, the PING stays fenced (soft wall).  After
 * the send, response surfaces are watched 3 s, changes only (the i2a
 * lo counter ticks ambiently — fw heartbeat in the W4-fix captures —
 * so it is sampled for the summary, not the trigger): the ring slot
 * doubles as the response area (fw completion strb @+6 / str @+8,
 * 0x4d324/0x4d3b0), and the i2a hi word + a2i_rd peer register carry
 * fw->host notifications.
 *
 * LIVE RESULT 2026-09-19 (W5-live, receipt
 * 2026-09-19-h14-w5-live-ping-serror.md): the first ring SError'd CPU0
 * (0xbe000000) 5 us after the {a2i word, doorbell} write pair — the
 * fw rejects an EP1 send with no RTBuddy session in front of it.
 * W6: ane_t6021_mgmt_session() now runs first (HELLO/EPMAP/STARTEP on
 * EP0, 32-bit a2i halves); a silent session fences this PING. */
void ane_t6021_csne_ping_attempt(struct ane_t6021 *ane)
{
	void __iomem *eng = ane->base[ANE_T6021_REG_ENGINE];
	u8 *ring = ane->ep[ANE_T6021_EP_INIT].ring;
	struct ane_csne_hdr hdr;
	u64 slot0, slot8, prev0, prev8;
	u32 hi, lo, rd, prev_hi, prev_rd;
	unsigned long start;
	int err;

	if (!ane->doorbell)
		return;

	/* W15 gate: the W5/W6 host sends into these surfaces failed
	 * (0xbe000000) while no valid fw was staged or running; cause
	 * was not isolated. Conservative rule: this driver sends
	 * nothing until the boot handshake observes a live fw AND the
	 * DONE response has been validated against owned windows —
	 * booted alone is an ACK milestone, not transport clearance
	 * (Main lifetime review 2026-09-20: first-boot fenced window). */
	if (!ane->booted || !ane->response_validated) {
		dev_err(ane->dev,
			"CSNE PING ep1: FENCED — booted=%u response_validated=%u (first boot: transport stays fenced until DONE response semantics are sourced and the fw device address is range/length validated)\n",
			ane->booted, ane->response_validated);
		return;
	}

	/* W6 gate: the EP0 MGMT session MUST precede any EP1 send
	 * (W5-live: a bare EP1 ring is the machine-fatal 0xbe000000
	 * class).  No fw MGMT word = soft wall: the PING stays fenced
	 * and the wall is reported instead of replayed. */
	if (!ane_t6021_mgmt_session(ane)) {
		dev_err(ane->dev,
			"CSNE PING ep1: FENCED — EP0 MGMT session silent (soft wall; see W5-live SError receipt)\n");
		return;
	}

	ane_mbi_msgregs_dump(ane, "pre-ping");
	ane_csne_hdr_init(&hdr, CSNE_CMD_PING);
	err = ane_t6021_csne_submit(ane, &hdr, sizeof(hdr));
	if (err) {
		dev_err(ane->dev, "CSNE PING ep1: submit failed %d\n", err);
		return;
	}

	prev0 = READ_ONCE(*(__force u64 *)ring);
	prev8 = READ_ONCE(*(__force u64 *)(ring + 8));
	prev_hi = readl(eng + ANE_MBI_MSG_I2A_HI);
	prev_rd = readl(eng + ANE_MBI_MSG_A2I_RD);
	start = jiffies;
	while (time_before(jiffies, start + msecs_to_jiffies(3000))) {
		msleep(200);
		slot0 = READ_ONCE(*(__force u64 *)ring);
		slot8 = READ_ONCE(*(__force u64 *)(ring + 8));
		hi = readl(eng + ANE_MBI_MSG_I2A_HI);
		rd = readl(eng + ANE_MBI_MSG_A2I_RD);
		if (slot0 != prev0 || slot8 != prev8) {
			dev_info(ane->dev,
				 "CSNE PING: ring slot changed %016llx_%016llx -> %016llx_%016llx at +%ums\n",
				 prev0, prev8, slot0, slot8,
				 jiffies_to_msecs(jiffies - start));
			prev0 = slot0;
			prev8 = slot8;
		}
		if (hi != prev_hi || rd != prev_rd) {
			dev_info(ane->dev,
				 "CSNE PING: msgregs moved i2a_hi %08x->%08x a2i_rd %08x->%08x at +%ums\n",
				 prev_hi, hi, prev_rd, rd,
				 jiffies_to_msecs(jiffies - start));
			prev_hi = hi;
			prev_rd = rd;
		}
	}
	lo = readl(eng + ANE_MBI_MSG_I2A_LO);
	dev_info(ane->dev,
		 "CSNE PING watch done: i2a=%08x_%08x a2i_rd=%08x a2i_wr=%08x slot=%016llx_%016llx\n",
		 prev_hi, lo, prev_rd, readl(eng + ANE_MBI_MSG_A2I_WR),
		 prev0, prev8);
}

irqreturn_t ane_t6021_rtkit_irq_thread(int irq, void *data)
{
	ane_t6021_rtkit_drain(data);
	return IRQ_HANDLED;
}

int ane_t6021_rtkit_init(struct ane_t6021 *ane)
{
	static const u32 sizes[] = { 0x10000, 0x20000, 0x40000 };
	int id, err;

	/* doorbell codec round-trip, unit-1 (4K) size class — the only
	 * class the RTBuddy ring sizes produce; then a non-multiple
	 * size to pin the ceiling rounding (K14 cinc @0x…95fe8dc) */
	for (id = 0; id < ARRAY_SIZE(sizes); id++) {
		u64 msg = ane_ep_doorbell_encode(0x1234, sizes[id]);

		if (ane_ep_doorbell_size(msg) != sizes[id] ||
		    FIELD_GET(ANE_EP_DOORBELL_OFFSET, msg) != 0x1234) {
			dev_err(ane->dev, "doorbell codec broken (size %#x)\n",
				sizes[id]);
			return -EINVAL;
		}
	}
	if (ane_ep_doorbell_size(ane_ep_doorbell_encode(0, 0x1234)) !=
	    0x2000) {
		dev_err(ane->dev, "doorbell codec ceiling broken\n");
		return -EINVAL;
	}

	mutex_init(&ane->mbox_lock);
	memcpy(ane->ep, ane_ep_config, sizeof(ane->ep));

	/* RTBuddy app rings up front: STARTEP for ids 1..6 fires from the
	 * MGMT path once the fw ACKs the AP power state (W2 §3, §7). */
	for (id = ANE_T6021_EP_INIT; id < ANE_T6021_EP_COUNT; id++) {
		struct ane_t6021_ep *r = &ane->ep[id];

		r->ring = dma_alloc_coherent(ane->dev, r->ring_size,
					     &r->ring_iova, GFP_KERNEL);
		if (r->ring &&
		    !ane_t6021_fw_alias_iova_ok(ane, r->ring_iova,
						r->ring_size)) {
			dev_err(ane->dev,
				"ep%u ring %pad overlaps fw alias — refusing\n",
				r->id, &r->ring_iova);
			dma_free_coherent(ane->dev, r->ring_size, r->ring,
					  r->ring_iova);
			r->ring = NULL;
		}
		if (!r->ring) {
			err = -ENOMEM;
			goto free;
		}
		dev_dbg(ane->dev, "ep%u %s ring %u bytes at %pad\n",
			r->id, r->name, r->ring_size, &r->ring_iova);
	}
	return 0;

free:
	ane_t6021_rtkit_shutdown(ane);
	return err;
}

void ane_t6021_rtkit_shutdown(struct ane_t6021 *ane)
{
	int id;

	for (id = ANE_T6021_EP_INIT; id < ANE_T6021_EP_COUNT; id++) {
		struct ane_t6021_ep *r = &ane->ep[id];

		if (!r->ring)
			continue;
		dma_free_coherent(ane->dev, r->ring_size, r->ring,
				  r->ring_iova);
		r->ring = NULL;
		r->started = false;
	}
	mutex_destroy(&ane->mbox_lock);
}
