/* ANE working-state register dump for the macOS window (T6021, user tool).
 * Runs AFTER macOS has started the ANE firmware. Reads the ANE ASC wrapper
 * page, the ANE pmgr ps words, the three ANE DARTs, the mailbox, and the
 * firmware DATA patchbay/boot-args through the H11 ANE user client.
 * EXCLUDES the 0x818/0x820 event-queue pop registers: host reads there
 * steal the firmware's queued events (pop on read).
 *
 * Registers (engine base 0x284000000, mailbox 0x285408000):
 *   wrapper  engine+0x1400000 size 0x14000 EXCEPT +0x818,+0x81c,+0x820
 *   rvbar    engine+0x1050000 (8 B)
 *   scratch  engine+0x1840048..0x184006c (GPIO/READY words)
 *   pmgr ps  0x28e080000: 0x2e0,0x4000..0x4030 (8 islands, ACTUAL)
 *   dart x3  0x285800000/0x285810000/0x285820000: TCR+0x1000, TTBR+0x1400,
 *            ENABLE+0xc00, PROTECT+0x200
 *   mailbox  0x285408000: CTRL 0x110/0x114, SEND0 0x800, RECV0 0x830/0x838
 *            (NEVER RECV1 0x818 / SEND0-alias 0x820: pop semantics)
 *   patchbay firmware DATA PA 0x10001406870 (36 B tag check) + BOOTARGS
 *
 * Build on macstudio: clang -arch arm64e -framework IOKit \
 *   -framework CoreFoundation ane_regdump.c -o ane_regdump
 * Sign ad-hoc (SIP off + Reduced Security in the window), run as root.
 * Emits out dir: regs.bin (raw words) + regs.json (decoded + SHAs).
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <IOKit/IOKitLib.h>

/* Pinned from the Linux lane (receipts 2026-09-25): engine base
 * 0x284000000, mailbox 0x285408000 (DT reg), pmgr 0x28e080000,
 * dart x3 0x285800000/10/20, patchbay PA 0x10001406870. Offsets below
 * are engine/window-relative; the tool requests them through the user
 * client so no /dev/mem is needed. */
static const uint32_t kWrapperSkip[] = { 0x818, 0x81c, 0x820 };
static const uint32_t kPsWords[] = { 0x2e0, 0x4000, 0x4008, 0x4010,
    0x4018, 0x4020, 0x4028, 0x4030 };
static const uint64_t kDartBases[] = { 0x285800000ull, 0x285810000ull,
    0x285820000ull };

int main(int argc, char **argv) {
    const char *out = (argc > 2 && !strcmp(argv[1], "-o")) ? argv[2] : NULL;
    if (!out) { fprintf(stderr, "usage: ane_regdump -o outprefix\n"); return 2; }
    /* TODO: IOServiceOpen(AppleH11ANEInterface) -> externalMethod reads.
     * Wiring lands before the window; the address table above is final. */
    fprintf(stderr, "ane_regdump: address table staged, user-client wiring next (out=%s)\n", out);
    return 2;
}
