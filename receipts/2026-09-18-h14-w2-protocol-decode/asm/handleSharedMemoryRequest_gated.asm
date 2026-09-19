; handleSharedMemoryRequest_gated [0xfffffe00095f98c8-0xfffffe00095f9c8c) 0x3c4 bytes
0xfffffe00095f98c8: bti      c
0xfffffe00095f98cc: pacibsp  
0xfffffe00095f98d0: sub      sp, sp, #0x180
0xfffffe00095f98d4: stp      x28, x27, [sp, #0x140]
0xfffffe00095f98d8: stp      x22, x21, [sp, #0x150]
0xfffffe00095f98dc: stp      x20, x19, [sp, #0x160]
0xfffffe00095f98e0: stp      x29, x30, [sp, #0x170]
0xfffffe00095f98e4: add      x29, sp, #0x170
0xfffffe00095f98e8: mov      x19, x1
0xfffffe00095f98ec: mov      x20, x0
0xfffffe00095f98f0: sub      x22, x29, #0xa8
0xfffffe00095f98f4: adrp     x8, #0xfffffe0008163000
0xfffffe00095f98f8: ldr      x8, [x8, #0xbf0]
0xfffffe00095f98fc: ldr      x8, [x8]
0xfffffe00095f9900: stur     x8, [x29, #-0x38]
0xfffffe00095f9904: bl       #0xfffffe000964c488
0xfffffe00095f9908: mov      x21, x0
0xfffffe00095f990c: sub      x8, x29, #0x88
0xfffffe00095f9910: stp      xzr, xzr, [x29, #-0x48]
0xfffffe00095f9914: adrp     x16, #0xfffffe000814d000
0xfffffe00095f9918: add      x16, x16, #0x738
0xfffffe00095f991c: add      x16, x16, #0x10
0xfffffe00095f9920: mov      x17, x8
0xfffffe00095f9924: movk     x17, #0x7215, lsl #48
0xfffffe00095f9928: pacda    x16, x17
0xfffffe00095f992c: stp      x16, x20, [x29, #-0x88]
0xfffffe00095f9930: stur     x8, [x29, #-0x70]
0xfffffe00095f9934: adrp     x16, #0xfffffe000814d000
0xfffffe00095f9938: add      x16, x16, #0x788
0xfffffe00095f993c: add      x16, x16, #0x10
0xfffffe00095f9940: mov      x17, x22
0xfffffe00095f9944: movk     x17, #0x7215, lsl #48
0xfffffe00095f9948: pacda    x16, x17
0xfffffe00095f994c: stp      x16, x20, [x29, #-0xa8]
0xfffffe00095f9950: stp      x0, x22, [x29, #-0x98]
0xfffffe00095f9954: sub      x8, x29, #0x68
0xfffffe00095f9958: stur     x8, [x29, #-0x50]
0xfffffe00095f995c: adrp     x16, #0xfffffe000814d000
0xfffffe00095f9960: add      x16, x16, #0x788
0xfffffe00095f9964: add      x16, x16, #0x10
0xfffffe00095f9968: mov      x17, x8
0xfffffe00095f996c: movk     x17, #0x7215, lsl #48
0xfffffe00095f9970: pacda    x16, x17
0xfffffe00095f9974: stur     x16, [x29, #-0x68]
0xfffffe00095f9978: ldur     q0, [x22, #8]
0xfffffe00095f997c: stur     q0, [x22, #0x48]
0xfffffe00095f9980: mov      w8, #1
0xfffffe00095f9984: strb     w8, [x20, #0x8cc]
0xfffffe00095f9988: mov      x0, x20
0xfffffe00095f998c: bl       #0xfffffe00095be240  ; __ZN19ANEInferenceRequest17disableLowLatencyEv+0x38
0xfffffe00095f9990: stur     wzr, [x29, #-0x40]
0xfffffe00095f9994: sub      x0, x29, #0xa8
0xfffffe00095f9998: bl       #0xfffffe00095047f0
0xfffffe00095f999c: sub      x0, x29, #0x88
0xfffffe00095f99a0: bl       #0xfffffe00095047f0
0xfffffe00095f99a4: ldr      w8, [x19, #0xc]
0xfffffe00095f99a8: cmp      w8, #7
0xfffffe00095f99ac: b.ne     #0xfffffe00095f9a38
0xfffffe00095f99b0: ldr      w8, [x19, #0x24]
0xfffffe00095f99b4: cmp      w8, #2
0xfffffe00095f99b8: b.eq     #0xfffffe00095f9b1c
0xfffffe00095f99bc: cmp      w8, #1
0xfffffe00095f99c0: b.eq     #0xfffffe00095f9ab0
0xfffffe00095f99c4: cbnz     w8, #0xfffffe00095f9b8c
0xfffffe00095f99c8: ldr      x8, [x19, #0x30]
0xfffffe00095f99cc: ldr      x0, [x20, #0x820]
0xfffffe00095f99d0: add      x9, sp, #0x88
0xfffffe00095f99d4: adrp     x16, #0xfffffe0008163000
0xfffffe00095f99d8: ldr      x16, [x16, #0xb20]
0xfffffe00095f99dc: mov      x17, x9
0xfffffe00095f99e0: movk     x17, #0x6ae1, lsl #48
0xfffffe00095f99e4: pacda    x16, x17
0xfffffe00095f99e8: str      x16, [sp, #0x88]
0xfffffe00095f99ec: adrp     x10, #0xfffffe0007502000
0xfffffe00095f99f0: ldr      d0, [x10, #0xf70]
0xfffffe00095f99f4: str      d0, [sp, #0x90]
0xfffffe00095f99f8: add      x10, x9, #0x10
0xfffffe00095f99fc: adrp     x16, #0xfffffe00095f9000
0xfffffe00095f9a00: add      x16, x16, #0xc8c
0xfffffe00095f9a04: pacia    x16, x10
0xfffffe00095f9a08: str      x16, [sp, #0x98]
0xfffffe00095f9a0c: add      x9, x9, #0x18
0xfffffe00095f9a10: adrp     x16, #0xfffffe000814d000
0xfffffe00095f9a14: add      x16, x16, #0x648
0xfffffe00095f9a18: mov      x17, x9
0xfffffe00095f9a1c: movk     x17, #0xc0bb, lsl #48
0xfffffe00095f9a20: pacda    x16, x17
0xfffffe00095f9a24: stp      x16, x20, [sp, #0xa0]
0xfffffe00095f9a28: stp      x8, x19, [sp, #0xb0]
0xfffffe00095f9a2c: str      x21, [sp, #0xc0]
0xfffffe00095f9a30: add      x1, sp, #0x88
0xfffffe00095f9a34: b        #0xfffffe00095f9b80
0xfffffe00095f9a38: ldr      w9, [x20, #0x180]
0xfffffe00095f9a3c: cmp      w9, #3
0xfffffe00095f9a40: b.hi     #0xfffffe00095f9a6c
0xfffffe00095f9a44: lsl      x9, x9, #3
0xfffffe00095f9a48: adrp     x10, #0xfffffe000814d000
0xfffffe00095f9a4c: add      x10, x10, #0x938
0xfffffe00095f9a50: cmp      x9, w9, sxtw
0xfffffe00095f9a54: add      x11, x10, w9, sxtw
0xfffffe00095f9a58: add      x16, x10, x9
0xfffffe00095f9a5c: movk     x16, #0x2bad, lsl #48
0xfffffe00095f9a60: csel     x11, x11, x16, eq
0xfffffe00095f9a64: ldr      x9, [x11]
0xfffffe00095f9a68: b        #0xfffffe00095f9a74
0xfffffe00095f9a6c: adrp     x9, #0xfffffe00074b8000
0xfffffe00095f9a70: add      x9, x9, #0x69c
0xfffffe00095f9a74: mov      w19, #0x2c7
0xfffffe00095f9a78: movk     w19, #0xe000, lsl #16
0xfffffe00095f9a7c: str      x8, [sp, #0x10]
0xfffffe00095f9a80: adrp     x8, #0xfffffe00074c4000
0xfffffe00095f9a84: add      x8, x8, #0x5c0
0xfffffe00095f9a88: stp      x9, x8, [sp]
0xfffffe00095f9a8c: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f9a90: add      x0, x0, #0xec0
0xfffffe00095f9a94: adrp     x1, #0xfffffe0008163000
0xfffffe00095f9a98: ldr      x1, [x1, #0xbf8]
0xfffffe00095f9a9c: adrp     x3, #0xfffffe00074f5000
0xfffffe00095f9aa0: add      x3, x3, #0xac7
0xfffffe00095f9aa4: mov      w2, #0x10
0xfffffe00095f9aa8: bl       #0xfffffe000964c288
0xfffffe00095f9aac: b        #0xfffffe00095f9c00
0xfffffe00095f9ab0: ldr      x8, [x19, #0x28]
0xfffffe00095f9ab4: ldr      x0, [x20, #0x820]
0xfffffe00095f9ab8: add      x9, sp, #0x50
0xfffffe00095f9abc: adrp     x16, #0xfffffe0008163000
0xfffffe00095f9ac0: ldr      x16, [x16, #0xb20]
0xfffffe00095f9ac4: mov      x17, x9
0xfffffe00095f9ac8: movk     x17, #0x6ae1, lsl #48
0xfffffe00095f9acc: pacda    x16, x17
0xfffffe00095f9ad0: str      x16, [sp, #0x50]
0xfffffe00095f9ad4: adrp     x10, #0xfffffe0007502000
0xfffffe00095f9ad8: ldr      d0, [x10, #0xf70]
0xfffffe00095f9adc: str      d0, [sp, #0x58]
0xfffffe00095f9ae0: add      x10, x9, #0x10
0xfffffe00095f9ae4: adrp     x16, #0xfffffe00095fa000
0xfffffe00095f9ae8: add      x16, x16, #0x148
0xfffffe00095f9aec: pacia    x16, x10
0xfffffe00095f9af0: str      x16, [sp, #0x60]
0xfffffe00095f9af4: add      x9, x9, #0x18
0xfffffe00095f9af8: adrp     x16, #0xfffffe000814d000
0xfffffe00095f9afc: add      x16, x16, #0x668
0xfffffe00095f9b00: mov      x17, x9
0xfffffe00095f9b04: movk     x17, #0xc0bb, lsl #48
0xfffffe00095f9b08: pacda    x16, x17
0xfffffe00095f9b0c: stp      x16, x20, [sp, #0x68]
0xfffffe00095f9b10: stp      x19, x8, [sp, #0x78]
0xfffffe00095f9b14: add      x1, sp, #0x50
0xfffffe00095f9b18: b        #0xfffffe00095f9b80
0xfffffe00095f9b1c: ldr      x0, [x20, #0x820]
0xfffffe00095f9b20: add      x8, sp, #0x20
0xfffffe00095f9b24: adrp     x16, #0xfffffe0008163000
0xfffffe00095f9b28: ldr      x16, [x16, #0xb20]
0xfffffe00095f9b2c: mov      x17, x8
0xfffffe00095f9b30: movk     x17, #0x6ae1, lsl #48
0xfffffe00095f9b34: pacda    x16, x17
0xfffffe00095f9b38: str      x16, [sp, #0x20]
0xfffffe00095f9b3c: adrp     x9, #0xfffffe0007502000
0xfffffe00095f9b40: ldr      d0, [x9, #0xf70]
0xfffffe00095f9b44: str      d0, [sp, #0x28]
0xfffffe00095f9b48: add      x9, x8, #0x10
0xfffffe00095f9b4c: adrp     x16, #0xfffffe00095fa000
0xfffffe00095f9b50: add      x16, x16, #0x258
0xfffffe00095f9b54: pacia    x16, x9
0xfffffe00095f9b58: str      x16, [sp, #0x30]
0xfffffe00095f9b5c: add      x8, x8, #0x18
0xfffffe00095f9b60: adrp     x16, #0xfffffe000814d000
0xfffffe00095f9b64: add      x16, x16, #0x688
0xfffffe00095f9b68: mov      x17, x8
0xfffffe00095f9b6c: movk     x17, #0xc0bb, lsl #48
0xfffffe00095f9b70: pacda    x16, x17
0xfffffe00095f9b74: stp      x16, x20, [sp, #0x38]
0xfffffe00095f9b78: str      x19, [sp, #0x48]
0xfffffe00095f9b7c: add      x1, sp, #0x20
0xfffffe00095f9b80: bl       #0xfffffe000964bb78
0xfffffe00095f9b84: mov      x19, x0
0xfffffe00095f9b88: b        #0xfffffe00095f9c00
0xfffffe00095f9b8c: ldr      w9, [x20, #0x180]
0xfffffe00095f9b90: cmp      w9, #3
0xfffffe00095f9b94: b.hi     #0xfffffe00095f9bc0
0xfffffe00095f9b98: lsl      x9, x9, #3
0xfffffe00095f9b9c: adrp     x10, #0xfffffe000814d000
0xfffffe00095f9ba0: add      x10, x10, #0x938
0xfffffe00095f9ba4: cmp      x9, w9, sxtw
0xfffffe00095f9ba8: add      x11, x10, w9, sxtw
0xfffffe00095f9bac: add      x16, x10, x9
0xfffffe00095f9bb0: movk     x16, #0x2bad, lsl #48
0xfffffe00095f9bb4: csel     x11, x11, x16, eq
0xfffffe00095f9bb8: ldr      x9, [x11]
0xfffffe00095f9bbc: b        #0xfffffe00095f9bc8
0xfffffe00095f9bc0: adrp     x9, #0xfffffe00074b8000
0xfffffe00095f9bc4: add      x9, x9, #0x69c
0xfffffe00095f9bc8: mov      w19, #0x2c7
0xfffffe00095f9bcc: movk     w19, #0xe000, lsl #16
0xfffffe00095f9bd0: str      x8, [sp, #0x10]
0xfffffe00095f9bd4: adrp     x8, #0xfffffe00074c4000
0xfffffe00095f9bd8: add      x8, x8, #0x5c0
0xfffffe00095f9bdc: stp      x9, x8, [sp]
0xfffffe00095f9be0: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f9be4: add      x0, x0, #0xec0
0xfffffe00095f9be8: adrp     x1, #0xfffffe0008163000
0xfffffe00095f9bec: ldr      x1, [x1, #0xbf8]
0xfffffe00095f9bf0: adrp     x3, #0xfffffe00074f5000
0xfffffe00095f9bf4: add      x3, x3, #0xa8c
0xfffffe00095f9bf8: mov      w2, #0x10
0xfffffe00095f9bfc: bl       #0xfffffe000964c288
0xfffffe00095f9c00: ldur     x0, [x29, #-0x50]
0xfffffe00095f9c04: cbz      x0, #0xfffffe00095f9c2c
0xfffffe00095f9c08: ldr      x16, [x0]
0xfffffe00095f9c0c: mov      x17, x0
0xfffffe00095f9c10: movk     x17, #0x7215, lsl #48
0xfffffe00095f9c14: autda    x16, x17
0xfffffe00095f9c18: ldr      x8, [x16, #0x30]!
0xfffffe00095f9c1c: movk     x16, #0x2140, lsl #48
0xfffffe00095f9c20: blraa    x8, x16
0xfffffe00095f9c24: stur     w0, [x29, #-0x40]
0xfffffe00095f9c28: b        #0xfffffe00095f9c4c
0xfffffe00095f9c2c: ldur     x0, [x29, #-0x48]
0xfffffe00095f9c30: cbz      x0, #0xfffffe00095f9c4c
0xfffffe00095f9c34: mov      x8, x0
0xfffffe00095f9c38: ldr      x9, [x8, #0x10]!
0xfffffe00095f9c3c: blraa    x9, x8
0xfffffe00095f9c40: stur     w0, [x29, #-0x40]
0xfffffe00095f9c44: ldur     x0, [x29, #-0x48]
0xfffffe00095f9c48: bl       #0xfffffe000964b9f8
0xfffffe00095f9c4c: sub      x0, x29, #0x68
0xfffffe00095f9c50: bl       #0xfffffe00095047f0
0xfffffe00095f9c54: ldur     x8, [x29, #-0x38]
0xfffffe00095f9c58: adrp     x9, #0xfffffe0008163000
0xfffffe00095f9c5c: ldr      x9, [x9, #0xbf0]
0xfffffe00095f9c60: ldr      x9, [x9]
0xfffffe00095f9c64: cmp      x9, x8
0xfffffe00095f9c68: b.ne     #0xfffffe00095f9c88
0xfffffe00095f9c6c: mov      x0, x19
0xfffffe00095f9c70: ldp      x29, x30, [sp, #0x170]
0xfffffe00095f9c74: ldp      x20, x19, [sp, #0x160]
0xfffffe00095f9c78: ldp      x22, x21, [sp, #0x150]
0xfffffe00095f9c7c: ldp      x28, x27, [sp, #0x140]
0xfffffe00095f9c80: add      sp, sp, #0x180
0xfffffe00095f9c84: retab    
0xfffffe00095f9c88: bl       #0xfffffe000964c278