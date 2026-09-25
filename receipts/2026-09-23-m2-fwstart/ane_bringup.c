/* SPDX-License-Identifier: MIT */

/* Boot-time ANE (t6021, m2-host) bring-up inside m1n1, no USB needed.
 *
 * Constant provenance: ane-linux-experiments
 *   scripts/m2-proxyclient/t6021_consts.py (validated) and
 *   receipts/2026-09-21-t6021-host-tm/NIGHT-SUMMARY.md (kext ANE_Init chain).
 * Addresses are CPU-physical as seen from m1n1 stage 1.
 *
 * Global deadline: ANE_TIMEOUT_MS after entry, after which the hook aborts
 * whatever it was doing and lets the normal chainload proceed. m1n1 has no
 * watchdog here; this is the only safety net.
 */

#include "ane_bringup.h"

#include <stdarg.h>

#include "adt.h"
#include "dapf.h"
#include "dart.h"
#include "malloc.h"
#include "pmgr.h"
#include "string.h"
#include "tunables.h"
#include "types.h"
#include "utils.h"
#include "vsprintf.h"
#include "wdt.h"

#define ANE_ENGINE 0x284000000UL
#define ASC_CPU_CONTROL (ANE_ENGINE + 0x1400044)
#define ASC_CPU_STATUS (ANE_ENGINE + 0x1400048)
#define ASC_RVBAR (ANE_ENGINE + 0x1050000)
#define ASC_SCRATCH(i) (ANE_ENGINE + 0x1840000 + 4 * (i))

#define RVBAR_MODE 0x0081000000000001ULL
/* M2Research lane/t6021-research §7.13 kext compose mask */
#define RVBAR_DVA_MASK 0xFF7EFFFFFFFFF800ULL

#define FW_DVA 0x10000000000ULL

/* fw MMU load-base stamp: 64-bit pair at vm 0x423C (file 0x823C), must
 * hold the dart-ane0 IOVA base the image is mapped at (receipt 05a7d8a,
 * B7 recipe; §7.13 obligation 2). */
#define FW_STAMP_OFF 0x423cull
#define FW_STAMP_VAL FW_DVA
/* fw page-table build region for the B8 split discriminator (§7.9) */
#define FW_PT_OFF 0x104000
#define FW_PT_END 0x110000

#define READY_MAGIC 0x08042006u
#define WAKE_MAGIC 0xf7fbdff9u

#define ANE_POLL_MAX 1000
#define ANE_POLL_MS 1
/* global in-hook budget; must stay below the 30 s WDT */
#define ANE_TIMEOUT_MS 20000

/* ASC mailbox (module mirror: ane_t6021.h, W10 live-decoded) */
#define ASC_MBOX_A2I_CTRL (ANE_ENGINE + 0x1408110)
#define ASC_MBOX_I2A_CTRL (ANE_ENGINE + 0x1408114)
#define ASC_MBOX_A2I_SEND0 (ANE_ENGINE + 0x1408800)
#define ASC_MBOX_A2I_SEND1 (ANE_ENGINE + 0x1408808)
#define ASC_MBOX_I2A_RECV0 (ANE_ENGINE + 0x1408830)
#define ASC_MBOX_I2A_RECV1 (ANE_ENGINE + 0x1408838)
#define MBOX_CTRL_EMPTY BIT(17)

/* RTKit EP0 MGMT (ane_t6021.h constants) */
#define RT_TYPE GENMASK(59, 52)
#define RT_MGMT_HELLO 1ull
#define RT_MGMT_HELLO_REPLY 2ull
#define RT_MGMT_STARTEP 5ull
#define RT_MGMT_SET_IOP_PWR_STATE 6ull
#define RT_MGMT_SET_IOP_PWR_STATE_ACK 7ull
#define RT_MGMT_EPMAP 8ull
#define RT_HELLO_MINVER GENMASK(15, 0)
#define RT_HELLO_MAXVER GENMASK(31, 16)
#define RT_EPMAP_LAST BIT(51)
#define RT_EPMAP_BASE GENMASK(34, 32)
#define RT_EPMAP_BITMAP GENMASK(31, 0)
#define RT_EPMAP_REPLY_MORE BIT(0)
#define RT_PWR_STATE GENMASK(15, 0)
#define RT_VER_MIN 11u
#define RT_VER_MAX 12u
#define RT_EP_MGMT_DOORBELL BIT(0)

#define ANE_LOG_SIZE 12288

extern u8 _binary_build_ane_selene_fw_bin_start[];
extern u8 _binary_build_ane_selene_fw_bin_end[];

static char ane_log[ANE_LOG_SIZE];
static size_t ane_log_len;
static u64 ane_deadline_ticks;

#ifndef ANE_BRINGUP_WRITE
#define ANE_BRINGUP_WRITE 0
#endif

static bool ane_expired(void)
{
    return timeout_expired(ane_deadline_ticks);
}

static void alog(const char *fmt, ...)
{
    va_list args;
    char buf[256];
    int n;

    if (ane_log_len + 2 >= ANE_LOG_SIZE)
        return;
    ane_log[ane_log_len++] = '|';

    va_start(args, fmt);
    n = vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    if (n < 0)
        return;
    if ((size_t)n > sizeof(buf) - 1)
        n = sizeof(buf) - 1;
    if (ane_log_len + n >= ANE_LOG_SIZE)
        n = ANE_LOG_SIZE - 1 - ane_log_len;
    memcpy(ane_log + ane_log_len, buf, n);
    ane_log_len += n;
    /* pin: every entry is also on the console so a hang leaves the exact
     * last step visible on the UART */
    printf("ANE: %.*s\n", n, buf);
}

/* log-then-read: the "reading <reg>" pin is committed (buffer + console)
 * BEFORE the MMIO access, so a fabric hang on an unpowered island leaves
 * the guilty register named as the last line. */
static u32 logged_r32(const char *name, u64 addr)
{
    alog("reading %s@%09lx", name, addr);
    u32 v = read32(addr);
    alog("%s=%08x", name, v);
    return v;
}

static u64 logged_r64(const char *name, u64 addr)
{
    alog("reading %s@%09lx", name, addr);
    u64 v = read64(addr);
    alog("%s=%09lx", name, v);
    return v;
}

static u64 ane_wdt_base;

#define ANE_WDT_COUNT 0x10
#define ANE_WDT_ALARM 0x14
#define ANE_WDT_CTL 0x1c
/* m1n1 wdt.c defines WDT_COUNT/ALARM/CTL privately; mirror here (same
 * layout as drivers/watchdog/apple_wdt.c: WD1 block). WD2_BITE_TIME
 * (0x24) is unused by everyone and lives in the same MMIO window; it is
 * our warm-reset-persistent attempt marker. */
#define ANE_WDT2_BITE_TIME 0x24
#define ANE_WDT_MAGIC 0x414e4531u /* "ANE1" */

/* Pure decision: skip the hook when the previous attempt started but
 * never finished (marker left set by a hang or WDT bite). */
static bool ane_should_skip(u32 marker)
{
    return marker == ANE_WDT_MAGIC;
}

static u32 ane_wdt2_read_marker(void)
{
    return read32(ane_wdt_base + ANE_WDT2_BITE_TIME);
}

static void ane_wdt2_write_marker(u32 v)
{
    write32(ane_wdt_base + ANE_WDT2_BITE_TIME, v);
}

/* Arm the primary WDT with a self-calibrated timeout (ticks measured at
 * runtime), as a last-resort escape if an engine access hangs the fabric.
 * NOTE: no sticky reset-reason register is wired yet, so a WDT bite will
 * boot straight back into this hook; the 10 s in-hook deadline already
 * bounds all bounded sections — the WDT covers only unbounded fabric
 * hangs. Arm only around the unbounded-risk window, disarm immediately
 * after. */
static bool ane_wdt_arm(void)
{
    int path[8];
    int node = adt_path_offset_trace(adt, "/arm-io/wdt", path);
    if (node < 0 || adt_get_reg(adt, path, "reg", 0, &ane_wdt_base, NULL))
        return false;

    u32 rate;
    write32(ane_wdt_base + ANE_WDT_COUNT, 0);
    udelay(100000);
    rate = read32(ane_wdt_base + ANE_WDT_COUNT) * 10; /* ticks per second */
    if (!rate || rate > 100000000u)
        rate = 24000000u; /* fallback: 24 MHz */
    u32 alarm = rate * 30;                          /* 30 s */
    if (!alarm)
        return false;
    write32(ane_wdt_base + ANE_WDT_ALARM, alarm);
    write32(ane_wdt_base + ANE_WDT_COUNT, 0);
    write32(ane_wdt_base + ANE_WDT_CTL, 4); /* enable */
    ane_wdt2_write_marker(ANE_WDT_MAGIC);
    alog("wdt armed rate=%u alarm=%u", rate, alarm);
    return true;
}

static void ane_wdt_disarm(void)
{
    if (ane_wdt_base) {
        write32(ane_wdt_base + ANE_WDT_CTL, 0);
        ane_wdt2_write_marker(0);
    }
    alog("wdt disarmed");
}

static void ane_dump_scratch(const char *when)
{
    u32 s[8];
    char nm[3] = "s0";
    alog("dump %s begin", when);
    for (int i = 0; i < 8; i++) {
        nm[1] = '0' + i;
        s[i] = logged_r32(nm, ASC_SCRATCH(i));
    }
    u32 ctl = logged_r32("ctl", ASC_CPU_CONTROL);
    u32 st = logged_r32("st", ASC_CPU_STATUS);
    u64 rv = logged_r64("rvbar", ASC_RVBAR);
    alog("dump %s s0=%08x s1=%08x s2=%08x s3=%08x s4=%08x s5=%08x"
         " s6=%08x s7=%08x ctl=%08x st=%08x rvbar=%09lx",
         when, s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], ctl, st, rv);
}

/* push the staged fw copy to the point of coherence so the ANE CPU's
 * DART-routed fetches see the patch and payload */
static void ane_clean_fw_range(void *fw, size_t len)
{
    u64 line = 64;
    u64 start = ((u64)fw) & ~(line - 1);
    u64 end = (u64)fw + len;
    for (u64 a = start; a < end; a += line)
        __asm__ volatile("dc cvac, %0" ::"r"(a) : "memory");
    __asm__ volatile("dsb sy" ::: "memory");
}

/* B8 split discriminator (M2Research §7.9): scan the staged copy's
 * page-table build region. zero => fw never reached the table builder;
 * nonzero => fw built tables and parked post-MMU. Also re-reads the
 * stamp to verify patcher placement. */
static void ane_split_readback(void *fw)
{
    volatile u32 *pt = (volatile u32 *)((u8 *)fw + FW_PT_OFF);
    size_t words = (FW_PT_END - FW_PT_OFF) / 4;
    size_t nz = 0;
    u32 fo[4] = {0}, fv[4] = {0};
    int nf = 0;
    for (size_t i = 0; i < words; i++) {
        u32 v = pt[i];
        if (v) {
            nz++;
            if (nf < 4) {
                fo[nf] = FW_PT_OFF + i * 4;
                fv[nf] = v;
                nf++;
            }
        }
    }
    u64 stamp = *(volatile u64 *)((u8 *)fw + FW_STAMP_OFF);
    alog("split pt nz=%u %08x:%08x %08x:%08x %08x:%08x %08x:%08x"
         " stamp=%012llx",
         nz, fo[0], fv[0], fo[1], fv[1], fo[2], fv[2], fo[3], fv[3], stamp);
}

static bool ane_poll_ready(const char *name, u32 target)
{
    u32 last_s1 = 0, last_s2 = 0;
    for (int i = 0; i < ANE_POLL_MAX; i++) {
        if (ane_expired()) {
            alog("poll %s abort=deadline", name);
            return false;
        }
        if (read32(ASC_SCRATCH(7)) == target) {
            alog("poll %s tries=%d match=%08x", name, i + 1, target);
            return true;
        }
        /* §7.9: selene writes SCRATCH1=0xc440/SCRATCH2=0x100 pre-READY;
         * log on first appearance (progress proof, no flooding) */
        if (i && !(i % 50)) {
            u32 s1 = read32(ASC_SCRATCH(1));
            u32 s2 = read32(ASC_SCRATCH(2));
            if (s1 != last_s1 || s2 != last_s2) {
                alog("poll %s i=%d s1=%08x s2=%08x", name, i, s1, s2);
                last_s1 = s1;
                last_s2 = s2;
            }
        }
        mdelay(ANE_POLL_MS);
    }
    alog("poll %s tries=%d NOMATCH last=%08x", name, ANE_POLL_MAX,
         read32(ASC_SCRATCH(7)));
    return false;
}

/* ---- ASC mailbox RTKit EP0 MGMT (mirrors ane_t6021_rtkit.c, W10) ---- */

static bool mbox_pending(void)
{
    return !(read32(ASC_MBOX_I2A_CTRL) & MBOX_CTRL_EMPTY);
}

/* pop-on-read: only call while pending; reads both halves */
static u64 mbox_recv(void)
{
    u32 lo = read32(ASC_MBOX_I2A_RECV0);
    u32 hi = read32(ASC_MBOX_I2A_RECV1);
    return ((u64)hi << 32) | lo;
}

/* two 32-bit stores + doorbell, module send contract */
static void mbox_send(u64 msg, u32 doorbell, const char *what)
{
    alog("rt tx %s msg=%016llx db=%x", what, msg, doorbell);
    write32(ASC_MBOX_A2I_SEND0, msg & 0xffffffffu);
    write32(ASC_MBOX_A2I_SEND0 + 4, msg >> 32);
    write32(ASC_MBOX_A2I_SEND1, doorbell);
}

static u32 epmap_seen[8];

static void ane_rtkit_handshake(void)
{
    /* drain any stale word */
    if (mbox_pending())
        alog("rt stale=%016llx", mbox_recv());

    /* fw HELLO (type 1) or silence -> one host HELLO opener (module
     * step 3); version window 11..12 */
    u64 msg = 0;
    u32 ep = 0;
    bool fw_spoke = false, hello_done = false;
    for (int round = 0; round < 2 && !ane_expired(); round++) {
        /* watch up to 3 s */
        u64 waited = 0;
        while (!ane_expired() && waited < 3000) {
            if (mbox_pending())
                break;
            mdelay(50);
            waited += 50;
        }
        if (!mbox_pending())
            break;
        msg = mbox_recv();
        ep = (msg >> 32) & 0xff; /* RECV1 low byte = endpoint */
        u32 type = FIELD_GET(RT_TYPE, msg);
        alog("rt rx ep=%x type=%u msg=%016llx", ep, type, msg);
        fw_spoke = true;
        switch (type) {
        case RT_MGMT_HELLO: {
            u32 min_v = FIELD_GET(RT_HELLO_MINVER, msg);
            u32 max_v = FIELD_GET(RT_HELLO_MAXVER, msg);
            u32 want = max_v < RT_VER_MIN ? RT_VER_MIN
                       : max_v > RT_VER_MAX ? RT_VER_MAX
                                            : max_v;
            alog("rt fw HELLO ver[%u,%u] reply=%u", min_v, max_v, want);
            mbox_send(FIELD_PREP(RT_TYPE, RT_MGMT_HELLO_REPLY) |
                          FIELD_PREP(RT_HELLO_MINVER, want) |
                          FIELD_PREP(RT_HELLO_MAXVER, want),
                      RT_EP_MGMT_DOORBELL, "HELLO_REPLY");
            hello_done = true;
            break;
        }
        case RT_MGMT_HELLO_REPLY:
            alog("rt HELLO_REPLY ver[%u,%u]",
                 FIELD_GET(RT_HELLO_MINVER, msg),
                 FIELD_GET(RT_HELLO_MAXVER, msg));
            hello_done = true;
            break;
        case RT_MGMT_EPMAP: {
            u32 base = FIELD_GET(RT_EPMAP_BASE, msg);
            u32 bmp = FIELD_GET(RT_EPMAP_BITMAP, msg);
            bool last = !!(msg & RT_EPMAP_LAST);
            alog("rt EPMAP base=%u bmp=%08x last=%u", base, bmp, last);
            if (base < 8)
                epmap_seen[base] = bmp;
            mbox_send(FIELD_PREP(RT_TYPE, RT_MGMT_EPMAP) |
                          FIELD_PREP(RT_EPMAP_BASE, base) |
                          (last ? RT_EPMAP_LAST : RT_EPMAP_REPLY_MORE),
                      RT_EP_MGMT_DOORBELL, "EPMAP_REPLY");
            break;
        }
        case RT_MGMT_SET_IOP_PWR_STATE:
            mbox_send(FIELD_PREP(RT_TYPE,
                                 RT_MGMT_SET_IOP_PWR_STATE_ACK) |
                          (msg & RT_PWR_STATE),
                      RT_EP_MGMT_DOORBELL, "IOP_PWR_ACK");
            hello_done = true;
            break;
        default:
            alog("rt fw word type=%u (logged)", type);
            break;
        }
    }
    if (!fw_spoke && !ane_expired()) {
        alog("rt silent 3s; host HELLO opener");
        mbox_send(FIELD_PREP(RT_TYPE, RT_MGMT_HELLO) |
                      FIELD_PREP(RT_HELLO_MINVER, RT_VER_MIN) |
                      FIELD_PREP(RT_HELLO_MAXVER, RT_VER_MAX),
                  RT_EP_MGMT_DOORBELL, "HELLO(host)");
        /* final watch */
        u64 waited = 0;
        while (!ane_expired() && waited < 3000) {
            if (mbox_pending())
                break;
            mdelay(50);
            waited += 50;
        }
        if (mbox_pending()) {
            msg = mbox_recv();
            alog("rt rx-after-opener type=%u msg=%016llx",
                 FIELD_GET(RT_TYPE, msg), msg);
            fw_spoke = true;
        }
    }
    alog("rt session fw_spoke=%u hello=%u epmap=%08x,%08x,%08x,%08x,"
         " %08x,%08x,%08x,%08x",
         fw_spoke, hello_done, epmap_seen[0], epmap_seen[1], epmap_seen[2],
         epmap_seen[3], epmap_seen[4], epmap_seen[5], epmap_seen[6],
         epmap_seen[7]);
}

/* Nine ANE pmgr islands, parents first. Live-confirmed 2026-09-23 on
 * m2-host: each word read ACTUAL=0xf at these CPU-physical addresses.
 * ane_sys is the parent the others sit on, so it is raised too. */
static const struct {
    const char *name;
    u64 addr;
} ane_islands[] = {
    {"ane_sys", 0x28e080260},
    {"ane_cpu", 0x28e0802e0},
    {"ane_sys_mpm", 0x28e084000},
    {"ane_td", 0x28e084008},
    {"ane_base", 0x28e084010},
    {"ane_set1", 0x28e084018},
    {"ane_set2", 0x28e084020},
    {"ane_set3", 0x28e084028},
    {"ane_set4", 0x28e084030},
};

/* TARGET=0xf only. Never TARGET=0, never the RESET bit. A failed poll
 * aborts before any engine-window read. */
static bool ane_raise_islands(void)
{
    for (size_t i = 0; i < sizeof(ane_islands) / sizeof(ane_islands[0]); i++) {
        u32 before = logged_r32(ane_islands[i].name, ane_islands[i].addr);
        alog("raise %s", ane_islands[i].name);
        if (pmgr_set_mode(ane_islands[i].addr, PMGR_PS_ACTIVE)) {
            alog("raise %s FAIL ps=%08x", ane_islands[i].name,
                 read32(ane_islands[i].addr));
            return false;
        }
        u32 after = read32(ane_islands[i].addr);
        u32 actual = (after >> 4) & 0xf;
        alog("island %s before=%08x after=%08x actual=%x",
             ane_islands[i].name, before, after, actual);
        if (actual != 0xf)
            return false;
    }
    return true;
}

void ane_bringup_run(void)
{
    bool wdt = false;
    ane_log_len = 0;
    ane_deadline_ticks = timeout_calculate(ANE_TIMEOUT_MS * 1000);

#if ANE_BRINGUP_WRITE
    alog("mode=write t6021 m2-host");
#else
    alog("mode=dry t6021 m2-host");
#endif

    /* v4 guard: locate the WDT and check the attempt marker. If the
     * previous run started but never finished (hang or WDT bite), skip
     * the hook entirely and let the normal chainload run. */
    {
        int path[8];
        int node = adt_path_offset_trace(adt, "/arm-io/wdt", path);
        if (node >= 0 &&
            adt_get_reg(adt, path, "reg", 0, &ane_wdt_base, NULL) == 0) {
            u32 marker = ane_wdt2_read_marker();
            alog("wdt marker=%08x", marker);
            if (ane_should_skip(marker)) {
                ane_wdt2_write_marker(0);
                alog("hook skipped: reset during previous attempt "
                     "(hang or watchdog bite)");
                alog("END");
                return;
            }
        } else {
            alog("wdt node missing - no skip guard");
        }
    }

    /* step a: ADT presence */
    int an = adt_path_offset(adt, "/arm-io/ane");
    int dn = adt_path_offset(adt, "/arm-io/dart-ane0");
    alog("adt ane=%d dart=%d", an, dn);
    if (an < 0 || dn < 0)
        goto done;
    {
        char compat[64] = "?";
        u32 len = 0;
        const void *p = adt_getprop(adt, an, "compatible", &len);
        if (p && len && len <= sizeof(compat))
            memcpy(compat, p, len), compat[sizeof(compat) - 1] = 0;
        alog("ane compat=%s", compat);
    }

    /* WDT first, before any pmgr or engine access that can hang. */
    wdt = ane_wdt_arm();
    if (!wdt)
        alog("wdt arm FAIL - continuing bounded");

    /* Raise every island and require ACTUAL=0xf before an engine read.
     * The old clock-gates walk only hit virtual gate 473 and left the
     * engine window unpowered; the following scratch read then hung. */
    if (!ane_raise_islands()) {
        alog("islands not all ACTUAL=0xf - no engine read");
        goto done;
    }
    alog("islands up");

    ane_dump_scratch("pre");

#if ANE_BRINGUP_WRITE
    /* §7.13 order: (1) quiesce power-cycle, (2) stage+stamp, (3) dart
     * map, (4) RVBAR with mode bits, (5) RUN + poll + split readback */

    /* step 1: power-cycle ane_cpu itself. The ADT clock-gates walk only
     * hits virtual gate 473 and does not clear the RVBAR latch. TARGET=0
     * then TARGET=0xf, no RESET bit. WDT is already armed. */
    alog("cycle ane_cpu off");
    if (pmgr_set_mode(0x28e0802e0, PMGR_PS_PWRGATE)) {
        alog("ane_cpu off FAIL ps=%08x", read32(0x28e0802e0));
        goto done;
    }
    alog("ane_cpu off ps=%08x", read32(0x28e0802e0));
    alog("cycle ane_cpu on");
    if (pmgr_set_mode(0x28e0802e0, PMGR_PS_ACTIVE)) {
        alog("ane_cpu on FAIL ps=%08x", read32(0x28e0802e0));
        goto done;
    }
    alog("ane_cpu on ps=%08x", read32(0x28e0802e0));

    /* step 2: stage selene into a contiguous carveout, VM layout
     * (TEXT@0, DATA content @0xe8000). The carveout is the FULL VM
     * footprint: __DATA vmsize runs to 0x36c000 (BSS zero-fill) and the
     * config-mandated FWIM surface tail ends at 0x500000
     * (ane_fw_validate.h: FWIM surface = config+0x138 = 0x500000) —
     * staging only the 0x1a0000 file content would fault-park selene on
     * its first BSS/surface access. */
    size_t fw_blob = _binary_build_ane_selene_fw_bin_end -
                     _binary_build_ane_selene_fw_bin_start;
    size_t fw_size = 0x500000;
    void *fw = memalign(SZ_16K, fw_size);
    if (!fw) {
        alog("fw alloc FAIL size=%lx", fw_size);
        goto done;
    }
    memset(fw, 0, fw_size);
    memcpy(fw, _binary_build_ane_selene_fw_bin_start, fw_blob);
    {
        u64 stamp_orig = *(volatile u64 *)((u8 *)fw + FW_STAMP_OFF);
        *(volatile u64 *)((u8 *)fw + FW_STAMP_OFF) = FW_STAMP_VAL;
        alog("stamp vm%04llx %llx -> %llx (blob=%lx carveout=%lx)",
             FW_STAMP_OFF, stamp_orig,
             *(volatile u64 *)((u8 *)fw + FW_STAMP_OFF), fw_blob, fw_size);
    }
    ane_clean_fw_range(fw, fw_size);

    /* step 3: dart-ane0 stream-0 map carveout -> FW_DVA; TTBR shared to
     * reg instances 1/2 (proxyclient ane hack) */
    dart_dev_t *dart = dart_init_adt("/arm-io/dart-ane0", 0, 0, true);
    if (!dart) {
        alog("dart init FAIL");
        goto done;
    }
    alog("dart vm_base=%09lx", dart_vm_base(dart));
    if (dapf_init("/arm-io/dart-ane0", 1))
        alog("dapf init FAIL");
    else
        alog("dapf inst0 ok");
    for (int inst = 1; inst <= 2; inst++) {
        dart_dev_t *dr = dart_init_adt("/arm-io/dart-ane0", inst, 0, true);
        if (!dr) {
            alog("dart inst%d init FAIL", inst);
            continue;
        }
        dart_share_ttbr0(dart, dr);
        alog("dart inst%d ttbr0 shared", inst);
        dart_shutdown(dr);
    }
    if (dart_map(dart, FW_DVA, fw, fw_size)) {
        alog("dart map FAIL dva=%09lx size=%lx", FW_DVA, fw_size);
        dart_shutdown(dart);
        goto done;
    }
    alog("dart map dva=%09lx size=%lx", FW_DVA, fw_size);
    dart_shutdown(dart);

    /* step 4: RVBAR with kext mode bits, write+readback (abort on
     * mismatch — no silent park) */
    u64 rvbar = RVBAR_MODE | (FW_DVA & RVBAR_DVA_MASK);
    (void)logged_r64("rvbar-pre", ASC_RVBAR);
    write64(ASC_RVBAR, rvbar);
    alog("rvbar wr=%09lx", rvbar);
    u64 rvbar_post = logged_r64("rvbar-post", ASC_RVBAR);
    if (rvbar_post != rvbar) {
        alog("rvbar MISMATCH abort");
        goto done;
    }

    /* step 5: CPU_CONTROL 0 -> 0x10 (RUN), poll SCRATCH7 (kext poll A) */
    write32(ASC_CPU_CONTROL, 0);
    logged_r32("ctl-after-0", ASC_CPU_CONTROL);
    write32(ASC_CPU_CONTROL, 0x10);
    logged_r32("ctl-after-10", ASC_CPU_CONTROL);
    if (ane_poll_ready("A-READY", READY_MAGIC)) {
        ane_split_readback(fw);
        ane_dump_scratch("ready");
        /* publish fw DVA then wake, poll B */
        alog("publish s0=%08x s1=%08x wake=%08x", (u32)FW_DVA,
             (u32)(FW_DVA >> 32), WAKE_MAGIC);
        write32(ASC_SCRATCH(0), (u32)FW_DVA);
        write32(ASC_SCRATCH(1), (u32)(FW_DVA >> 32));
        write32(ASC_SCRATCH(7), WAKE_MAGIC);
        if (ane_poll_ready("B-ACK", READY_MAGIC))
            alog("READY-ACK");
        else
            alog("wake NO-ACK st=%08x", read32(ASC_CPU_STATUS));
        /* RTKit EP0 MGMT over the ASC mailbox with a live fw */
        ane_rtkit_handshake();
        ane_split_readback(fw);
        ane_dump_scratch("post");
    } else {
        /* extended 2 s progress watch, then the B8 split readback */
        u64 waited = 0;
        u32 last_s1 = read32(ASC_SCRATCH(1));
        u32 last_s2 = read32(ASC_SCRATCH(2));
        while (!ane_expired() && waited < 2000) {
            mdelay(100);
            waited += 100;
            u32 s1 = read32(ASC_SCRATCH(1));
            u32 s2 = read32(ASC_SCRATCH(2));
            if (s1 != last_s1 || s2 != last_s2) {
                alog("post-poll s1=%08x s2=%08x st=%08x", s1, s2,
                     read32(ASC_CPU_STATUS));
                last_s1 = s1;
                last_s2 = s2;
            }
        }
        logged_r32("ctl-noREADY", ASC_CPU_CONTROL);
        logged_r32("st-noREADY", ASC_CPU_STATUS);
        ane_split_readback(fw);
        ane_dump_scratch("noREADY");
    }
#else
    /* dry: readbacks only, prove the FDT log path */
    alog("dry readbacks only");
#endif

done:
    if (wdt)
        ane_wdt_disarm();
    else if (ane_wdt_base)
        ane_wdt2_write_marker(0);
    ane_dump_scratch("end");
    alog("elapsed=%s", ane_expired() ? "deadline-hit" : "ok");
    alog("END");
}

const char *ane_bringup_log(size_t *len)
{
    if (len)
        *len = ane_log_len;
    return ane_log;
}
