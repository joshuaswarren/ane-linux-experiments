/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
/*
 * ane_t6021_boot.h — T6021 legacy-boot contract units (pure, shared by
 * the kernel sequencer and the userspace regression).
 *
 * Byte anchors (KC kernelcache.release.mac14j sha256 8304156f…, selene
 * sha256 9f7915c4…; receipts under ane-linux-experiments/receipts/,
 * commits 3762aee + 12be074):
 *  - RVBAR fold: ANEHWDevice::ANE_Init 0x95e9850–0x95e9988 (K13
 *    0x93203b0–0x93204e0 identical). Read64 of eng+0x01050000; bit0
 *    set skips the write (live jw14m2 read 0x1). Otherwise write64
 *    ENTRY_BASE | (fw DVA & ADDR_MASK) — single u64 store
 *    (2026-09-20-h14-rvbar-width.json width_proof).
 *  - fw DVA = ANESharedMemorySurfaceParams("FWIM")+0x18, produced by
 *    dartMapMemoryDescriptor (vtable slot 0x8a8, genIOVMSegments) for
 *    the out-param installed at start+0x336c (mapper-callchain audit
 *    pass1–3). Linux correspondence: dma_alloc_coherent on the ane
 *    platform device is dart-ane0-translated (live iommu group 6,
 *    three apple,t6020-dart streams, DMA domain).
 *  - SCRATCH0/1 u64 split: low32 → 0x01840048 first, high32 →
 *    0x0184004c, dsb st before (legacy-init-publication receipt,
 *    accessor write32 width-proven at 0x9622d4c).
 *  - 0x174 init suballocation: header[0x00] u64 = fw DVA (legacy
 *    branch, dev+0x780 bit0 clear = observed AppleARMIODevice
 *    provider), [0x68] u32 = 64 count, template 256 B at
 *    [0x6C,0x16C) with template+0xC0 = 4 RESOLVED (Main raw anchors
 *    0x9612b78/7c/80 on the dev+0x998 template; conditional |=0x10
 *    separate, unqualified, not set).
 *
 * This header intentionally includes nothing. Kernel consumers have
 * <linux/types.h> already; userspace consumers typedef u8/u32/u64 and
 * include <stdbool.h> first (tools/h14_boot_regression.c in this
 * repository is the shipped runnable check).
 */
#ifndef __ANE_T6021_BOOT_H__
#define __ANE_T6021_BOOT_H__

/* RVBAR entry fold (ANE_Init 0x95e9868–0x95e988c). The mask clears
 * bits 0–10, 48 and 55 — bit 11 IS retained (0xf800 keeps 0x800); the
 * base supplies bit0 and the fixed upper pattern. */
#define ANE_T6021_RVBAR_ENTRY_BASE	0x0081000000000001ULL
#define ANE_T6021_RVBAR_ADDR_MASK	0xff7efffffffff800ULL

/* CPU_CONTROL release (rvbar-width local order: write32 0 then 0x10;
 * h14g config selects eng+0x01400044). RUN = BIT(4). */
#define ANE_T6021_CPU_RUN_RELEASE	0x10

/* SCRATCH7 handshake words (InitializeRTBuddy / legacy ANE_Init
 * publication; selene ack writer 0x77c8). */
/* SCRATCH0 request band (pass9-corrected, Main raw trace): post-READY
 * SCRATCH0 >= 0x21 REFUSES the boot preparation; below 0x21 proceeds
 * to the MAX/alloc path. */
#define ANE_T6021_BOOT_IPC_REQ_THRESHOLD	0x21U

#define ANE_T6021_BOOT_WAKE_REQ		0xf7fbdff9U
#define ANE_T6021_BOOT_ACK		0x08042006U

/* Init suballocation geometry (ANE_Init 0x95ea710–0x95ea97c;
 * legacy-init-publication receipt). */
#define ANE_T6021_INIT_STRUCT_SIZE	0x174
#define ANE_T6021_INIT_FW_DVA_OFF	0x00	/* u64, legacy branch */
#define ANE_T6021_INIT_COUNT_OFF	0x68	/* u32 = 64 */
#define ANE_T6021_INIT_COUNT		0x40
#define ANE_T6021_INIT_TEMPLATE_OFF	0x6c	/* 256 B at [0x6C,0x16C) */
#define ANE_T6021_INIT_TEMPLATE_SIZE	0x100
#define ANE_T6021_INIT_TBIT_OFF		0xc0	/* template-relative */
#define ANE_T6021_INIT_TBIT_VAL		0x4	/* RESOLVED (Main raw
					 * anchors 0x9612b78/7c/80:
					 * ldr/orr#4/str on the dev+0x998
					 * template); the conditional
					 * |=0x10 is a separate, still
					 * unqualified mutation and is
					 * NOT set */


static inline u64 ane_t6021_rvbar_compose(u64 iova)
{
	return ANE_T6021_RVBAR_ENTRY_BASE | (iova & ANE_T6021_RVBAR_ADDR_MASK);
}

/* The kext skip condition: bit0 of the RVBAR read (tbnz w0,#0 at
 * ANE_Init 0x95e9878; live jw14m2 reads have been 0x1). What a set
 * bit names in boot-mode terms is the open lifecycle fork — see
 * ane_t6021_boot.c; this predicate only decodes the bit. */
static inline bool ane_t6021_rvbar_latched(u64 rd)
{
	return rd & 1;
}

/* Entry bits of an RVBAR read (what the fold would have named). */
static inline u64 ane_t6021_rvbar_entry_bits(u64 rd)
{
	return rd & ANE_T6021_RVBAR_ADDR_MASK;
}

/* Boot acceptance predicate — the EXACT check the boot path applies
 * to a staged fw DVA: the fold must lose nothing. Bit 11 is retained;
 * bits 0-10, 48 and 55 are not, so an iova with any of them set is
 * rejected rather than silently truncated. */
static inline bool ane_t6021_rvbar_entry_ok(u64 iova)
{
	return (iova & (u64)~ANE_T6021_RVBAR_ADDR_MASK) == 0;
}

/* Publication convention: low32 → SCRATCH0 (0x01840048) first, then
 * high32 → SCRATCH1, after dsb st. */
static inline void ane_t6021_scratch64_split(u64 v, u32 *lo, u32 *hi)
{
	*lo = (u32)(v & 0xffffffffU);
	*hi = (u32)(v >> 32);
}

static inline u64 ane_t6021_scratch64_join(u32 lo, u32 hi)
{
	return ((u64)hi << 32) | lo;
}

/* Linux sources for the init-suballocation fields (pass5b/5c/5d
 * b8b7c35 + pass6c 75a017b; validator tools/check_init_contract.py
 * 68/68). EVERY fw-read field is explicitly sourced from the struct
 * below — nothing is silently zero: [0x00] FWIM DVA, [0x08] 'IPC '
 * surface DVA (Linux alloc, size = ane_t6021_ipc_size), [0x10]
 * config+0x138 = 0x500000, [0x18] = 0x10000000 - size, [0x20] obj2
 * DVA, [0x28] w22, [0x30] fw-load progress, [0x50] zext [x23+4],
 * [0x58] pool DMA base, [0x60] pool word0, [0x68] count 64,
 * template[0x00] = 0, template+0xC0 = 4. The struct values pin BEFORE
 * the preflight gate can open (Main: no unresolved field silently
 * zero; no partial boot). The caller MUST zero the full 0x174 block
 * first (coherent alloc): gaps [0x34..37]/[0x64..67] get no kext
 * store and sit inside fw-read u64 units. */
/* Init-suballocation contract — pass6 producer semantics
 * (rvbar-lifecycle-evidence.json pass6_init_header_producers, commit
 * cd25b46, anchors G1-G26; 87/87 total):
 *
 * STATIC sources (pinned before the preflight can open):
 *   fw_dva      -> [0x00] staged selene ('FWIM') surface DVA,
 *   ipc_dva     -> [0x08] 'IPC ' surface DVA (its size calc remains
 *                  the audit lane's open item),
 *   cfg_size    -> [0x10] config+0x138 = 0x500000; [0x18] =
 *                  0x10000000 - cfg_size = 0x0fb00000,
 *   prev_fw_len -> [0x30] previous fw image length (0 on first boot;
 *                  driver-static, updated on each reload),
 *   heap_floor  -> [0x28] floor = config field dev+0x3A90 (value
 *                  pinned by the audit lane at preflight close),
 *   pool_dma    -> [0x58] the 'DDM ' pool surface DVA (Linux allocates
 *                  its own 0x40000-byte DDM pool — the kext size),
 *   pool_word0  -> [0x60] first qword of the Linux pool-descriptor
 *                  struct. NOT CLOSED: the fw-side consumer of
 *                  pool+0x00 is untraced and the kext never stores it
 *                  (free-list head at manager+0 untouched by
 *                  Allocate). This value is a HARD-GATED source — the
 *                  sequence cannot run until a producer/consumer proof
 *                  pins it; no hypothesis value is shipped.
 *                  PRODUCER OPEN (Main, superseding b21e23f): the
 *                  "pool+0x00 = manager free-list head" claim is
 *                  REJECTED — manager dev+0x968 != Params pool
 *                  dev+0x980 (wrong-object alias likely), and
 *                  Reset6cb048d shows the consumer stores word0
 *                  VERBATIM at image ops 68 (possible extent use).
 *                  Wait for the exact same-Params producer.
 *
 * DYNAMIC inputs (read AFTER poll A — the fw publishes its extra-heap
 * request into SCRATCH3 (cell idx3) and its boot ordinal is
 * SCRATCH1+1; both read from the live cells, never hardcoded):
 *   scratch3_req  -> the fw extra-heap request; 0 = no heap surface,
 *   scratch1_read -> SCRATCH1 read; [0x50] = (u32)read + 1 (boot
 *                    ordinal).
 *
 * TRUST BOUNDARY: scratch3_req is firmware-supplied. The heap size
 * must pass ane_t6021_heap_size() bounds BEFORE any allocation; the
 * heap DVA and size are written to [0x20]/[0x28] only on success. */
struct ane_t6021_init_sources {
	u64 fw_dva;
	u64 ipc_dva;
	u32 cfg_size;
	u32 prev_fw_len;
	u64 heap_floor;
	u64 pool_dma;
	u64 pool_word0;
};

/* 'IPC ' surface size (CURRENT_CONTRACT f9602e0; operands proven:
 * u64[dev+0x3A90] = IODARTMapper::getPageSize() — 0x4000, one 16K
 * DART page, typical; u32[x23+4] = captured SCRATCH1 + 1, the boot
 * ordinal): size = max(page_size, ordinal + 1). Used by the kernel
 * prepare hook to size the 'IPC ' allocation. */
/* SCRATCH0 read-order note (pass9 phase-1: SCRATCH0 then SCRATCH1
 * after READY): Main raw branch proof SUPERSEDES the audit's
 * "SCRATCH0 >= 0x21 arms IPC" reading — 0x95ea1dc b.cc(low) branches
 * TO the MAX+IPC-alloc path and >=0x21 goes to logging/error, so
 * scratch0 < 33 is likely a VALIDITY gate, not an optional-IPC
 * condition. Header [0x08] unconditionally dereferences
 * dev+0x988+0x18. Allocation stays UNCONDITIONAL until Reset corrects
 * the source; the threshold is NOT implemented. */
static inline u64 ane_t6021_ipc_size(u64 page_size, u32 captured)
{
	/* EXACT u32 semantics: the fw-visible ordinal is the captured
	 * SCRATCH1 value + 1 in 32-bit arithmetic (kext add w8,w0,#1) —
	 * it wraps. Callers pass the CAPTURED value, never pre-incremented.
	 * The result is then bounded by ANE_T6021_BOOT_IPC_CEILING at the
	 * allocation site: captured is fw-supplied and untrusted. */
	u32 ord = captured + 1;

	return page_size > (u64)ord ? page_size : (u64)ord;
}

/* Operational ceiling for the fw-influenced 'IPC ' allocation
 * (captured is untrusted; the max() can otherwise be forced to an
 * arbitrary size). Distinct from ABI width — documented budget. */
#define ANE_T6021_BOOT_IPC_CEILING	0x100000ULL	/* 1 MiB */

/* Trust boundary for the firmware-supplied heap request: 0 disables
 * the heap surface; otherwise the size is MAX(request, floor) and is
 * refused (negative) when the request exceeds the ceiling.
 *
 * ANE_T6021_BOOT_HEAP_CEILING is an OPERATIONAL RESOURCE BUDGET, kept
 * distinct from ABI width: header [0x28] is a u64 field and can
 * express far larger values — the u64-ness says nothing about what is
 * safe to allocate. The dart-ane0 vm window only bounds ADDRESSABILITY,
 * not allocation safety, so it is deliberately not used as the
 * ceiling. 32 MiB is the documented budget bounding a firmware-supplied
 * allocation to a size the host can honor without starving; re-anchor
 * to a config field when the h14g blob map lands. */
#define ANE_T6021_BOOT_HEAP_CEILING	0x02000000ULL	/* 32 MiB budget */

static inline long long
ane_t6021_heap_size(u32 scratch3_req, u64 floor, u64 max_size)
{
	u64 req = scratch3_req;

	if (!req)
		return 0;
	if (req > max_size)
		return -E2BIG;
	return (long long)(req > floor ? req : floor);
}

/* Fill the COMPLETE init suballocation from the static sources plus
 * the post-READY dynamic values. The caller MUST zero the full 0x174
 * block first (coherent alloc): the gap bytes [0x34..37]/[0x64..67]
 * get no kext store and sit inside fw-read u64 units. */
static inline void
ane_t6021_init_struct_fill(u8 *buf, const struct ane_t6021_init_sources *s,
			   long long heap_size, u64 heap_dva,
			   u32 boot_ordinal)
{
	u64 size = s->cfg_size;
	int i;

	for (i = 0; i < 8; i++) {
		buf[ANE_T6021_INIT_FW_DVA_OFF + i] =
			(u8)(s->fw_dva >> (8 * i));
		buf[0x08 + i] = (u8)(s->ipc_dva >> (8 * i));
		buf[0x10 + i] = (u8)(size >> (8 * i));
		buf[0x18 + i] = (u8)((0x10000000ULL - size) >> (8 * i));
		buf[0x20 + i] = (u8)(heap_dva >> (8 * i));
		buf[0x50 + i] = (u8)((u64)boot_ordinal >> (8 * i));
		buf[0x58 + i] = (u8)(s->pool_dma >> (8 * i));
		buf[0x60 + i] = (u8)(s->pool_word0 >> (8 * i));
	}

	/* [0x28] u64 heap size (0 when the fw requested none) */
	for (i = 0; i < 8; i++)
		buf[0x28 + i] = (u8)((u64)heap_size >> (8 * i));

	/* [0x30] u32 FULL width: previous fw image length (0 first
	 * boot). Main review: low-byte-only serialization dropped the
	 * upper length bits. */
	buf[0x30] = (u8)s->prev_fw_len;
	buf[0x31] = (u8)(s->prev_fw_len >> 8);
	buf[0x32] = (u8)(s->prev_fw_len >> 16);
	buf[0x33] = (u8)(s->prev_fw_len >> 24);

	buf[ANE_T6021_INIT_COUNT_OFF + 0] = (u8)ANE_T6021_INIT_COUNT;
	buf[ANE_T6021_INIT_COUNT_OFF + 1] = 0;
	buf[ANE_T6021_INIT_COUNT_OFF + 2] = 0;
	buf[ANE_T6021_INIT_COUNT_OFF + 3] = 0;

	/* template[0x00] = config word [dev+0x1D8], pinned value 0
	 * (pass5d); [0x04..0x0B] zero via the caller's zeroing. */
	buf[ANE_T6021_INIT_TEMPLATE_OFF + 0] = 0;
	buf[ANE_T6021_INIT_TEMPLATE_OFF + 1] = 0;
	buf[ANE_T6021_INIT_TEMPLATE_OFF + 2] = 0;
	buf[ANE_T6021_INIT_TEMPLATE_OFF + 3] = 0;

	/* template+0xC0 = 4: RESOLVED initial state (Main raw anchors
	 * 0x9612b78/7c/80). The conditional |=0x10 remains unset. */
	buf[ANE_T6021_INIT_TEMPLATE_OFF + ANE_T6021_INIT_TBIT_OFF + 0] =
		ANE_T6021_INIT_TBIT_VAL;
}

/* ---- Shared prepare-source assembly ----
 *
 * The ALLOCATION-SIZING + HEADER-FILL + PUBLISH-VALUE path used by the
 * kernel prepare hook AND the fake-MMIO trace test — one
 * implementation, so wrong-DVA / double-increment / unbounded-size
 * classes fail in the host trace test instead of only on hardware.
 *
 * Allocation contract: alloc(ctx, size, &iova) is called in the order
 * pool (0x40000), 'IPC ' (max(DART page 0x4000, ordinal+1)), HEAP
 * (0 when the fw requested none); each must return NULL on failure
 * and set *iova to the device-visible address of the returned memory
 * (the DMA address, NOT a recorded constant). Refusal classes: the
 * fw-supplied request and captured value are UNTRUSTED — over-ceiling
 * heap requests and over-budget IPC sizes are refused BEFORE any
 * allocation. */
struct ane_t6021_boot_allocs {
	u64 pool_dva, ipc_dva, heap_dva;
	u64 ipc_size, heap_size;
	void *pool, *ipc, *heap;
};

static inline int
ane_t6021_boot_prepare_publish(const struct ane_t6021_init_sources *s,
			       u32 scratch3_req, u32 scratch0_read,
			       u32 scratch1_read,
			       u64 page_size, u64 ipc_ceiling,
			       u64 heap_ceiling,
			       void *alloc_ctx,
			       void *(*alloc)(void *ctx, u64 size,
					      u64 *iova),
			       struct ane_t6021_boot_allocs *a,
			       u32 *lo, u32 *hi)
{
	int i;

	for (i = 0; i < (int)(sizeof(*a) / sizeof(u64)); i++)
		((u64 *)a)[i] = 0;

	/* SCRATCH0 band check — REFUSAL before allocations/publication
	 * (Main raw trace: >= 0x21 -> 0x95ea2a0 log -> 0x2c4 -> 0x3330
	 * error, w21 = 0xE00002DA; < 0x21 -> 0x214 MAX -> 0x25c alloc ->
	 * 0x260 -> 0x2c8). Boundary: 0x20 accepted, 0x21 refused.
	 * Read order: SCRATCH0 first, then SCRATCH1 (0x95ea0d8/0x95ea100).
	 * Untrusted-input sizing after the band check; heap_size()
	 * returns SIGNED (negative = refused) — kept local so a refusal
	 * cannot wrap into the u64 record. */
	if (scratch0_read >= ANE_T6021_BOOT_IPC_REQ_THRESHOLD)
		return -EPROTO;
	a->ipc_size = ane_t6021_ipc_size(page_size, scratch1_read);
	if (a->ipc_size > ipc_ceiling)
		return -E2BIG;
	{
		long long heap = ane_t6021_heap_size(scratch3_req,
						     s->heap_floor,
						     heap_ceiling);

		if (heap < 0)
			return (int)heap;
		a->heap_size = (u64)heap;
	}

	a->pool = alloc(alloc_ctx, 0x40000, &a->pool_dva);
	if (!a->pool)
		return -ENOMEM;
	a->ipc = alloc(alloc_ctx, a->ipc_size, &a->ipc_dva);
	if (!a->ipc)
		return -ENOMEM;
	if (a->heap_size) {
		a->heap = alloc(alloc_ctx, a->heap_size, &a->heap_dva);
		if (!a->heap)
			return -ENOMEM;
	}

	/* ordinal: exact u32 +1 on the READ SCRATCH1 value (kext add
	 * w8,w0,#1; callers pass the read value, never pre-incremented).
	 * HEADER SOURCES come from the ALLOCATIONS: s->ipc_dva/pool_dma
	 * may be zero in the caller's static sources — fill from the
	 * allocator outputs (a->ipc_dva/a->pool_dva), never from s
	 * (Main review: zero-DVA header bug). */
	{
		struct ane_t6021_init_sources filled = *s;

		filled.ipc_dva = a->ipc_dva;
		filled.pool_dma = a->pool_dva;
		ane_t6021_init_struct_fill(a->pool, &filled, a->heap_size,
					   a->heap_dva,
					   (u32)(scratch1_read + 1));
	}
	*lo = (u32)(a->pool_dva & 0xffffffffU);
	*hi = (u32)(a->pool_dva >> 32);
	return 0;
}

/* Post-DONE SCRATCH1:SCRATCH0 (read SCRATCH1 first, then SCRATCH0)
 * is a fw-produced DEVICE ADDRESS (pass9 phase-2), NOT a return code —
 * never dereference it raw. WHITELIST (Main 2026-09-20): only the
 * Linux-owned FWIM and 'IPC ' windows may ever be matched against it;
 * the 'DDM ' pool is NOT whitelisted. No consumption until range AND
 * length checks are proven; until then the raw u64 is stored and
 * logged only. */

/* ---- Fake-MMIO-testable sequence core ----
 *
 * Register offsets (ENGINE-relative; the Linux driver maps the engine
 * window, so kernel offsets == trace offsets) and the io backend.
 * ane_t6021_boot_run() executes the resolved total order against ANY
 * backend: the kernel wraps readl/writeq/udelay; the host regression
 * wraps a recording fake (trace asserts: full order, no writes when
 * the preflight gate is closed, publish strictly after poll A). */

#define ANE_T6021_BOOT_REG_TABLE0	0x00000b38
#define ANE_T6021_BOOT_REG_TABLE1	0x00000b98
#define ANE_T6021_BOOT_REG_TABLE2	0x00000bf8
#define ANE_T6021_BOOT_REG_RVBAR	0x01050000
#define ANE_T6021_BOOT_REG_CPUCTRL	0x01400044
#define ANE_T6021_BOOT_REG_SCRATCH0	0x01840048
#define ANE_T6021_BOOT_REG_SCRATCH1	0x0184004c
#define ANE_T6021_BOOT_REG_SCRATCH6	0x01840060
#define ANE_T6021_BOOT_REG_SCRATCH7	0x01840064
/* 13.5 stub execution-progress observables (M2StartupRecovery 2026-09-26
 * decode of a9c4b771294a6b11…). Only PROVEN-readable engine-window
 * registers: the 24 MHz domain tick at VM 0x1160008 (watched advancing
 * ~24 MHz post-release, 2026-09-25 handshake receipt) plus SCRATCH,
 * RVBAR and CPU_STATUS already on the whitelist. The stub's VM 0x30c
 * store to engine+0x1140008 is real, but the register's readability,
 * width and reset state are UNPROVEN and no pre-release baseline exists
 * — it is deliberately NOT read here (Main review 2026-09-26). */
#define ANE_T6021_BOOT_REG_TICK		0x01160008
#define ANE_T6021_BOOT_TABLE_VALUE	0x01ff01ffU
#define ANE_T6021_BOOT_TABLE_POLLS	1000

struct ane_t6021_boot_io {
	void *ctx;
	u32 (*rd32)(void *ctx, unsigned int off);
	u64 (*rd64)(void *ctx, unsigned int off);
	void (*wr32)(void *ctx, unsigned int off, u32 v);
	void (*wr64)(void *ctx, unsigned int off, u64 v);
	void (*publish_barrier)(void *ctx); /* orders the coherent fill
					     * before the device publish:
					     * dma_wmb() = dmb oshst on
					     * arm64; NOT claimed as dsb st
					     * (completion) */
	void (*phase)(void *ctx, const char *what); /* bounded phase log:
					     * emitted ONCE before each
					     * write/poll block so a crash
					     * source survives netconsole
					     * (never per-poll) */
	void (*poll_wait)(void *ctx);    /* 1 ms poll delay */
	/* prepare(): called once, strictly AFTER poll A and BEFORE the
	 * SCRATCH0/1 publish; returns the suballoc DVA halves. Kernel
	 * backend: allocate pool/IPC + fill from pinned sources. */
	int (*prepare)(void *ctx, u32 *lo, u32 *hi);
};

struct ane_t6021_boot_cfg {
	int preflight_ok;	/* EVERY prerequisite closed (Main: no
				 * partial boot — the whole sequence or
				 * nothing) */
	int preboot_table_mode;	/* LIVE-FAULT gating of the pre-CPU table
				 * block (2026-09-20 wedge):
				 * 0 = ABORT: -EAGAIN, zero writes
				 *   (accidental-repeat prevention),
				 * 1 = WRITE the table block (re-armed
				 *   after the table-base analysis),
				 * 2 = SKIP the table block, run the rest
				 *   (diagnostic: tests fw-alive without
				 *   the kext pre-CPU config). */
	u64 fw_dva;		/* staged surface DVA (fold input) */
	int rtb_mode;		/* 1 = S1 writes SCRATCH6=0 (RTBuddy/RTKit-app-
				 * endpoint select, fw 0x42c8) instead of 1
				 * (legacy ChMan/MBI). In RTBuddy mode the fw
				 * may skip READY/DONE; listen on mailbox.
				 * Run contract: P4 READY is recorded, not
				 * required; no legacy publish/wake runs;
				 * aliveness is gated by the RTKit HELLO. */
	int stop_after;		/* fw-start-debug step bisect (2026-09-22):
				 * 0 = full run; N in 1..4 = stop AFTER
				 * step N completes, return -ECANCELED
				 * (1 grant tunables, 2 scratch, 3 rvbar,
				 * 4 cpu release + poll A). A poll-A
				 * timeout inside step 4 still returns
				 * -ETIMEDOUT — the timeout is the
				 * answer. Steps complete = writes done;
				 * the stop never splits a step. */
};

/* Ownership: a started CPU may be fetching from the staged surfaces —
 * the DMA memory is NOT reclaimable on failure/remove while
 * cpu_started; reclaimable only via the domain-off reset (reboot). */
static inline int ane_t6021_boot_dma_reclaimable(int cpu_started)
{
	return !cpu_started;
}

/* The cleanup decision the predicate implements: while cpu_started,
 * remove() is HELD (H13 wedged-pin pattern — surfaces, rings, IRQ and
 * power-domain links preserved; reboot reclaims). */
static inline int ane_t6021_boot_remove_held(int cpu_started)
{
	return cpu_started;
}

/* Returns 0 (DONE observed, booted), -ENODATA (preflight closed: ZERO
 * io writes), or -ETIMEDOUT (poll A/B: cpu_started holds, DMA stays
 * unreclaimable, no publish/wake happened on poll A timeout). */
static inline int
ane_t6021_boot_run(const struct ane_t6021_boot_io *io,
		   const struct ane_t6021_boot_cfg *cfg,
		   int *cpu_started, int *fw_alive, int *booted,
		   u64 *scratch_result)
{
	unsigned int i;
	u32 v;
	u64 rvbar;

	*cpu_started = 0;
	*fw_alive = 0;
	*booted = 0;
	*scratch_result = 0;

	/* Main: all gates checked BEFORE any boot write — no partial
	 * sequence when the preflight is closed. */
	if (!cfg->preflight_ok)
		return -ENODATA;

	/* pre-CPU engine table (pass4 receiver, pass5 gate: REQUIRED
	 * every EnableANEClocksAndPower; residual alias/indirect writer
	 * risk documented in the preflight list).
	 * LIVE-FAULT 2026-09-20: this block wedged the machine (P0 then
	 * silence — stall could be the FIRST write; P1 never reached;
	 * hardware reset 16:24:08) — pf_preboot_table_safe gates it
	 * OFF; nothing below runs until re-armed. */
	switch (cfg->preboot_table_mode) {
	case 0:
		return -EAGAIN;	/* BEFORE any write: accidental-repeat
				 * prevention (Main 2026-09-20) */
	case 1:
		io->phase(io->ctx, "P0 preboot-table");
		io->phase(io->ctx, "P0-1 eng+0xb38");
		io->wr32(io->ctx, ANE_T6021_BOOT_REG_TABLE0,
			 ANE_T6021_BOOT_TABLE_VALUE);
		io->phase(io->ctx, "P0-2 eng+0xb98");
		io->wr32(io->ctx, ANE_T6021_BOOT_REG_TABLE1,
			 ANE_T6021_BOOT_TABLE_VALUE);
		io->phase(io->ctx, "P0-3 eng+0xbf8");
		io->wr32(io->ctx, ANE_T6021_BOOT_REG_TABLE2,
			 ANE_T6021_BOOT_TABLE_VALUE);
		break;
	case 2:
	default:
		/* diagnostic skip: NO table writes — tests fw-alive
		 * without the kext pre-CPU config (user override
		 * 2026-09-20). */
		io->phase(io->ctx, "P0 table SKIPPED (diagnostic)");
		break;
	}

	/* P-1: W8 write-grant tunables (proven no-abort class,
	 * w8-run.out: APERTURE_UNLOCKED — 12 engine-aperture writes
	 * preparing the aperture; replayed verbatim).
	 * Per-write before/after discrimination (Main: attempt 3 stalled
	 * LAST phase = P-1, possibly FIRST tunable write). */
	{
		static const struct { u32 off; u32 val; } tun[] = {
			{ 0x000, 0x00000010 }, { 0x038, 0x00050020 },
			{ 0x03c, 0x000a0030 }, { 0x400, 0x40010001 },
			{ 0x600, 0x01ffffff }, { 0x738, 0x00200020 },
			{ 0x798, 0x00100030 }, { 0x7f8, 0x0100000a },
			{ 0x900, 0x00000101 }, { 0x410, 0x00001100 },
			{ 0x420, 0x00001100 }, { 0x430, 0x00001100 },
		};
		unsigned int ti;

		io->phase(io->ctx, "P-1 grant-tunables begin");
		for (ti = 0; ti < sizeof(tun) / sizeof(tun[0]); ti++) {
			io->phase(io->ctx, tun[ti].off == 0x000 ?
				  "P-1a eng+0x000" :
				  tun[ti].off == 0x038 ? "P-1b eng+0x038" :
				  tun[ti].off == 0x03c ? "P-1c eng+0x03c" :
				  tun[ti].off == 0x400 ? "P-1d eng+0x400" :
				  tun[ti].off == 0x600 ? "P-1e eng+0x600" :
				  tun[ti].off == 0x738 ? "P-1f eng+0x738" :
				  tun[ti].off == 0x798 ? "P-1g eng+0x798" :
				  tun[ti].off == 0x7f8 ? "P-1h eng+0x7f8" :
				  tun[ti].off == 0x900 ? "P-1i eng+0x900" :
				  tun[ti].off == 0x410 ? "P-1j eng+0x410" :
				  tun[ti].off == 0x420 ? "P-1k eng+0x420" :
				  "P-1l eng+0x430");
			io->wr32(io->ctx, tun[ti].off, tun[ti].val);
			io->phase(io->ctx, "P-1 write done");
		}
		io->phase(io->ctx, "P-1 grant-tunables end");
	}
	if (cfg->stop_after == 1)
		return -ECANCELED;	/* tunables done, nothing else fired */

	io->phase(io->ctx, "P1 scratch-clear+pulse");
	/* S1: InitANEScratchRegisters — clear ALL cells, SCRATCH6 = rtb_mode ? 0 (RTBuddy) : 1
	 * (legacy ChMan/MBI); pulse SCRATCH7 1 -> 0 (stale cleared). */
	for (i = 0; i < 8; i++)
		io->wr32(io->ctx,
			 ANE_T6021_BOOT_REG_SCRATCH0 + 4 * i, 0);
	io->wr32(io->ctx, ANE_T6021_BOOT_REG_SCRATCH6,
		 cfg->rtb_mode ? 0 : 1);
	io->phase(io->ctx, cfg->rtb_mode ?
		  "P1 S1 SCRATCH6=0 (RTBuddy select)" :
		  "P1 S1 SCRATCH6=1 (legacy ChMan/MBI select)");
	io->wr32(io->ctx, ANE_T6021_BOOT_REG_SCRATCH7, 1);
	io->wr32(io->ctx, ANE_T6021_BOOT_REG_SCRATCH7, 0);
	if (cfg->stop_after == 2)
		return -ECANCELED;	/* scratch programmed, CPU untouched */

	io->phase(io->ctx, "P2 rvbar");
	/* S2: RVBAR skip-or-fold (bit0 set = lawful skip branch; no
	 * latch override, no reset before first attempt). */
	rvbar = io->rd64(io->ctx, ANE_T6021_BOOT_REG_RVBAR);
	if (!ane_t6021_rvbar_latched(rvbar))
		io->wr64(io->ctx, ANE_T6021_BOOT_REG_RVBAR,
			 ane_t6021_rvbar_compose(cfg->fw_dva));
	if (cfg->stop_after == 3)
		return -ECANCELED;	/* entry decision recorded, no RUN */

	io->phase(io->ctx, "P3 cpu-release");
	/* S3: CPU release — both paths, strictly 0 then 0x10. */
	io->wr32(io->ctx, ANE_T6021_BOOT_REG_CPUCTRL, 0);
	io->phase(io->ctx, "P3b cpu-release RUN=0x10");
	io->wr32(io->ctx, ANE_T6021_BOOT_REG_CPUCTRL,
		 ANE_T6021_CPU_RUN_RELEASE);
	*cpu_started = 1;

	io->phase(io->ctx, "P4 pollA-READY");
	/* S4: poll A — FRESH READY (the pulse made it unambiguous).
	 * RTBuddy mode (SCRATCH6=0, kext fw 0x42c8: rtbuddyFW when
	 * SCRATCH6 == 0): the fw does not publish BOOT_ACK to SCRATCH7
	 * and no legacy publication follows — aliveness is gated by the
	 * RTKit HELLO after boot_run returns (selene InitializeRTBuddy
	 * 0x95ead04). A missing READY is recorded, not fatal, and
	 * *fw_alive stays 0 — never fabricated. */
	for (i = 0; i < ANE_T6021_BOOT_TABLE_POLLS; i++) {
		v = io->rd32(io->ctx, ANE_T6021_BOOT_REG_SCRATCH7);
		if (v == ANE_T6021_BOOT_ACK)
			break;
		io->poll_wait(io->ctx);
	}
	if (v == ANE_T6021_BOOT_ACK) {
		*fw_alive = 1;
		io->phase(io->ctx, "P4 pollA READY observed");
	} else if (cfg->rtb_mode) {
		io->phase(io->ctx,
			  "P4 pollA no READY (RTBuddy: HELLO-gated)");
		return 0;	/* RTBuddy: no legacy publish/wake */
	} else {
		return -ETIMEDOUT;
	}
	if (cfg->stop_after == 4)
		return -ECANCELED;	/* fw alive, publish/wake withheld */
	if (cfg->rtb_mode)
		return 0;	/* RTBuddy: no legacy publish/wake */

	io->phase(io->ctx, "P5 prepare+publish");
	/* S5-S6: prepare (alloc/fill; kernel backend owns DMA), then the
	 * publish barrier, then publish suballoc DVA low32/high32, then
	 * wake. Barrier semantics (Main review 2026-09-20): the kernel
	 * backend's dma_wmb() is dmb oshst — it ORDERS the coherent fill
	 * before the device publish; it is NOT the kext's dsb st (which
	 * additionally waits for completion). Ordering suffices for the
	 * Linux coherent-DMA + writel doorbell contract (writel itself
	 * orders prior accesses before the MMIO store); the kext dsb st
	 * choice is a completion guarantee this driver does not claim. */
	{
		u32 lo = 0, hi = 0;
		int err = io->prepare(io->ctx, &lo, &hi);

		if (err)
			return err;
		io->publish_barrier(io->ctx);
		io->wr32(io->ctx, ANE_T6021_BOOT_REG_SCRATCH0, lo);
		io->wr32(io->ctx, ANE_T6021_BOOT_REG_SCRATCH1, hi);
	}
	io->phase(io->ctx, "P6 wake");
	io->wr32(io->ctx, ANE_T6021_BOOT_REG_SCRATCH7,
		 ANE_T6021_BOOT_WAKE_REQ);

	io->phase(io->ctx, "P7 pollB-DONE");
	/* S7: poll B — DONE; read back the SCRATCH0/1 result u64. */
	for (i = 0; i < ANE_T6021_BOOT_TABLE_POLLS; i++) {
		v = io->rd32(io->ctx, ANE_T6021_BOOT_REG_SCRATCH7);
		if (v == ANE_T6021_BOOT_ACK)
			break;
		io->poll_wait(io->ctx);
	}
	if (v != ANE_T6021_BOOT_ACK)
		return -ETIMEDOUT;
	*booted = 1;
	io->phase(io->ctx, "P7 pollB DONE observed");

	/* HANDSHAKE COMPLETE != firmware result success: the DONE ack is
	 * the fw's handshake word; the SCRATCH0/1 result u64 it leaves
	 * behind has UNSOURCED success semantics (pass6: the fw writes a
	 * "result" at 0x77a0 whose meaning is not decoded). Expose it
	 * raw; never infer success from booted alone. */
	*scratch_result =
		((u64)io->rd32(io->ctx, ANE_T6021_BOOT_REG_SCRATCH1) << 32) |
		 io->rd32(io->ctx, ANE_T6021_BOOT_REG_SCRATCH0);
	return 0;
}

/* Pinned 13.5 firmware's eight channel descriptors, captured before ACK.
 * Type 0 is host-to-firmware; type 1 is firmware-to-host.
 * Each ring slot is 64 bytes. The descriptor table uses 256-byte entries. */
#define ANE_T6021_CHMAN_ENTRY_SIZE	0x100
#define ANE_T6021_CHMAN_NAME_LEN	0x40
#define ANE_T6021_CHMAN_COUNT		8
#define ANE_T6021_CHMAN_TOTAL		0x10440

struct ane_t6021_chman_desc {
	char name[ANE_T6021_CHMAN_NAME_LEN];
	u32 type;
	u32 bit;
	u64 size;
	u64 ring;
	u8 pad[ANE_T6021_CHMAN_ENTRY_SIZE - ANE_T6021_CHMAN_NAME_LEN - 0x18];
};

struct ane_t6021_chman_static {
	const char *name;
	u32 type;
	u32 bit;
	u64 size;
	u32 off;	/* ring offset from the IPC DVA */
};

static const struct ane_t6021_chman_static
ane_t6021_chman_layout[ANE_T6021_CHMAN_COUNT] = {
	{ "TERMINAL",       2, 0, 0x300, 0x0800 },
	{ "IO",             0, 1, 0x010, 0xc800 },
	{ "DEBUG",          0, 2, 0x008, 0xcc00 },
	{ "BUF_H2T",        0, 3, 0x040, 0xce00 },
	{ "BUF_T2H",        1, 4, 0x040, 0xde00 },
	{ "SHAREDMALLOC",   1, 5, 0x008, 0xee00 },
	{ "IO_T2H",         1, 6, 0x040, 0xf000 },
	{ "DATA_CHAIN_H2T", 0, 7, 0x010, 0x10000 },
};

/* True when entry i of a table read from the IPC surface matches the
 * static layout with the rings based at ipc_dva. */
static inline bool
ane_t6021_chman_entry_ok(const struct ane_t6021_chman_desc *d,
			 unsigned int i, u64 ipc_dva)
{
	const struct ane_t6021_chman_static *s = &ane_t6021_chman_layout[i];

	return !strncmp(d->name, s->name, ANE_T6021_CHMAN_NAME_LEN) &&
	       d->type == s->type && d->bit == s->bit && d->size == s->size &&
	       d->ring == ipc_dva + s->off;
}

/* Bitmask of mismatching entries (0 = the whole table validated). */
static inline unsigned int
ane_t6021_chman_check(const struct ane_t6021_chman_desc *t, u64 ipc_dva)
{
	unsigned int i, bad = 0;

	for (i = 0; i < ANE_T6021_CHMAN_COUNT; i++)
		if (!ane_t6021_chman_entry_ok(&t[i], i, ipc_dva))
			bad |= 1U << i;
	return bad;
}

/* Before ACK, ownership value 1 prevents firmware from consuming empty H2T slots. */
static inline bool ane_t6021_chman_host_init(void *ipc, u64 size, u64 dva)
{
	unsigned int i, slot;

	if (!ipc || size < ANE_T6021_CHMAN_TOTAL ||
	    dva > ~(u64)0 - ANE_T6021_CHMAN_TOTAL ||
	    ane_t6021_chman_check(ipc, dva))
		return false;
	for (i = 0; i < ANE_T6021_CHMAN_COUNT; i++) {
		const struct ane_t6021_chman_static *s = &ane_t6021_chman_layout[i];

		if (s->type != 0)
			continue;
		for (slot = 0; slot < s->size; slot++) {
			u8 *entry = (u8 *)ipc + s->off + slot * 0x40;

			memset(entry, 0, 24);
			entry[0] = 1;
		}
	}
	return true;
}

#endif /* __ANE_T6021_BOOT_H__ */
