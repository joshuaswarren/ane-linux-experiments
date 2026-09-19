; rtbuddyEndpointSendMessage [0xfffffe00095f3990-0xfffffe00095f3cdc) 0x34c bytes
0xfffffe00095f3990: bti      c
0xfffffe00095f3994: pacibsp  
0xfffffe00095f3998: sub      sp, sp, #0xa0
0xfffffe00095f399c: stp      x28, x27, [sp, #0x40]
0xfffffe00095f39a0: stp      x26, x25, [sp, #0x50]
0xfffffe00095f39a4: stp      x24, x23, [sp, #0x60]
0xfffffe00095f39a8: stp      x22, x21, [sp, #0x70]
0xfffffe00095f39ac: stp      x20, x19, [sp, #0x80]
0xfffffe00095f39b0: stp      x29, x30, [sp, #0x90]
0xfffffe00095f39b4: add      x29, sp, #0x90
0xfffffe00095f39b8: mov      x20, x0
0xfffffe00095f39bc: ldr      x8, [x2, #0x30]
0xfffffe00095f39c0: cbz      x8, #0xfffffe00095f39e8
0xfffffe00095f39c4: ldr      x9, [x20, #0x980]
0xfffffe00095f39c8: cbz      x9, #0xfffffe00095f39e8
0xfffffe00095f39cc: mov      x19, x2
0xfffffe00095f39d0: add      x9, x20, #0xe, lsl #12
0xfffffe00095f39d4: ldr      w10, [x9, #0x3e8]
0xfffffe00095f39d8: cmp      w10, w1
0xfffffe00095f39dc: b.ne     #0xfffffe00095f3a5c
0xfffffe00095f39e0: mov      w24, #2
0xfffffe00095f39e4: b        #0xfffffe00095f3aa8
0xfffffe00095f39e8: ldr      w8, [x20, #0x180]
0xfffffe00095f39ec: cmp      w8, #3
0xfffffe00095f39f0: b.hi     #0xfffffe00095f3a1c
0xfffffe00095f39f4: lsl      x8, x8, #3
0xfffffe00095f39f8: adrp     x9, #0xfffffe000814d000
0xfffffe00095f39fc: add      x9, x9, #0x1a0
0xfffffe00095f3a00: cmp      x8, w8, sxtw
0xfffffe00095f3a04: add      x10, x9, w8, sxtw
0xfffffe00095f3a08: add      x16, x9, x8
0xfffffe00095f3a0c: movk     x16, #0x2bad, lsl #48
0xfffffe00095f3a10: csel     x10, x10, x16, eq
0xfffffe00095f3a14: ldr      x8, [x10]
0xfffffe00095f3a18: b        #0xfffffe00095f3a24
0xfffffe00095f3a1c: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f3a20: add      x8, x8, #0x69c
0xfffffe00095f3a24: mov      w23, #0x2c2
0xfffffe00095f3a28: movk     w23, #0xe000, lsl #16
0xfffffe00095f3a2c: adrp     x9, #0xfffffe00074c4000
0xfffffe00095f3a30: add      x9, x9, #0xe8
0xfffffe00095f3a34: stp      x8, x9, [sp]
0xfffffe00095f3a38: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f3a3c: add      x0, x0, #0xec0
0xfffffe00095f3a40: adrp     x1, #0xfffffe0008163000
0xfffffe00095f3a44: ldr      x1, [x1, #0xbf8]
0xfffffe00095f3a48: adrp     x3, #0xfffffe00074f4000
0xfffffe00095f3a4c: add      x3, x3, #0xc78
0xfffffe00095f3a50: mov      w2, #0x10
0xfffffe00095f3a54: bl       #0xfffffe000964c288
0xfffffe00095f3a58: b        #0xfffffe00095f3cb8
0xfffffe00095f3a5c: ldr      w10, [x9, #0x3f4]
0xfffffe00095f3a60: cmp      w10, w1
0xfffffe00095f3a64: b.ne     #0xfffffe00095f3a70
0xfffffe00095f3a68: mov      w24, #3
0xfffffe00095f3a6c: b        #0xfffffe00095f3aa8
0xfffffe00095f3a70: ldr      w10, [x9, #0x3d8]
0xfffffe00095f3a74: cmp      w10, w1
0xfffffe00095f3a78: b.ne     #0xfffffe00095f3a84
0xfffffe00095f3a7c: mov      w24, #4
0xfffffe00095f3a80: b        #0xfffffe00095f3aa8
0xfffffe00095f3a84: ldr      w10, [x9, #0x3ec]
0xfffffe00095f3a88: cmp      w10, w1
0xfffffe00095f3a8c: b.ne     #0xfffffe00095f3a98
0xfffffe00095f3a90: mov      w24, #5
0xfffffe00095f3a94: b        #0xfffffe00095f3aa8
0xfffffe00095f3a98: ldr      w9, [x9, #0x3dc]
0xfffffe00095f3a9c: cmp      w9, w1
0xfffffe00095f3aa0: mov      w9, #6
0xfffffe00095f3aa4: csinc    w24, w9, wzr, eq
0xfffffe00095f3aa8: ldr      w21, [x19, #0x10]
0xfffffe00095f3aac: add      x9, x20, #0x5c0
0xfffffe00095f3ab0: mov      w10, w24
0xfffffe00095f3ab4: add      x26, x9, x10, lsl #6
0xfffffe00095f3ab8: ldr      x9, [x26, #8]
0xfffffe00095f3abc: cmp      x9, x21
0xfffffe00095f3ac0: b.hs     #0xfffffe00095f3af8
0xfffffe00095f3ac4: ldr      w8, [x20, #0x180]
0xfffffe00095f3ac8: cmp      w8, #3
0xfffffe00095f3acc: b.hi     #0xfffffe00095f3b70
0xfffffe00095f3ad0: lsl      x8, x8, #3
0xfffffe00095f3ad4: adrp     x10, #0xfffffe000814d000
0xfffffe00095f3ad8: add      x10, x10, #0x1a0
0xfffffe00095f3adc: cmp      x8, w8, sxtw
0xfffffe00095f3ae0: add      x11, x10, w8, sxtw
0xfffffe00095f3ae4: add      x16, x10, x8
0xfffffe00095f3ae8: movk     x16, #0x2bad, lsl #48
0xfffffe00095f3aec: csel     x11, x11, x16, eq
0xfffffe00095f3af0: ldr      x8, [x11]
0xfffffe00095f3af4: b        #0xfffffe00095f3b78
0xfffffe00095f3af8: ldr      w10, [x26, #0x20]
0xfffffe00095f3afc: add      x11, x10, x21
0xfffffe00095f3b00: cmp      x11, x9
0xfffffe00095f3b04: csel     w25, w10, wzr, lo
0xfffffe00095f3b08: ldr      x9, [x26, #0x18]
0xfffffe00095f3b0c: ldr      x9, [x9, #0x38]
0xfffffe00095f3b10: add      x22, x9, x25
0xfffffe00095f3b14: ldr      x1, [x8]
0xfffffe00095f3b18: mov      x0, x22
0xfffffe00095f3b1c: mov      x2, x21
0xfffffe00095f3b20: bl       #0xfffffe000964c528
0xfffffe00095f3b24: adrp     x8, #0xfffffe000cb6d000
0xfffffe00095f3b28: add      x8, x8, #0xc60
0xfffffe00095f3b2c: ldrb     w8, [x8, #1]
0xfffffe00095f3b30: adrp     x27, #0xfffffe00074c4000
0xfffffe00095f3b34: add      x27, x27, #0xe8
0xfffffe00095f3b38: tbz      w8, #2, #0xfffffe00095f3bf4
0xfffffe00095f3b3c: ldr      w8, [x20, #0x180]
0xfffffe00095f3b40: cmp      w8, #3
0xfffffe00095f3b44: b.hi     #0xfffffe00095f3bbc
0xfffffe00095f3b48: lsl      x8, x8, #3
0xfffffe00095f3b4c: adrp     x9, #0xfffffe000814d000
0xfffffe00095f3b50: add      x9, x9, #0x1a0
0xfffffe00095f3b54: cmp      x8, w8, sxtw
0xfffffe00095f3b58: add      x10, x9, w8, sxtw
0xfffffe00095f3b5c: add      x16, x9, x8
0xfffffe00095f3b60: movk     x16, #0x2bad, lsl #48
0xfffffe00095f3b64: csel     x10, x10, x16, eq
0xfffffe00095f3b68: ldr      x8, [x10]
0xfffffe00095f3b6c: b        #0xfffffe00095f3bc4
0xfffffe00095f3b70: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f3b74: add      x8, x8, #0x69c
0xfffffe00095f3b78: stp      x9, x24, [sp, #0x18]
0xfffffe00095f3b7c: adrp     x9, #0xfffffe00074c4000
0xfffffe00095f3b80: add      x9, x9, #0xe8
0xfffffe00095f3b84: stp      x9, x21, [sp, #8]
0xfffffe00095f3b88: str      x8, [sp]
0xfffffe00095f3b8c: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f3b90: add      x0, x0, #0xec0
0xfffffe00095f3b94: adrp     x1, #0xfffffe0008163000
0xfffffe00095f3b98: ldr      x1, [x1, #0xbf8]
0xfffffe00095f3b9c: adrp     x3, #0xfffffe00074f4000
0xfffffe00095f3ba0: add      x3, x3, #0xcb8
0xfffffe00095f3ba4: mov      w2, #0x10
0xfffffe00095f3ba8: bl       #0xfffffe000964c288
0xfffffe00095f3bac: mov      w8, #0x2c2
0xfffffe00095f3bb0: movk     w8, #0xe000, lsl #16
0xfffffe00095f3bb4: add      w23, w8, #0x1f
0xfffffe00095f3bb8: b        #0xfffffe00095f3cb8
0xfffffe00095f3bbc: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f3bc0: add      x8, x8, #0x69c
0xfffffe00095f3bc4: stp      x25, x21, [sp, #0x20]
0xfffffe00095f3bc8: mov      x9, x24
0xfffffe00095f3bcc: stp      x9, x22, [sp, #0x10]
0xfffffe00095f3bd0: stp      x8, x27, [sp]
0xfffffe00095f3bd4: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f3bd8: add      x0, x0, #0xec0
0xfffffe00095f3bdc: adrp     x1, #0xfffffe0008163000
0xfffffe00095f3be0: ldr      x1, [x1, #0xbf8]
0xfffffe00095f3be4: adrp     x3, #0xfffffe00074f4000
0xfffffe00095f3be8: add      x3, x3, #0xd1e
0xfffffe00095f3bec: mov      w2, #0
0xfffffe00095f3bf0: bl       #0xfffffe000964c288
0xfffffe00095f3bf4: and      w8, w25, #0xffffff
0xfffffe00095f3bf8: bfi      x8, x21, #0x18, #0x18
0xfffffe00095f3bfc: str      x8, [sp, #0x38]
0xfffffe00095f3c00: ldr      x0, [x26, #0x28]
0xfffffe00095f3c04: ldr      x16, [x0]
0xfffffe00095f3c08: mov      x17, x0
0xfffffe00095f3c0c: movk     x17, #0xcda1, lsl #48
0xfffffe00095f3c10: autda    x16, x17
0xfffffe00095f3c14: mov      x17, #0x1e8
0xfffffe00095f3c18: add      x16, x16, x17
0xfffffe00095f3c1c: ldr      x8, [x16]
0xfffffe00095f3c20: add      x1, sp, #0x38
0xfffffe00095f3c24: mov      x2, #0
0xfffffe00095f3c28: mov      w3, #1
0xfffffe00095f3c2c: movk     x16, #0xab08, lsl #48
0xfffffe00095f3c30: blraa    x8, x16
0xfffffe00095f3c34: mov      x23, x0
0xfffffe00095f3c38: cbz      w0, #0xfffffe00095f3c70
0xfffffe00095f3c3c: ldr      w8, [x20, #0x180]
0xfffffe00095f3c40: cmp      w8, #3
0xfffffe00095f3c44: b.hi     #0xfffffe00095f3c84
0xfffffe00095f3c48: lsl      x8, x8, #3
0xfffffe00095f3c4c: adrp     x9, #0xfffffe000814d000
0xfffffe00095f3c50: add      x9, x9, #0x1a0
0xfffffe00095f3c54: cmp      x8, w8, sxtw
0xfffffe00095f3c58: add      x10, x9, w8, sxtw
0xfffffe00095f3c5c: add      x16, x9, x8
0xfffffe00095f3c60: movk     x16, #0x2bad, lsl #48
0xfffffe00095f3c64: csel     x10, x10, x16, eq
0xfffffe00095f3c68: ldr      x8, [x10]
0xfffffe00095f3c6c: b        #0xfffffe00095f3c8c
0xfffffe00095f3c70: add      w8, w25, w21
0xfffffe00095f3c74: str      x22, [x19, #0x58]
0xfffffe00095f3c78: str      x22, [x19, #0x40]
0xfffffe00095f3c7c: str      w8, [x26, #0x20]
0xfffffe00095f3c80: b        #0xfffffe00095f3cb8
0xfffffe00095f3c84: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f3c88: add      x8, x8, #0x69c
0xfffffe00095f3c8c: stp      x25, x21, [sp, #0x20]
0xfffffe00095f3c90: stp      x24, x23, [sp, #0x10]
0xfffffe00095f3c94: stp      x8, x27, [sp]
0xfffffe00095f3c98: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f3c9c: add      x0, x0, #0xec0
0xfffffe00095f3ca0: adrp     x1, #0xfffffe0008163000
0xfffffe00095f3ca4: ldr      x1, [x1, #0xbf8]
0xfffffe00095f3ca8: adrp     x3, #0xfffffe00074f4000
0xfffffe00095f3cac: add      x3, x3, #0xd81
0xfffffe00095f3cb0: mov      w2, #0x10
0xfffffe00095f3cb4: bl       #0xfffffe000964c288
0xfffffe00095f3cb8: mov      x0, x23
0xfffffe00095f3cbc: ldp      x29, x30, [sp, #0x90]
0xfffffe00095f3cc0: ldp      x20, x19, [sp, #0x80]
0xfffffe00095f3cc4: ldp      x22, x21, [sp, #0x70]
0xfffffe00095f3cc8: ldp      x24, x23, [sp, #0x60]
0xfffffe00095f3ccc: ldp      x26, x25, [sp, #0x50]
0xfffffe00095f3cd0: ldp      x28, x27, [sp, #0x40]
0xfffffe00095f3cd4: add      sp, sp, #0xa0
0xfffffe00095f3cd8: retab    