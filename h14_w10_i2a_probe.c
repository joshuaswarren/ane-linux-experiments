// SPDX-License-Identifier: MIT
/* H14/W10 i2a receive-path probe — READ-ONLY on the ANE aperture.
 *
 * W9 left the send class (a2i_wr +0x1850000/4 + doorbell +0x1844000)
 * host-write-fatal behind the W8 grant, and the lane never mapped the
 * firmware->host direction at all.  This probe maps it, reading only.
 *
 * Two questions, in ladder order:
 *
 *  Q1  Is +0x1170000/4 — which the driver calls "fw->host u64 message
 *      pair" and which W6/W9 called a type-0 heartbeat — actually a
 *      message surface, or a free-running counter?  W9 captured
 *      i2a=0x0000000bb53eb904 = 50 285 426 948 at kernel t=2059.7 s;
 *      divided by the 24 MHz Apple timebase that is 2095 s, i.e. box
 *      uptime plus the usual pre-Linux m1n1/iBoot offset.  If the pair
 *      advances 1:1 with CNTVCT_EL0 it is a timebase, not a mailbox,
 *      and the "firmware heartbeat" that the fw-first hypothesis rests
 *      on does not exist.  Phase `tick` settles this with no new
 *      addresses at all.
 *
 *  Q2  Where is the real receive path?  The ANE DT node carries no
 *      mailbox (reg-names = engine/pmgr/set, one IRQ named "ane"), but
 *      every sibling ASC on this live SoC does: mbox@2a2408000 is
 *      "apple,t6020-asc-mailbox" / "apple,asc-mailbox-v4", reg size
 *      0x4000, IRQs send-empty/send-not-empty/recv-empty/recv-not-empty
 *      — i.e. mailbox = asc_base + 0x8000.  The ANE kext builds
 *      CPU_CONTROL 0x1400044 / CPU_STATUS 0x1400048, the Apple ASC
 *      +0x44/+0x48 pair, so ANE's ASC base is ANE+0x1400000 and its
 *      mailbox should be ANE+0x1408000 = 0x285408000 — which matches
 *      the sibling naming exactly (…408000).
 *
 * Register offsets are upstream, not guessed: drivers/soc/apple/mailbox.c
 * apple_mbox_asc_hw — a2i_control 0x110, i2a_control 0x114, i2a_recv0
 * 0x830, i2a_recv1 0x838, CONTROL_FULL BIT(16), CONTROL_EMPTY BIT(17).
 * Receive is "while !(i2a_control & EMPTY): readq(recv0); readq(recv1)".
 *
 * C, not Python: recv0/recv1 are 64-bit POP-ON-READ ports.
 * struct.unpack_from() on an mmap goes through memcpy, and glibc's
 * aarch64 memcpy issues TWO 8-byte loads for an 8-byte copy — that
 * would pop the FIFO twice and silently eat a message.  A volatile u64
 * load is one LDR.
 *
 * Safety: every access is logged to /dev/kmsg (netconsole-carried)
 * BEFORE it issues, so a hard abort pins the exact word.  A SIGBUS
 * handler catches synchronous external aborts, so a register that
 * simply does not decode is survivable evidence rather than a box kill;
 * only a fabric-level SError takes the machine.
 *
 * Build on-box:  gcc -O2 -Wall -o h14_w10_i2a_probe h14_w10_i2a_probe.c
 * Run:           sudo ./h14_w10_i2a_probe <phase>
 *   tick     Q1: +0x1170000/4 vs CNTVCT_EL0, 24 samples + burst
 *   surface  proven-safe read set, 3 passes, diffed
 *   asc      Q2 rung 1: ASC CPU_CONTROL/CPU_STATUS/flags
 *   mbox     Q2 rung 2: ASC mailbox a2i_control/i2a_control
 *   watch    poll i2a_control for new fw messages
 *   pop      drain the i2a FIFO by reading recv0/recv1 (reads only)
 *   akf      0x4000-stride walk of the MBI block (fallback map)
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <setjmp.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define ANE_BASE	0x284000000UL
#define KILL_LO		0x285C04000UL	/* t8103 "engine" window: fatal here */
#define KILL_HI		0x285C28000UL

/* W10 run 1 (13:53:59, netconsole [1812.145753]) pre-logged
 * "akf.pre 0x285854000", never printed a value, and the box took a
 * watchdog reset — a READ of ANE+0x1854000 is fabric-fatal.  The
 * SIGBUS guard cannot catch that class (it is an async external abort,
 * not a synchronous data abort), so that address and its untested
 * neighbour up to the kill window are refused outright.
 */
#define FATAL_LO	0x285854000UL
#define FATAL_HI	0x285C04000UL

/* proven-safe surfaces (W2/W3/W8/W9 read these live) */
#define I2A_LO		0x1170000
#define I2A_HI		0x1170004
#define RVBAR		0x1050000
#define VERS		0x1840000
#define SCRATCH0	0x1840048
#define RTB_7C		0x184007c
#define RTB_STATUS	0x1840088
#define DOORBELL	0x1844000
#define A2I_RD		0x184c000
#define A2I_WR		0x1850000

/* ASC block (kext config blob: dev+0x4a0 / dev+0x49c build 0x1400044/48) */
#define ASC		0x1400000
#define ASC_FLAGS	(ASC + 0x40)
#define ASC_CPU_CONTROL	(ASC + 0x44)
#define ASC_CPU_STATUS	(ASC + 0x48)

/* ASC mailbox — drivers/soc/apple/mailbox.c apple_mbox_asc_hw, verbatim */
#define MBOX		(ASC + 0x8000)
#define MBOX_A2I_CTRL	(MBOX + 0x110)
#define MBOX_A2I_SEND0	(MBOX + 0x800)
#define MBOX_A2I_SEND1	(MBOX + 0x808)
#define MBOX_A2I_RECV0	(MBOX + 0x810)
#define MBOX_A2I_RECV1	(MBOX + 0x818)
#define MBOX_I2A_CTRL	(MBOX + 0x114)
#define MBOX_I2A_SEND0	(MBOX + 0x820)
#define MBOX_I2A_SEND1	(MBOX + 0x828)
#define MBOX_I2A_RECV0	(MBOX + 0x830)
#define MBOX_I2A_RECV1	(MBOX + 0x838)

#define CTRL_FULL	(1u << 16)
#define CTRL_EMPTY	(1u << 17)

static int kmsg_fd = -1;

static void klog(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

static void klog(const char *fmt, ...)
{
	char buf[512];
	va_list ap;
	int n;

	va_start(ap, fmt);
	n = vsnprintf(buf, sizeof(buf) - 2, fmt, ap);
	va_end(ap);
	if (n < 0)
		return;
	buf[n] = '\n';
	buf[n + 1] = '\0';
	if (kmsg_fd >= 0) {
		ssize_t w = write(kmsg_fd, buf, n + 1);
		(void)w;
	}
	fputs(buf, stdout);
	fflush(stdout);
}

/* ---- SIGBUS guard: a non-decoding register should cost us a line of
 * evidence, not the machine.  Only an async fabric SError escapes. ---- */
static sigjmp_buf fault_env;
static volatile sig_atomic_t in_guard;
static volatile sig_atomic_t fault_hits;

static void sigbus_handler(int sig)
{
	if (in_guard) {
		fault_hits++;
		siglongjmp(fault_env, sig);
	}
	_exit(135);
}

static void install_guard(void)
{
	struct sigaction sa;

	memset(&sa, 0, sizeof(sa));
	sa.sa_handler = sigbus_handler;
	sa.sa_flags = SA_NODEFER;
	sigemptyset(&sa.sa_mask);
	sigaction(SIGBUS, &sa, NULL);
	sigaction(SIGSEGV, &sa, NULL);
}

static uint64_t cntvct(void)
{
	uint64_t v;

	__asm__ volatile("isb; mrs %0, cntvct_el0" : "=r"(v) :: "memory");
	return v;
}

static uint64_t cntfrq(void)
{
	uint64_t v;

	__asm__ volatile("mrs %0, cntfrq_el0" : "=r"(v));
	return v;
}

static int mem_fd = -1;
static unsigned char *win;
static unsigned long win_base, win_len;

static void map_window(unsigned long base, unsigned long len)
{
	long ps = sysconf(_SC_PAGESIZE);
	unsigned long b = base & ~((unsigned long)ps - 1);
	unsigned long e = (base + len + ps - 1) & ~((unsigned long)ps - 1);

	mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (mem_fd < 0) {
		perror("open /dev/mem");
		exit(1);
	}
	win = mmap(NULL, e - b, PROT_READ | PROT_WRITE, MAP_SHARED, mem_fd,
		   (off_t)b);
	if (win == MAP_FAILED) {
		perror("mmap");
		exit(1);
	}
	win_base = b;
	win_len = e - b;
}

static volatile void *at(unsigned int off)
{
	unsigned long pa = ANE_BASE + off;

	if (pa >= KILL_LO && pa < KILL_HI) {
		fprintf(stderr, "refusing kill-window address %#lx\n", pa);
		exit(2);
	}
	if (pa >= FATAL_LO && pa < FATAL_HI) {
		fprintf(stderr,
			"refusing %#lx: W10 run 1 took a watchdog reset reading 0x285854000\n",
			pa);
		exit(2);
	}
	if (pa < win_base || pa + 8 > win_base + win_len) {
		fprintf(stderr, "address %#lx outside mapped window\n", pa);
		exit(2);
	}
	return (volatile void *)(win + (pa - win_base));
}

/* Logged read: the klog line is flushed BEFORE the load issues, so an
 * async external abort pins the exact register that killed the box.
 * Returns 0 on success, -1 if the load took SIGBUS (val untouched). */
static int rd32(const char *name, unsigned int off, uint32_t *out)
{
	volatile uint32_t *p = at(off);
	uint32_t v;

	klog("H14W10 {\"ev\":\"rd32.pre\",\"name\":\"%s\",\"addr\":\"%#lx\"}",
	     name, ANE_BASE + off);
	in_guard = 1;
	if (sigsetjmp(fault_env, 1)) {
		in_guard = 0;
		klog("H14W10 {\"ev\":\"rd32.FAULT\",\"name\":\"%s\",\"addr\":\"%#lx\",\"signal\":\"SIGBUS/SEGV\"}",
		     name, ANE_BASE + off);
		return -1;
	}
	v = *p;
	in_guard = 0;
	klog("H14W10 {\"ev\":\"rd32\",\"name\":\"%s\",\"addr\":\"%#lx\",\"val\":\"%#010x\"}",
	     name, ANE_BASE + off, v);
	if (out)
		*out = v;
	return 0;
}

static int rd64(const char *name, unsigned int off, uint64_t *out)
{
	volatile uint64_t *p = at(off);
	uint64_t v;

	klog("H14W10 {\"ev\":\"rd64.pre\",\"name\":\"%s\",\"addr\":\"%#lx\"}",
	     name, ANE_BASE + off);
	in_guard = 1;
	if (sigsetjmp(fault_env, 1)) {
		in_guard = 0;
		klog("H14W10 {\"ev\":\"rd64.FAULT\",\"name\":\"%s\",\"addr\":\"%#lx\",\"signal\":\"SIGBUS/SEGV\"}",
		     name, ANE_BASE + off);
		return -1;
	}
	v = *p;
	in_guard = 0;
	klog("H14W10 {\"ev\":\"rd64\",\"name\":\"%s\",\"addr\":\"%#lx\",\"val\":\"%#018llx\"}",
	     name, ANE_BASE + off, (unsigned long long)v);
	if (out)
		*out = v;
	return 0;
}

/* quiet read for the sampling loops (proven-safe offsets only) */
static uint32_t q32(unsigned int off)
{
	return *(volatile uint32_t *)at(off);
}

/* ---- phases ---- */

/* Q1.  A message register holds still between messages; a counter never
 * does.  If d_i2a == d_cntvct on every interval, the pair is the 24 MHz
 * timebase and the "heartbeat" is an artifact. */
static void phase_tick(void)
{
	const int n = 24;
	uint64_t frq = cntfrq();
	uint64_t prev_v = 0, prev_t = 0;
	uint64_t first_v = 0, first_t = 0;
	int i, locked = 0, moved = 0;

	klog("H14W10 {\"ev\":\"tick.begin\",\"cntfrq\":%llu,\"samples\":%d,\"cadence_ms\":100,\"addr_lo\":\"%#lx\",\"addr_hi\":\"%#lx\"}",
	     (unsigned long long)frq, n, ANE_BASE + I2A_LO, ANE_BASE + I2A_HI);

	for (i = 0; i < n; i++) {
		uint64_t t, hi1, lo, hi2, v;

		t = cntvct();
		hi1 = q32(I2A_HI);
		lo = q32(I2A_LO);
		hi2 = q32(I2A_HI);
		if (hi1 != hi2)		/* wrapped mid-read: re-read lo */
			lo = q32(I2A_LO);
		v = (hi2 << 32) | lo;

		if (i == 0) {
			first_v = v;
			first_t = t;
			klog("H14W10 {\"ev\":\"tick\",\"i\":%d,\"i2a\":\"%016llx\",\"hi\":\"%08llx\",\"lo\":\"%08llx\",\"cntvct\":%llu,\"rtkit_type\":%llu}",
			     i, (unsigned long long)v, (unsigned long long)hi2,
			     (unsigned long long)lo, (unsigned long long)t,
			     (unsigned long long)((v >> 52) & 0xff));
		} else {
			uint64_t dv = v - prev_v, dt = t - prev_t;

			if (dv == dt)
				locked++;
			if (dv)
				moved++;
			klog("H14W10 {\"ev\":\"tick\",\"i\":%d,\"i2a\":\"%016llx\",\"hi\":\"%08llx\",\"lo\":\"%08llx\",\"cntvct\":%llu,\"rtkit_type\":%llu,\"d_i2a\":%llu,\"d_cnt\":%llu,\"skew\":%lld,\"locked\":%d}",
			     i, (unsigned long long)v, (unsigned long long)hi2,
			     (unsigned long long)lo, (unsigned long long)t,
			     (unsigned long long)((v >> 52) & 0xff),
			     (unsigned long long)dv, (unsigned long long)dt,
			     (long long)dv - (long long)dt, dv == dt);
		}
		prev_v = v;
		prev_t = t;
		usleep(100000);
	}

	klog("H14W10 {\"ev\":\"tick.summary\",\"intervals\":%d,\"moved\":%d,\"phase_locked_to_cntvct\":%d,\"total_d_i2a\":%llu,\"total_d_cnt\":%llu,\"implied_uptime_s\":%llu,\"verdict\":\"%s\"}",
	     n - 1, moved, locked,
	     (unsigned long long)(prev_v - first_v),
	     (unsigned long long)(prev_t - first_t),
	     (unsigned long long)(frq ? prev_v / frq : 0),
	     locked >= (n - 1) - 1 ? "FREE_RUNNING_TIMEBASE_NOT_MAILBOX"
				   : "NOT_TIMEBASE_LOCKED");

	/* burst: eight back-to-back samples, no sleep. */
	klog("H14W10 {\"ev\":\"burst.begin\"}");
	for (i = 0; i < 8; i++) {
		uint64_t t = cntvct();
		uint64_t v = ((uint64_t)q32(I2A_HI) << 32) | q32(I2A_LO);

		klog("H14W10 {\"ev\":\"burst\",\"i\":%d,\"i2a\":\"%016llx\",\"cntvct\":%llu}",
		     i, (unsigned long long)v, (unsigned long long)t);
	}
}

struct reg { const char *name; unsigned int off; };

static const struct reg surface[] = {
	{ "rvbar",	RVBAR },
	{ "i2a_lo",	I2A_LO },
	{ "i2a_hi",	I2A_HI },
	{ "i2a+8",	I2A_LO + 8 },
	{ "i2a+c",	I2A_LO + 12 },
	{ "vers",	VERS },
	{ "scratch0",	SCRATCH0 + 0 },
	{ "scratch1",	SCRATCH0 + 4 },
	{ "scratch2",	SCRATCH0 + 8 },
	{ "scratch3",	SCRATCH0 + 12 },
	{ "scratch4",	SCRATCH0 + 16 },
	{ "scratch5",	SCRATCH0 + 20 },
	{ "scratch6",	SCRATCH0 + 24 },
	{ "scratch7",	SCRATCH0 + 28 },
	{ "rtb_70",	0x1840070 },
	{ "rtb_74",	0x1840074 },
	{ "rtb_78",	0x1840078 },
	{ "rtb_7c",	RTB_7C },
	{ "rtb_status",	RTB_STATUS },
	{ "doorbell",	DOORBELL },
	{ "doorbell+4",	DOORBELL + 4 },
	{ "a2i_rd",	A2I_RD },
	{ "a2i_rd+4",	A2I_RD + 4 },
	{ "a2i_wr",	A2I_WR },
	{ "a2i_wr+4",	A2I_WR + 4 },
};
#define NSURF (int)(sizeof(surface) / sizeof(surface[0]))

static void phase_surface(void)
{
	uint32_t pass[3][NSURF];
	int p, i;

	for (p = 0; p < 3; p++) {
		klog("H14W10 {\"ev\":\"surface.pass\",\"p\":%d,\"cntvct\":%llu}",
		     p, (unsigned long long)cntvct());
		for (i = 0; i < NSURF; i++) {
			if (p == 0)
				klog("H14W10 {\"ev\":\"surface.pre\",\"name\":\"%s\",\"addr\":\"%#lx\"}",
				     surface[i].name,
				     ANE_BASE + surface[i].off);
			pass[p][i] = q32(surface[i].off);
		}
		if (p < 2)
			usleep(1000000);
	}
	for (i = 0; i < NSURF; i++)
		klog("H14W10 {\"ev\":\"surface\",\"name\":\"%s\",\"addr\":\"%#lx\",\"p0\":\"%08x\",\"p1\":\"%08x\",\"p2\":\"%08x\",\"changed\":%d}",
		     surface[i].name, ANE_BASE + surface[i].off,
		     pass[0][i], pass[1][i], pass[2][i],
		     (pass[0][i] != pass[1][i] || pass[1][i] != pass[2][i]));
}

static void phase_asc(void)
{
	uint32_t ctl = 0, st = 0;

	klog("H14W10 {\"ev\":\"asc.begin\",\"base\":\"%#lx\",\"note\":\"ASC block first touch this lane\",\"src\":\"m1n1 proxyclient/m1n1/hw/asc.py ASCRegs\"}",
	     ANE_BASE + ASC);
	rd32("asc_flags40", ASC_FLAGS, NULL);
	if (rd32("asc_cpu_control", ASC_CPU_CONTROL, &ctl) == 0)
		klog("H14W10 {\"ev\":\"asc.cpu_control.decode\",\"raw\":\"%#010x\",\"RUN\":%u}",
		     ctl, (ctl >> 4) & 1);
	if (rd32("asc_cpu_status", ASC_CPU_STATUS, &st) == 0)
		klog("H14W10 {\"ev\":\"asc.cpu_status.decode\",\"raw\":\"%#010x\",\"RUNNING\":%u,\"STOPPED\":%u,\"IRQ_NOT_PEND\":%u,\"FIQ_NOT_PEND\":%u,\"IDLE\":%u,\"m1n1_is_running\":%u}",
		     st, st & 1, (st >> 1) & 1, (st >> 2) & 1, (st >> 3) & 1,
		     (st >> 5) & 1, !((st >> 1) & 1));
}

/* R_MBOX_CTRL, m1n1 proxyclient/m1n1/hw/asc.py:
 *   FIFOCNT 23:20, OVERFLOW 18, EMPTY 17, FULL 16,
 *   RPTR 15:12, WPTR 11:8, ENABLE 0 */
static void ctrl_decode(const char *name, uint32_t v)
{
	klog("H14W10 {\"ev\":\"mbox.ctrl.decode\",\"name\":\"%s\",\"raw\":\"%#010x\",\"ENABLE\":%u,\"FULL\":%u,\"EMPTY\":%u,\"OVERFLOW\":%u,\"FIFOCNT\":%u,\"WPTR\":%u,\"RPTR\":%u}",
	     name, v, v & 1, !!(v & CTRL_FULL), !!(v & CTRL_EMPTY),
	     (v >> 18) & 1, (v >> 20) & 0xf, (v >> 8) & 0xf, (v >> 12) & 0xf);
}

static void phase_mbox(void)
{
	uint32_t a2i = 0, i2a = 0;

	klog("H14W10 {\"ev\":\"mbox.begin\",\"base\":\"%#lx\",\"src\":\"drivers/soc/apple/mailbox.c apple_mbox_asc_hw; live DT mbox@2a2408000 = apple,asc-mailbox-v4 at asc+0x8000\"}",
	     ANE_BASE + MBOX);
	if (rd32("i2a_control", MBOX_I2A_CTRL, &i2a) == 0)
		ctrl_decode("i2a_control", i2a);
	if (rd32("a2i_control", MBOX_A2I_CTRL, &a2i) == 0)
		ctrl_decode("a2i_control", a2i);
	klog("H14W10 {\"ev\":\"mbox.end\",\"faults\":%d}", (int)fault_hits);
}

static void phase_watch(int secs)
{
	uint32_t prev = 0;
	int i, n = secs * 20;

	if (rd32("i2a_control", MBOX_I2A_CTRL, &prev) < 0) {
		klog("H14W10 {\"ev\":\"watch.abort\",\"reason\":\"i2a_control does not decode\"}");
		return;
	}
	klog("H14W10 {\"ev\":\"watch.begin\",\"secs\":%d,\"i2a_control\":\"%#010x\"}",
	     secs, prev);
	for (i = 0; i < n; i++) {
		uint32_t cur;

		usleep(50000);
		cur = *(volatile uint32_t *)at(MBOX_I2A_CTRL);
		if (cur != prev) {
			klog("H14W10 {\"ev\":\"watch.change\",\"ms\":%d,\"from\":\"%#010x\",\"to\":\"%#010x\"}",
			     i * 50, prev, cur);
			prev = cur;
		}
	}
	klog("H14W10 {\"ev\":\"watch.end\",\"i2a_control\":\"%#010x\"}", prev);
}

/* The only "response" this lane makes: pop what the firmware already
 * queued.  Both accesses are READS — the AKF receive port advances the
 * FIFO on the recv1 read.  No host message, no doorbell. */
static void phase_pop(void)
{
	uint32_t ctrl = 0;
	int n = 0;

	if (rd32("i2a_control", MBOX_I2A_CTRL, &ctrl) < 0) {
		klog("H14W10 {\"ev\":\"pop.abort\",\"reason\":\"i2a_control does not decode; nothing to pop\"}");
		return;
	}
	ctrl_decode("i2a_control", ctrl);
	if (ctrl & CTRL_EMPTY) {
		klog("H14W10 {\"ev\":\"pop.skip\",\"reason\":\"EMPTY set: firmware has queued nothing\"}");
		return;
	}
	while (!(ctrl & CTRL_EMPTY) && n < 16) {
		uint64_t m0 = 0, m1 = 0;

		klog("H14W10 {\"ev\":\"pop.begin\",\"n\":%d}", n);
		if (rd64("i2a_recv0", MBOX_I2A_RECV0, &m0) < 0)
			break;
		if (rd64("i2a_recv1", MBOX_I2A_RECV1, &m1) < 0)
			break;
		klog("H14W10 {\"ev\":\"pop.msg\",\"n\":%d,\"msg0\":\"%016llx\",\"msg1\":\"%08llx\",\"ep\":%llu,\"type\":%llu,\"outcnt\":%llu,\"incnt\":%llu}",
		     n, (unsigned long long)m0,
		     (unsigned long long)(m1 & 0xffffffffULL),
		     (unsigned long long)(m1 & 0xff),
		     (unsigned long long)((m0 >> 52) & 0xff),
		     (unsigned long long)((m1 >> 52) & 0x1f),
		     (unsigned long long)((m1 >> 48) & 0xf));
		n++;
		if (rd32("i2a_control", MBOX_I2A_CTRL, &ctrl) < 0)
			break;
		ctrl_decode("i2a_control(after pop)", ctrl);
	}
	klog("H14W10 {\"ev\":\"pop.end\",\"popped\":%d,\"i2a_control\":\"%#010x\"}",
	     n, ctrl);
	phase_watch(5);
}

/* Fallback map if the ASC mailbox does not decode: the MBI registers the
 * lane inherited are all multiples of 0x4000 inside one region.  Walk the
 * stride outward from the proven ones, pre-logging every word, so an
 * abort names the sub-block that owns it. */
static void phase_akf(void)
{
	static const unsigned int blocks[] = {
		0x1840000, 0x1844000, 0x184c000, 0x1850000,	/* proven */
		0x1848000,					/* new */
	};
	unsigned int b, o;
	size_t i;

	klog("H14W10 {\"ev\":\"akf.begin\",\"note\":\"0x4000 stride walk, proven blocks first\"}");
	for (i = 0; i < sizeof(blocks) / sizeof(blocks[0]); i++) {
		b = blocks[i];
		klog("H14W10 {\"ev\":\"akf.block\",\"base\":\"%#lx\",\"proven\":%d}",
		     ANE_BASE + b, i < 4);
		for (o = 0; o < 0x20; o += 4) {
			char nm[32];

			snprintf(nm, sizeof(nm), "akf+%#x", b + o);
			rd32(nm, b + o, NULL);
		}
	}
	klog("H14W10 {\"ev\":\"akf.end\",\"faults\":%d}", (int)fault_hits);
}

int main(int argc, char **argv)
{
	const char *phase = argc > 1 ? argv[1] : "tick";

	kmsg_fd = open("/dev/kmsg", O_WRONLY);
	install_guard();
	map_window(ANE_BASE, 0x1900000);
	klog("H14W10 {\"ev\":\"run.begin\",\"phase\":\"%s\",\"map\":\"%#lx+%#lx\"}",
	     phase, win_base, win_len);

	if (!strcmp(phase, "tick"))
		phase_tick();
	else if (!strcmp(phase, "surface"))
		phase_surface();
	else if (!strcmp(phase, "asc"))
		phase_asc();
	else if (!strcmp(phase, "mbox"))
		phase_mbox();
	else if (!strcmp(phase, "watch"))
		phase_watch(argc > 2 ? atoi(argv[2]) : 5);
	else if (!strcmp(phase, "pop"))
		phase_pop();
	else if (!strcmp(phase, "akf"))
		phase_akf();
	else {
		fprintf(stderr, "unknown phase %s\n", phase);
		return 2;
	}

	klog("H14W10 {\"ev\":\"run.end\",\"phase\":\"%s\",\"faults\":%d}",
	     phase, (int)fault_hits);
	return 0;
}
