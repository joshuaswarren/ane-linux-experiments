// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* T6021 (H14 / J414c) Apple Neural Engine — skeleton constants and types.
 *
 * Every constant below is static-decode provenance, no device writes:
 *  - reg windows, IRQ, pmgr islands: ADT j414c (DeviceTree.j414cap.im4p,
 *    receipts/2026-09-18-t6021-engine-layout-mined §2), Linux translation
 *    +0x200000000 (proven class, pmgr low-32 match).
 *  - ASC cpu block (+0x1400000 h14g) + MBI transport (SCRATCH, channel
 *    table, +0x1844000 doorbell): K14 kext disasm, W4-fix receipt
 *    (initializeANESoCConfig h14g blocks + InitializeRTBuddy +
 *    doorbell setter 0x…95ebdd0); m1n1 ASCRegs = t8103 cross-ref only
 *  - RTKit MGMT protocol: Asahi rtkit.c semantics, u64 message halves as
 *    staged in omarchy-ane rtkit/h14_rtkit_hello.py (commit 6ad26b7).
 *  - RTBuddy endpoint table + doorbell word: K14 kext cfg table
 *    __DATA_CONST.__const+0x814e520 and HandleRTBuddyMessage
 *    (receipts/2026-09-18-h14-w2-protocol-decode §3).
 *
 * DT binding (driver + ane/t6021-j414c-ane.dts are the two halves):
 *  compatible    = "apple,t6021-ane"
 *  reg/reg-names = "engine" (whole 32 MiB ADT range0, 0x284000000;
 *                  the H13-style +0x1c04000 engine delta does not exist
 *                  on this SoC — kext never computes it and first touch
 *                  external-aborted, proven 2026-09-18),
 *                  "pmgr" (0x28e080000+0x4034, pmgr1,t6021 island words),
 *                  "set"  (0x28e08c000+0x4000, SET window — read-only by
 *                  repo rule: direct SET writes external-abort the SoC)
 *  interrupts    = one AIC2 level-high interrupt named "ane" (raw 884;
 *                  [INFERENCE W2 §3: the ANE MBI doorbell IRQ].
 *                  dart-ane0 carries raw 885, provider-owned, never
 *                  fetched here)
 *  iommus        = dart-ane0 streams (apple,t6020-dart/apple,t8110-dart
 *                  nodes). The ADT dart-ane0 is one hardware block with a
 *                  four-window quartet (0x85800000/85810000/85820000/
 *                  85804000, each 0x4000); the installed overlay's
 *                  three-node split (t6001-proven pattern) is kept.
 *  power-domains = eight, phase1 raise order (sys_mpm→td→base→set1..4,
 *                  ane_cpu last): ane_sys_mpm@4000, ane_td@4008,
 *                  ane_base@4010, ane_set1..4@4018-4030, ane_cpu@2e0.
 *                  ane_td/ane_base were the W3 chain gap (six consumed,
 *                  block access reset the machine); receipt
 *                  2026-09-19-h14-init-sequence-kext-trace §3.
 */

#ifndef __ANE_T6021_H__
#define __ANE_T6021_H__

#include <linux/bitfield.h>
#include <linux/bits.h>
#include <linux/build_bug.h>
#include <linux/dma-mapping.h>
#include <linux/interrupt.h>
#include <linux/math.h>
#include <linux/sizes.h>
#include <linux/string.h>
#include <linux/device.h>
#include <linux/mutex.h>

/* reg windows (ane/t6021-j414c-ane.dts reg-names order) */
enum {
	ANE_T6021_REG_ENGINE,
	ANE_T6021_REG_PMGR,
	ANE_T6021_REG_SET,
	ANE_T6021_REG_COUNT
};

/* ANE-block-relative ASC/RTBuddy addresses.  CPU block = ANE+0x1400000
 * for h14g (K14 initializeANESoCConfig h14g blocks 0x…961365c /
 * 0x…9614084 build 0x1400044 with NO 0x200000 orr — the 0x1600044
 * phase-1 §2 quote is the h16g/h17/h18g variant block 0x…9613458;
 * runtime h14g-shaped sites 0x…95d2968 write RUN there).  CPU_STATUS
 * +0x48 keeps the m1n1 ASCRegs +4 shape (config field dev+0x49c =
 * 0x1400048; kext poll 0x…95ecfb4).  The m1n1 t8103 mailbox
 * (INBOX_CTRL +0x8110 / INBOX0 +0x8800 family) has NO h14g analog:
 * zero 0x1608xxx / 0x1408xxx constants in the whole kext text, and the
 * +0x1608114 read SError-aborted jw14m2 (2026-09-19).  The h14g
 * transport is MBI (see ANE_MBI_* below). */
#define ANE_ASC_CPU_CONTROL	0x1400044	/* RUN = BIT(4) */
#define ANE_ASC_CPU_STATUS	0x1400048	/* m1n1 R_CPU_STATUS shape */
#define ANE_ASC_RVBAR		0x1050000	/* fw entry | valid bit0 */
#define ANE_ASC_EDPRCR		0x1010310	/* phase1 S2 whitelist */
#define ANE_ASC_VERS		0x1840000
#define ANE_ASC_RTB_STATUS	0x1840088	/* K14 poll: value < 2 */
#define ANE_ASC_RTB_STATUS_UNK7C 0x184007c	/* phase1 S2 whitelist */

/* MBI transport (K14 h14g config: socinit stores the SCRATCH register
 * offsets as q-blobs @0x…7503a40/0x…7503a50/0x…7503a60 into dev+0x438
 * and the message-register offsets @0x…7503860 into dev+0x488; runtime
 * handshake in InitializeRTBuddy 0x…95e942c: cmd buffer base ->
 * SCRATCH0/1 (0x…95eaa94), wake 0xf7fbdff9 -> SCRATCH7 (0x…95eab24),
 * poll SCRATCH7 == 0x08042006 "channel description table ready"
 * (0x…95eab74), table base read back from SCRATCH0/1 (0x…95ead04),
 * per-channel {type,bit,size,phys} entries registered with the
 * doorbell setter 0x…95ebdd0 writing (1 << bit) to +0x1844000.  Host
 * ack = SCRATCH3 = 0x08042006 (0x…95eaee4).
 *
 * PROVIDER DECODE (2026-09-19, kernelcache.release.mac14j): in
 * RTBuddy mode the TX gate lives in com.apple.driver.RTBuddy 1.0.0
 * (carved from the KC, 46088 B, __TEXT_EXEC 0x…b696860).  RTBuddy
 * publishes per-ANE nubs named "%sEndpoint%u" (0x…7cc7d3f) with the
 * role string "ANE" -> ANEEndpoint1..ANEEndpoint5, class
 * RTBuddyEndpointService (0x98 B) wrapping RTBuddyEndpoint (0xE8 B),
 * over the kernel IOSlaveEndpoint family; K14 EnableRTBuddyEndpoints
 * (0x…95feb30) formats the name ("%s%d" @0x…74c481f), waits 10 s
 * (x1 = 10^10 ns) for the match and takes the gate from [svc+0x88],
 * registering its rx callback at gate+0xd0.  The gate's per-message
 * send is the vtable+0x1e8 slot; its body ends in the AKF mailbox
 * write (AKF_AP_MAILBOX_SET = the +0x1844000 doorbell; RTBuddy dump
 * fn 0x…b69d9c8 prints "AKF_KIC_INBOX_CTRL / AKF_KIC_MAILBOX_SET /
 * AKF_AP_OUTBOX_CTRL / AKF_AP_MAILBOX_SET" and guards
 * "INBOX%d not ready"/"Inbox%d overflow").  Endpoint number =
 * doorbell bit: EP0 is RTBuddyManagementEndpoint (_handleHello /
 * _handleEPRollCall / _handlePowerAck), EP1..5 the ANE data channels.
 * [INFERENCE: the fw->host doorbell/IRQ bit numbering mirrors the
 * host->fw SET bit per Asahi rtkit semantics; pinned live by W5.] */
#define ANE_MBI_SCRATCH0	0x1840048	/* SCRATCH0..7 = +0x48..+0x64 */
#define ANE_MBI_SCRATCH7	0x1840064
#define ANE_MBI_WAKE_REQ	0xf7fbdff9	/* host->fw SCRATCH7 */
#define ANE_MBI_WAKE_ACK	0x08042006	/* fw->host: table ready */
#define ANE_MBI_DOORBELL	0x1844000	/* write32 (1 << endpoint id) */
#define ANE_MBI_MSG_I2A_LO	0x1170000	/* fw->host u64 message pair */
#define ANE_MBI_MSG_I2A_HI	0x1170004
#define ANE_MBI_MSG_A2I_RD	0x184c000	/* host->fw message read peer */
#define ANE_MBI_MSG_A2I_WR	0x1850000	/* host->fw message write */

/* Per-message MBI word (48-bit ring notification, K14
 * rtbuddyEndpointSendMessage 0x…95f3bf4-c30): offset = ring write
 * cursor [23:0], length [47:24].  NOT the 54-bit surface-announce
 * word (ane_ep_doorbell_encode below) — that one rides SetupEndpoints
 * buffer mapping; this one is what the gate sends per command: the
 * gate call is send(&msg48, 0, 1) at vtable+0x1e8, after the command
 * bytes are already memcpy'd into the shared ring at ring_base +
 * cursor.  Length is capped at 0xffffff by the encoder field. */
#define ANE_MBI_MSG48_OFF	GENMASK_ULL(23, 0)
#define ANE_MBI_MSG48_LEN	GENMASK_ULL(47, 24)

static inline u64 ane_mbi_msg48_encode(u32 cursor, u32 len)
{
	return (cursor & ANE_MBI_MSG48_OFF) |
	       FIELD_PREP(ANE_MBI_MSG48_LEN, len);
}

/* Host->fw TX sequence (RTBuddy mode, all static-decode proven):
 *   1. fail if len > ring_size (K14 0xe00002c2 @0x…95f3a24)
 *   2. cursor = write_cursor; if (cursor + len >= ring_size) cursor = 0
 *      (exact fit wraps: csel lo @0x…95f3b04)
 *   3. memcpy(ring + cursor, cmd, len)   (DMA-coherent ring)
 *   4. dma_wmb()                          (ring visible before bell)
 *   5. write32(ANE_MBI_MSG_A2I_WR, lo) + write32(+4, hi) — 32-bit
 *      halves (the AKF message register is word-shaped; W6 proved the
 *      W5-live abort was NOT the 64-bit writeq — the halves abort too)
 *   6. write32(ANE_MBI_DOORBELL, 1 << ep)
 *   7. on send success only: write_cursor = cursor + len (K14
 *      0x…95f3c70-c); the cursors at rec+0x40/rec+0x58 track the last
 *      issued slot.
 * CSNE_CMD_PING = header-only 0x11 on EP1 (INIT) -> doorbell bit
 * 1 << 1 = 0x2.  Only the a2i message register + doorbell are
 * touched, and only behind the mbi_doorbell opt-in (both stay
 * host-write-fatal even behind the W8 grant, W9; SCRATCH family is
 * host-writable granted, W9 nonzero latch). */

/* MBI channel-table entry (kext stride 0x100, fields at +0x40 family:
 * type @+0x40, doorbell bit @+0x44, size @+0x48, phys @+0x50 —
 * InitializeRTBuddy 0x…95eade8-0x…95eae58) */
#define ANE_MBI_CHAN_STRIDE	0x100
#define ANE_MBI_CHAN_MAX_DUMP	8

/* RTKit MGMT (EP 0); type bits [59:52], u64 message halves */
#define ANE_RTKIT_TYPE			GENMASK_ULL(59, 52)
#define ANE_RTKIT_MGMT_HELLO		1
#define ANE_RTKIT_MGMT_HELLO_REPLY	2
#define ANE_RTKIT_MGMT_STARTEP		5
#define ANE_RTKIT_MGMT_SET_IOP_PWR_STATE	6
#define ANE_RTKIT_MGMT_SET_IOP_PWR_STATE_ACK	7
#define ANE_RTKIT_MGMT_EPMAP		8
#define ANE_RTKIT_MGMT_SET_AP_PWR_STATE		0xb
#define ANE_RTKIT_MGMT_SET_AP_PWR_STATE_ACK	0xb

#define ANE_RTKIT_HELLO_MINVER		GENMASK_ULL(15, 0)
#define ANE_RTKIT_HELLO_MAXVER		GENMASK_ULL(31, 16)
#define ANE_RTKIT_EPMAP_LAST		BIT_ULL(51)
#define ANE_RTKIT_EPMAP_BASE		GENMASK_ULL(34, 32)
#define ANE_RTKIT_EPMAP_BITMAP		GENMASK_ULL(31, 0)
#define ANE_RTKIT_EPMAP_REPLY_MORE	BIT_ULL(0)
#define ANE_RTKIT_STARTEP_EP		GENMASK_ULL(39, 32)
#define ANE_RTKIT_STARTEP_FLAG		BIT_ULL(1)
#define ANE_RTKIT_PWR_STATE		GENMASK_ULL(15, 0)
#define ANE_RTKIT_PWR_STATE_ON		0x20

#define ANE_RTKIT_VER_MIN	11
#define ANE_RTKIT_VER_MAX	12

/* RTKit system endpoints rtkit.c starts when announced */
#define ANE_RTKIT_EP_CRASHLOG	1
#define ANE_RTKIT_EP_SYSLOG	2
#define ANE_RTKIT_EP_DEBUG	3
#define ANE_RTKIT_EP_IOREPORT	4
#define ANE_RTKIT_EP_OSLOG	8
#define ANE_RTKIT_EP_TRACEKIT	0xa

/* RTBuddy app endpoints — K14 InitializeRTBuddyEndpoints opens ids 1..6;
 * ring sizes + fourccs from the per-EP config table (W2 §3). fourcc is
 * byte-reversed in the table (0x54324643 = "T2FC"). */
enum ane_t6021_eps {
	ANE_T6021_EP_INIT = 1,	/* INIT — CSNE_CMD controller channel (W4) */
	ANE_T6021_EP_T2FC,	/* fw->host commands */
	ANE_T6021_EP_T2FH,	/* fw->host commands */
	ANE_T6021_EP_T2HS,
	ANE_T6021_EP_T2HC,
	ANE_T6021_EP_T2HT,	/* polled on the host */
	ANE_T6021_EP_COUNT = ANE_T6021_EP_T2HT + 1	/* arrays index by id */
};

/* CSNE command ids — selene id->name table, vaddr 0xea430, 96 entries
 * (full set: receipts/2026-09-18-h14-w2-protocol-decode §4 and
 * receipts/2026-09-18-h14-w2-protocol-decode/fw_cmd_table.json). The
 * fw parses the id as u16 at wire offset +4 (W4 correction of the W2
 * §4 "offset 0" claim: fw sites 0x4d244/0x4d264/0x5246c); the kext
 * controller header for the fw->host direction is a different shape
 * (u32 id @ +0x8, 0x24 bytes) and never rides host->fw submission. */
enum ane_t6021_csne_cmd {
	CSNE_CMD_START		= 0x0000,
	CSNE_CMD_STOP		= 0x0001,
	CSNE_CMD_REG_FILE_LOAD	= 0x0005,	/* fw _rtk_tunables 1456 B */
	CSNE_CMD_BUILDINFO	= 0x0006,
	CSNE_CMD_BOOT		= 0x0010,
	CSNE_CMD_PING		= 0x0011,
	CSNE_CMD_POWER_DEVICE_ON	= 0x0013,
	CSNE_CMD_IPC_ENDPOINT_SET	= 0x0015,
	CSNE_CMD_IPC_ENDPOINT_UNSET	= 0x0016,
	CSNE_CMD_PROCEDURE_CALL	= 0x0204,
	CSNE_CMD_INFERENCE_CALL	= 0x0404,
	CSNE_CMD_BACK_CHANNEL_RPC	= 0x7000,
};

/* Doorbell word (app-EP ring notification, W2 §3): 54-bit packed
 * offset[43:0] | size_code[51:44] | unit[53:52]; unit 0=code bytes,
 * 1=code*4K, 2=code*1M, 3=code*2M. K14 SetupEndpoints encodes with
 * unit 1 below 1 MiB and unit 2 at or above, and the size code is a
 * CEILING division (cinc on remainder @0x…95fe8dc) — the reconstructed
 * receive-side size is the rounded-up value. */
#define ANE_EP_DOORBELL_OFFSET	GENMASK_ULL(43, 0)
#define ANE_EP_DOORBELL_SIZE	GENMASK_ULL(51, 44)
#define ANE_EP_DOORBELL_UNIT	GENMASK_ULL(53, 52)

static inline u64 ane_ep_doorbell_encode(u32 offset, u32 size)
{
	u64 unit = (size >= SZ_1M) ? 2 : 1;	/* K14 size-class encoder */
	u32 code = DIV_ROUND_UP(size, 1u << (unit * 12));

	return (offset & ANE_EP_DOORBELL_OFFSET) |
	       FIELD_PREP(ANE_EP_DOORBELL_SIZE, code) |
	       FIELD_PREP(ANE_EP_DOORBELL_UNIT, unit);
}

static inline u32 ane_ep_doorbell_size(u64 msg)
{
	static const u8 shift[] = { 0, 12, 20, 21 };
	u32 unit = FIELD_GET(ANE_EP_DOORBELL_UNIT, msg);

	return FIELD_GET(ANE_EP_DOORBELL_SIZE, msg) << shift[unit];
}

struct ane_t6021_ep {
	u8 id;
	const char *name;
	u32 fourcc;
	u32 ring_size;
	u32 write_cursor;	/* next ring slot (K14 rec+0x20) */
	void *ring;			/* dma_alloc_coherent, ring_size */
	dma_addr_t ring_iova;
	bool started;
};

struct ane_t6021 {
	struct device *dev;
	void __iomem *base[ANE_T6021_REG_COUNT];
	int irq;

	struct device **pd_dev;
	struct device_link **pd_link;
	int pd_count;

	/* Single MBI consumer (threaded IRQ + probe drain serialize
	 * here) */
	struct mutex mbox_lock;

	bool booted;		/* first_resume ran (eight-island gate) */

	/* The m1n1-analogy mailbox (+0x1608xxx) is read-fatal on t6021
	 * (SExternal-Abort 2026-09-19 under the full raise; phase1 hang
	 * 09-18) and does not exist in the kext text; default off =
	 * status-only bring-up.  Opt-in runs the kext-evidenced MBI
	 * handshake (SCRATCH wake -> fw channel table), capture-only. */
	bool transport;
	bool doorbell;	/* mbi_doorbell=1: EP rings may write the +0x1844000
			 * doorbell + a2i message register (decoded 2026-09-19) */
	bool irq_requested;

	/* MBI handshake state (transport only, capture-only) */
	bool mbi_table_ready;

	struct ane_t6021_ep ep[ANE_T6021_EP_COUNT];

	/* W13 fw surface (fw_load=1): coherent, DART-mapped via the
	 * device's iommu group. NULL unless loaded. */
	void *fw_buf;
	dma_addr_t fw_iova;
	u32 fw_size;
	u64 fw_pinned_iova;	/* host-chosen alias (fw_iova param), 0=none */
};

/* ane_t6021_rtkit.c */
int ane_t6021_rtkit_init(struct ane_t6021 *ane);
void ane_t6021_rtkit_shutdown(struct ane_t6021 *ane);
void ane_t6021_rtkit_drain(struct ane_t6021 *ane);
irqreturn_t ane_t6021_rtkit_irq_thread(int irq, void *data);
int ane_t6021_mbi_boot(struct ane_t6021 *ane);

/* ---- CSNE_CMD wire structs (host->fw on the INIT channel) ----
 *
 * W4 static decode, extending W2 §4 (the receipt's "fw parses a u16 id
 * at header offset 0" was WRONG — three independent fw parse sites read
 * the id as u16 at offset +4: the generic CSNE processor @0x4d264, its
 * preload @0x4d244, and the LOAD_PROGRAM/CREATE_PROCESS/PROCEDURE_CALL
 * pre-parse @0x5246c, all `ldrh wN, [xM, #4]` in selene). Wire is
 * little-endian; this module is arm64-only so host order is wire order.
 *
 * The generic processor takes commands < 0x1b89 bytes (work-item size
 * bound @0x4d134-0x4d158) and writes completion state back into the
 * command block (strb @0x4d324 byte +6, str @0x4d3b0 qword +8) — the
 * ring slot doubles as the response area. PING/BUILDINFO/BOOT/
 * REG_FILE_LOAD/IPC_ENDPOINT_SET fall through the processor's id tree
 * to the default path (0x4e65c): carried without field parsing, so
 * their payloads beyond the header are opaque until the W1 live
 * exchange pins them. */
struct ane_csne_hdr {
	u32 rsvd0;	/* bytes 0..3: never read by the fw processor; 0 */
	u16 id;		/* PROVEN u16 @ +4 (sites above) */
	u8 flags;	/* fw-written byte @ +6 (status/scratch) [INFERENCE] */
	u8 rsvd7;
};
static_assert(sizeof(struct ane_csne_hdr) == 8);

static inline void ane_csne_hdr_init(struct ane_csne_hdr *h, u16 id)
{
	memset(h, 0, sizeof(*h));
	h->id = id;
}

/* Header-only CSNE_CMDs: BOOT (0x10 — boot-arg surfaces ride
 * SCRATCH0-7 / SetupFWInitBootArgs, not the command, phase1 §2.5),
 * PING (0x11), BUILDINFO (0x06). sizeof(struct ane_csne_hdr) bytes. */

/* REG_FILE_LOAD (0x05) payload: the 1456 B blob is the fw's own
 * __DATA._rtk_tunables section (@0x100590, size 0x5b0) — its transport
 * (inline vs shared-memory iova) is [INFERENCE], pinned by W1. */
struct ane_csne_cmd_reg_file_load {
	struct ane_csne_hdr hdr;
	u8 blob[];
};

/* IPC_ENDPOINT_SET (0x15) payload: binds a host RTBuddy endpoint to a
 * fw channel. No field parsed by the fw processor — layout
 * [INFERENCE], pinned by W1. */
struct ane_csne_cmd_ipc_endpoint_set {
	struct ane_csne_hdr hdr;
	u8 payload[];
};

/* PROCEDURE_CALL (0x204) / INFERENCE_CALL (0x404) — the kext
 * CANE_SUB_PACKET_CMD_PROCEDURE_CALL family. Field offsets PROVEN from
 * the fw parse; field semantics named only where the kext asserts name
 * them (programId, procedureId, numIoBuffers in assert order, W2 §4):
 *   +0x08/+0x0c u32 pair validated together (ldp @0x4d654)
 *   +0x10        u64 passed to the fw validator (0x4d6d4)
 *   +0x18        u32 required in [8,15] (@0x4d660-0x4d66c)
 *   +0x28        u32 element count (loop bound @0x524bc-0x524c4)
 *   +0x60        count × 0x30-byte io-buffer records (@0x524a8-0x524b4)
 * The kext `size % sizeof(sCSneCmdProcedureCall) == 0` assert says
 * commands form same-shape arrays in the ring; this driver submits one
 * command per slot. INFERENCE_CALL shares the shape [INFERENCE: the
 * 0x404 id is not in the decoded id tree — it is the W4 submission
 * endpoint per the phase-1 workstream plan]. */
struct ane_csne_io_elem {
	u8 bytes[0x30];	/* internal layout not decoded */
};

struct ane_csne_cmd_procedure_call {
	struct ane_csne_hdr hdr;
	u32 program_id;		/* +0x08 */
	u32 procedure_id;	/* +0x0c */
	u64 field_10;
	u32 field_18;		/* fw requires 8..15 */
	u32 rsvd_1c;
	u64 field_20;
	u32 num_io_buffers;	/* +0x28 = element count */
	u32 rsvd_2c;
	u8 gap_30[0x30];
	struct ane_csne_io_elem io[];
};
static_assert(offsetof(struct ane_csne_cmd_procedure_call, program_id) == 0x08);
static_assert(offsetof(struct ane_csne_cmd_procedure_call, procedure_id) == 0x0c);
static_assert(offsetof(struct ane_csne_cmd_procedure_call, field_10) == 0x10);
static_assert(offsetof(struct ane_csne_cmd_procedure_call, field_18) == 0x18);
static_assert(offsetof(struct ane_csne_cmd_procedure_call, num_io_buffers) == 0x28);
static_assert(offsetof(struct ane_csne_cmd_procedure_call, io) == 0x60);

static inline size_t
ane_csne_cmd_procedure_call_size(unsigned int num_io_buffers)
{
	return sizeof(struct ane_csne_cmd_procedure_call) +
	       num_io_buffers * sizeof(struct ane_csne_io_elem);
}

/* Fw-side bound: the generic CSNE processor rejects work items of
 * 0x1b89 bytes and above (@0x4d134 cmp x2, #0x1b89). What x2 names
 * beyond "the command's size" is [INFERENCE] — enforced here as a
 * fail-fast so an oversized command cannot enter the ring. */
#define ANE_CSNE_CMD_MAX_SIZE	0x1b88

/* Submit one CSNE command block on the INIT (EP1) ring: K14
 * rtbuddyEndpointSendMessage semantics (W2 §3) — slot alloc with wrap,
 * memcpy into the ring, 54-bit doorbell word, cursor
 * advanced only on doorbell success. No synchronous response matching:
 * fw->host responses arrive on the T2F* channels and are not walked
 * yet (W2 §3). Sleeps (mutex) — process context only. */
int ane_t6021_csne_submit(struct ane_t6021 *ane, const void *cmd, size_t size);

/* Probe-time one-shot CSNE_CMD_PING on EP1 (W5-live), behind
 * mbi_doorbell=1 only; watches the fw response surfaces for 3 s. */
void ane_t6021_csne_ping_attempt(struct ane_t6021 *ane);

/* W13 firmware loader (ane_t6021_fwload.c): validate + DART-map the
 * selene PRELOAD payload behind fw_load=1. Non-fatal to probe; no boot
 * action (surface publication unevidenced, W13 §6). */
int ane_t6021_fwload_probe(struct ane_t6021 *ane);
void ane_t6021_fwload_remove(struct ane_t6021 *ane);

#endif /* __ANE_T6021_H__ */
