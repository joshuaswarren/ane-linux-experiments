/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
#ifndef ANE_T6021_DIAG_MARKER_H
#define ANE_T6021_DIAG_MARKER_H

/* Laboratory execution marker, NOT firmware READY or functional ANE.
 *
 * REPLACED 2026-09-27 (Main directive, M2StartupRecovery): the previous
 * marker stored to the SCRATCH7 MMIO register (0x285840064) pre-MMU — a
 * missing value there could not distinguish "no fetch" from "the MMIO
 * access itself faulted". The marker now stores 0x4d325431 into the OWNED
 * staged DMA buffer at offset 0xe0000 (the boot-PT window head, documented
 * unused at bootstrap time), then DSB and self-loop — no MMIO access at
 * all. The reader is the existing FW-PT readback (host-side coherent read
 * of fw_buf 0xe0000); the staged-buffer word at offset 0xe0000 IS the
 * marker result.
 *
 * Position independent: adr x0, #0 captures the runtime load base
 * (pre-MMU PC-relative, any load base), then +0xe0000 selects the staged
 * offset through the entry alias mapping (entry+0xe0000 -> staged page
 * 0xe0000). Byte-verified with Capstone against the 13.5 image.
 *
 * At VM 0x204 (replacing the first 8 stub instructions; eret at 0x228 is
 * never reached):
 *   adr  x0, #0                 ; x0 = runtime VM 0 (load base)
 *   add  x0, x0, #0xe0, lsl #12 ; x0 = staged offset 0xe0000
 *   movz w1, #0x5431
 *   movk w1, #0x4d32, lsl #16   ; w1 = 0x4d325431 ("M2T1")
 *   str  w1, [x0]               ; record in OWNED staged RAM
 *   dsb  sy
 *   b    .                      ; self-loop
 *   nop
 * Only the validated coherent copy may be patched. Historical MMIO-marker
 * receipts (2026-09-21-m2-reset-marker-offline 2caa6a9) are preserved; the
 * SCRATCH7 MMIO write is retired as the marker vehicle.
 */
/*
 * ane_t6021_diag_options_ok — diag-vs-options gate. Pure: callers
 * pass the booleans that drive the gate; no kernel state referenced.
 * Kernel probe sites pass module_param reads; tests pass hand-set
 * inputs through the SAME inline (no copy).
 */
static inline bool ane_t6021_diag_options_ok(bool diag, bool load,
                                            bool boot, bool transport)
{
    return !diag || (load && !boot && !transport);
}

/* ane_t6021_fw_extra_ram_envelope_ok — pure backing-envelope gate.
 * Returns true when (load == false) OR (fw_extra_ram == 0) OR
 * (fw_extra_ram is 16 KiB-aligned, <= SZ_16M, and fw_alias_reserved
 * is set). Aligned-to-0 is a degenerate case; the page check is
 * deliberately ANE_T6021_FW_ALIAS_PAGE (16 KiB) because the late
 * alloc-time check in ane_t6021_fwload.c uses the same constant.
 *
 * IMPORTANT: this is the SAME predicate the kernel probe calls
 * (chain ane_t6021_fwload_options_ok → ane_t6021_fw_extra_ram_envelope_ok
 * → ane_t6021_diag_options_ok). The unit test pulls it from this
 * header and never re-implements the rule. If the rule changes,
 * the test changes with it in lockstep.
 */
static inline bool ane_t6021_fw_extra_ram_envelope_ok(bool load,
                                                    unsigned int fw_extra_ram,
                                                    bool fw_alias_reserved)
{
    if (!load)
        return true;
    if (!fw_extra_ram)
        return true;
    if ((fw_extra_ram & (0x4000u - 1u)) != 0)
        return false;
    if (fw_extra_ram > (16u * 1024u * 1024u))
        return false;
    if (!fw_alias_reserved)
        return false;
    return true;
}

/* Marker word stored into the OWNED staged buffer (offset 0xe0000):
 * "M2T1" little-endian. NOT firmware READY 0x08042006. */
#define ANE_T6021_DIAG_MARKER_WORD	0x4d325431u
/* Staged-buffer offset the marker word lands at (boot-PT window head). */
#define ANE_T6021_DIAG_MARKER_BUF_OFF	0x000e0000ull

static inline void ane_t6021_diag_patch(void *image)
{
    static const unsigned char marker[] = {
        0xe0,0xef,0xff,0x10, 0x00,0x80,0x43,0x91,
        0x21,0x86,0x8a,0x52, 0x41,0xa6,0xa9,0x72,
        0x01,0x00,0x00,0xb9, 0x9f,0x3f,0x03,0xd5,
        0x00,0x00,0x00,0x14, 0x1f,0x20,0x03,0xd5
    };
    memcpy((unsigned char *)image + 0x204, marker, sizeof(marker));
}

#endif /* ANE_T6021_DIAG_MARKER_H */
