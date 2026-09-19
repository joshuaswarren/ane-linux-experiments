; InitializeRTBuddyEndpoints [0xfffffe00095ff824-0xfffffe00095ffb80) 0x35c bytes
0xfffffe00095ff824: bti      c
0xfffffe00095ff828: pacibsp  
0xfffffe00095ff82c: sub      sp, sp, #0x70
0xfffffe00095ff830: stp      x24, x23, [sp, #0x30]
0xfffffe00095ff834: stp      x22, x21, [sp, #0x40]
0xfffffe00095ff838: stp      x20, x19, [sp, #0x50]
0xfffffe00095ff83c: stp      x29, x30, [sp, #0x60]
0xfffffe00095ff840: add      x29, sp, #0x60
0xfffffe00095ff844: mov      x19, x0
0xfffffe00095ff848: ldrb     w8, [x0, #0x781]
0xfffffe00095ff84c: tbnz     w8, #0, #0xfffffe00095ff89c
0xfffffe00095ff850: ldr      x8, [x19, #0x628]
0xfffffe00095ff854: cbz      x8, #0xfffffe00095ff89c
0xfffffe00095ff858: adrp     x8, #0xfffffe000cb6d000
0xfffffe00095ff85c: add      x8, x8, #0xc60
0xfffffe00095ff860: ldrb     w8, [x8, #1]
0xfffffe00095ff864: tbz      w8, #2, #0xfffffe00095ffb60
0xfffffe00095ff868: ldr      w8, [x19, #0x180]
0xfffffe00095ff86c: cmp      w8, #3
0xfffffe00095ff870: b.hi     #0xfffffe00095ffa70
0xfffffe00095ff874: lsl      x8, x8, #3
0xfffffe00095ff878: adrp     x9, #0xfffffe000814e000
0xfffffe00095ff87c: add      x9, x9, #0xed0
0xfffffe00095ff880: cmp      x8, w8, sxtw
0xfffffe00095ff884: add      x10, x9, w8, sxtw
0xfffffe00095ff888: add      x16, x9, x8
0xfffffe00095ff88c: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff890: csel     x10, x10, x16, eq
0xfffffe00095ff894: ldr      x8, [x10]
0xfffffe00095ff898: b        #0xfffffe00095ffa78
0xfffffe00095ff89c: adrp     x8, #0xfffffe000cb6d000
0xfffffe00095ff8a0: add      x8, x8, #0xc60
0xfffffe00095ff8a4: ldrb     w8, [x8, #1]
0xfffffe00095ff8a8: tbz      w8, #2, #0xfffffe00095ff914
0xfffffe00095ff8ac: ldr      w8, [x19, #0x180]
0xfffffe00095ff8b0: cmp      w8, #3
0xfffffe00095ff8b4: b.hi     #0xfffffe00095ff8e0
0xfffffe00095ff8b8: lsl      x8, x8, #3
0xfffffe00095ff8bc: adrp     x9, #0xfffffe000814e000
0xfffffe00095ff8c0: add      x9, x9, #0xed0
0xfffffe00095ff8c4: cmp      x8, w8, sxtw
0xfffffe00095ff8c8: add      x10, x9, w8, sxtw
0xfffffe00095ff8cc: add      x16, x9, x8
0xfffffe00095ff8d0: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff8d4: csel     x10, x10, x16, eq
0xfffffe00095ff8d8: ldr      x8, [x10]
0xfffffe00095ff8dc: b        #0xfffffe00095ff8e8
0xfffffe00095ff8e0: adrp     x8, #0xfffffe00074b8000
0xfffffe00095ff8e4: add      x8, x8, #0x69c
0xfffffe00095ff8e8: adrp     x9, #0xfffffe00074c4000
0xfffffe00095ff8ec: add      x9, x9, #0x824
0xfffffe00095ff8f0: stp      x8, x9, [sp]
0xfffffe00095ff8f4: adrp     x0, #0xfffffe00074b7000
0xfffffe00095ff8f8: add      x0, x0, #0xec0
0xfffffe00095ff8fc: adrp     x1, #0xfffffe0008163000
0xfffffe00095ff900: ldr      x1, [x1, #0xbf8]
0xfffffe00095ff904: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ff908: add      x3, x3, #0xcb3
0xfffffe00095ff90c: mov      w2, #0
0xfffffe00095ff910: bl       #0xfffffe000964c288
0xfffffe00095ff914: ldr      w8, [x19, #0x180]
0xfffffe00095ff918: cmp      w8, #1
0xfffffe00095ff91c: b.ne     #0xfffffe00095ff92c
0xfffffe00095ff920: adrp     x1, #0xfffffe00074c4000
0xfffffe00095ff924: add      x1, x1, #0x83f
0xfffffe00095ff928: b        #0xfffffe00095ff9b8
0xfffffe00095ff92c: ldrb     w8, [x19, #0x781]
0xfffffe00095ff930: tbz      w8, #0, #0xfffffe00095ff9b0
0xfffffe00095ff934: mov      w22, #1
0xfffffe00095ff938: adrp     x21, #0xfffffe00074c4000
0xfffffe00095ff93c: add      x21, x21, #0x84c
0xfffffe00095ff940: and      w20, w22, #0xff
0xfffffe00095ff944: mov      x0, x19
0xfffffe00095ff948: mov      x1, x21
0xfffffe00095ff94c: mov      x2, x20
0xfffffe00095ff950: bl       #0xfffffe00095feb30
0xfffffe00095ff954: tbz      w0, #0, #0xfffffe00095ffa3c
0xfffffe00095ff958: add      w22, w22, #1
0xfffffe00095ff95c: cmp      w20, #5
0xfffffe00095ff960: b.ls     #0xfffffe00095ff940
0xfffffe00095ff964: add      x22, x19, #0x5c0
0xfffffe00095ff968: mov      x21, #-6
0xfffffe00095ff96c: mov      w23, #1
0xfffffe00095ff970: str      xzr, [sp, #0x28]
0xfffffe00095ff974: add      w1, w21, #7
0xfffffe00095ff978: add      x2, sp, #0x28
0xfffffe00095ff97c: mov      x0, x19
0xfffffe00095ff980: bl       #0xfffffe00095fe660
0xfffffe00095ff984: cbnz     w0, #0xfffffe00095ffae8
0xfffffe00095ff988: ldr      x8, [sp, #0x28]
0xfffffe00095ff98c: add      x9, x22, x23, lsl #6
0xfffffe00095ff990: str      x8, [x9, #0x18]
0xfffffe00095ff994: str      wzr, [x9, #0x20]
0xfffffe00095ff998: mov      w20, #1
0xfffffe00095ff99c: strb     w20, [x9, #0x38]
0xfffffe00095ff9a0: add      x23, x23, #1
0xfffffe00095ff9a4: adds     x21, x21, #1
0xfffffe00095ff9a8: b.lo     #0xfffffe00095ff970
0xfffffe00095ff9ac: b        #0xfffffe00095ffb64
0xfffffe00095ff9b0: adrp     x1, #0xfffffe00074c4000
0xfffffe00095ff9b4: add      x1, x1, #0x84c
0xfffffe00095ff9b8: mov      w20, #1
0xfffffe00095ff9bc: mov      x0, x19
0xfffffe00095ff9c0: mov      w2, #1
0xfffffe00095ff9c4: bl       #0xfffffe00095feb30
0xfffffe00095ff9c8: tbnz     w0, #0, #0xfffffe00095ffb64
0xfffffe00095ff9cc: ldr      w8, [x19, #0x180]
0xfffffe00095ff9d0: cmp      w8, #3
0xfffffe00095ff9d4: b.hi     #0xfffffe00095ffa00
0xfffffe00095ff9d8: lsl      x8, x8, #3
0xfffffe00095ff9dc: adrp     x9, #0xfffffe000814e000
0xfffffe00095ff9e0: add      x9, x9, #0xed0
0xfffffe00095ff9e4: cmp      x8, w8, sxtw
0xfffffe00095ff9e8: add      x10, x9, w8, sxtw
0xfffffe00095ff9ec: add      x16, x9, x8
0xfffffe00095ff9f0: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff9f4: csel     x10, x10, x16, eq
0xfffffe00095ff9f8: ldr      x8, [x10]
0xfffffe00095ff9fc: b        #0xfffffe00095ffa08
0xfffffe00095ffa00: adrp     x8, #0xfffffe00074b8000
0xfffffe00095ffa04: add      x8, x8, #0x69c
0xfffffe00095ffa08: adrp     x9, #0xfffffe00074c4000
0xfffffe00095ffa0c: add      x9, x9, #0x824
0xfffffe00095ffa10: stp      x8, x9, [sp]
0xfffffe00095ffa14: adrp     x0, #0xfffffe00074b7000
0xfffffe00095ffa18: add      x0, x0, #0xec0
0xfffffe00095ffa1c: adrp     x1, #0xfffffe0008163000
0xfffffe00095ffa20: ldr      x1, [x1, #0xbf8]
0xfffffe00095ffa24: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ffa28: add      x3, x3, #0xd53
0xfffffe00095ffa2c: mov      w2, #0x10
0xfffffe00095ffa30: bl       #0xfffffe000964c288
0xfffffe00095ffa34: mov      w20, #0
0xfffffe00095ffa38: b        #0xfffffe00095ffb64
0xfffffe00095ffa3c: ldr      w8, [x19, #0x180]
0xfffffe00095ffa40: cmp      w8, #3
0xfffffe00095ffa44: b.hi     #0xfffffe00095ffaa8
0xfffffe00095ffa48: lsl      x8, x8, #3
0xfffffe00095ffa4c: adrp     x9, #0xfffffe000814e000
0xfffffe00095ffa50: add      x9, x9, #0xed0
0xfffffe00095ffa54: cmp      x8, w8, sxtw
0xfffffe00095ffa58: add      x10, x9, w8, sxtw
0xfffffe00095ffa5c: add      x16, x9, x8
0xfffffe00095ffa60: movk     x16, #0x2bad, lsl #48
0xfffffe00095ffa64: csel     x10, x10, x16, eq
0xfffffe00095ffa68: ldr      x8, [x10]
0xfffffe00095ffa6c: b        #0xfffffe00095ffab0
0xfffffe00095ffa70: adrp     x8, #0xfffffe00074b8000
0xfffffe00095ffa74: add      x8, x8, #0x69c
0xfffffe00095ffa78: adrp     x9, #0xfffffe00074c4000
0xfffffe00095ffa7c: add      x9, x9, #0x824
0xfffffe00095ffa80: stp      x8, x9, [sp]
0xfffffe00095ffa84: adrp     x0, #0xfffffe00074b7000
0xfffffe00095ffa88: add      x0, x0, #0xec0
0xfffffe00095ffa8c: adrp     x1, #0xfffffe0008163000
0xfffffe00095ffa90: ldr      x1, [x1, #0xbf8]
0xfffffe00095ffa94: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ffa98: add      x3, x3, #0xc84
0xfffffe00095ffa9c: mov      w2, #0
0xfffffe00095ffaa0: bl       #0xfffffe000964c288
0xfffffe00095ffaa4: b        #0xfffffe00095ffb60
0xfffffe00095ffaa8: adrp     x8, #0xfffffe00074b8000
0xfffffe00095ffaac: add      x8, x8, #0x69c
0xfffffe00095ffab0: adrp     x9, #0xfffffe00074c4000
0xfffffe00095ffab4: add      x9, x9, #0x824
0xfffffe00095ffab8: stp      x9, x20, [sp, #8]
0xfffffe00095ffabc: str      x8, [sp]
0xfffffe00095ffac0: adrp     x0, #0xfffffe00074b7000
0xfffffe00095ffac4: add      x0, x0, #0xec0
0xfffffe00095ffac8: adrp     x1, #0xfffffe0008163000
0xfffffe00095ffacc: ldr      x1, [x1, #0xbf8]
0xfffffe00095ffad0: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ffad4: add      x3, x3, #0xcd9
0xfffffe00095ffad8: mov      w2, #0x10
0xfffffe00095ffadc: bl       #0xfffffe000964c288
0xfffffe00095ffae0: mov      w20, #0
0xfffffe00095ffae4: b        #0xfffffe00095ffb64
0xfffffe00095ffae8: ldr      w9, [x19, #0x180]
0xfffffe00095ffaec: add      x8, x21, #7
0xfffffe00095ffaf0: cmp      w9, #3
0xfffffe00095ffaf4: b.hi     #0xfffffe00095ffb20
0xfffffe00095ffaf8: lsl      x9, x9, #3
0xfffffe00095ffafc: adrp     x10, #0xfffffe000814e000
0xfffffe00095ffb00: add      x10, x10, #0xed0
0xfffffe00095ffb04: cmp      x9, w9, sxtw
0xfffffe00095ffb08: add      x11, x10, w9, sxtw
0xfffffe00095ffb0c: add      x16, x10, x9
0xfffffe00095ffb10: movk     x16, #0x2bad, lsl #48
0xfffffe00095ffb14: csel     x11, x11, x16, eq
0xfffffe00095ffb18: ldr      x9, [x11]
0xfffffe00095ffb1c: b        #0xfffffe00095ffb28
0xfffffe00095ffb20: adrp     x9, #0xfffffe00074b8000
0xfffffe00095ffb24: add      x9, x9, #0x69c
0xfffffe00095ffb28: stp      x8, x0, [sp, #0x10]
0xfffffe00095ffb2c: adrp     x8, #0xfffffe00074c4000
0xfffffe00095ffb30: add      x8, x8, #0x824
0xfffffe00095ffb34: stp      x9, x8, [sp]
0xfffffe00095ffb38: adrp     x0, #0xfffffe00074b7000
0xfffffe00095ffb3c: add      x0, x0, #0xec0
0xfffffe00095ffb40: adrp     x1, #0xfffffe0008163000
0xfffffe00095ffb44: ldr      x1, [x1, #0xbf8]
0xfffffe00095ffb48: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ffb4c: add      x3, x3, #0xd16
0xfffffe00095ffb50: mov      w2, #0x10
0xfffffe00095ffb54: bl       #0xfffffe000964c288
0xfffffe00095ffb58: mov      x0, x19
0xfffffe00095ffb5c: bl       #0xfffffe00095ffb80
0xfffffe00095ffb60: mov      w20, #1
0xfffffe00095ffb64: mov      x0, x20
0xfffffe00095ffb68: ldp      x29, x30, [sp, #0x60]
0xfffffe00095ffb6c: ldp      x20, x19, [sp, #0x50]
0xfffffe00095ffb70: ldp      x22, x21, [sp, #0x40]
0xfffffe00095ffb74: ldp      x24, x23, [sp, #0x30]
0xfffffe00095ffb78: add      sp, sp, #0x70
0xfffffe00095ffb7c: retab    