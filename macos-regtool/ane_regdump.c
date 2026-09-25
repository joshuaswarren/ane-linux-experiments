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
int main(int argc, char **argv) {
    (void)argc; (void)argv;
    fprintf(stderr, "ane_regdump: stub - wire IOServiceOpen(H11ANE) + reads next\n");
    return 2;
}
