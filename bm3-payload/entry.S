/* BM3 milestone-0 entry: the aura proxy reload/vector path calls the stub
 * with x0 = physical address of the BootArgs block, then branches to the
 * payload entry (image base + 0x800). The .space pins _start at file offset
 * 0x800 of the flat image; x19 keeps bootargs across the C call.
 */
    .section .text.boot, "ax"
    .space 0x800
    .global _start
_start:
    mov x19, x0
    bl bm3_main
1:  wfi
    b 1b
