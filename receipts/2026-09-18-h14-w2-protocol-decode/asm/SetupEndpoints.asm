; SetupEndpoints [0xfffffe00095fe660-0xfffffe00095feb30) 0x4d0 bytes
0xfffffe00095fe660: bti      c
0xfffffe00095fe664: pacibsp  
0xfffffe00095fe668: sub      sp, sp, #0xa0
0xfffffe00095fe66c: stp      x28, x27, [sp, #0x40]
0xfffffe00095fe670: stp      x26, x25, [sp, #0x50]
0xfffffe00095fe674: stp      x24, x23, [sp, #0x60]
0xfffffe00095fe678: stp      x22, x21, [sp, #0x70]
0xfffffe00095fe67c: stp      x20, x19, [sp, #0x80]
0xfffffe00095fe680: stp      x29, x30, [sp, #0x90]
0xfffffe00095fe684: add      x29, sp, #0x90
0xfffffe00095fe688: mov      x19, x1
0xfffffe00095fe68c: mov      x20, x0
0xfffffe00095fe690: cmp      w1, #7
0xfffffe00095fe694: b.lo     #0xfffffe00095fe6cc
0xfffffe00095fe698: ldr      w8, [x20, #0x180]
0xfffffe00095fe69c: cmp      w8, #3
0xfffffe00095fe6a0: b.hi     #0xfffffe00095fe750
0xfffffe00095fe6a4: lsl      x8, x8, #3
0xfffffe00095fe6a8: adrp     x9, #0xfffffe000814e000
0xfffffe00095fe6ac: add      x9, x9, #0xed0
0xfffffe00095fe6b0: cmp      x8, w8, sxtw
0xfffffe00095fe6b4: add      x10, x9, w8, sxtw
0xfffffe00095fe6b8: add      x16, x9, x8
0xfffffe00095fe6bc: movk     x16, #0x2bad, lsl #48
0xfffffe00095fe6c0: csel     x10, x10, x16, eq
0xfffffe00095fe6c4: ldr      x8, [x10]
0xfffffe00095fe6c8: b        #0xfffffe00095fe758
0xfffffe00095fe6cc: add      x8, x20, #0x5c0
0xfffffe00095fe6d0: ubfiz    x9, x19, #6, #0x20
0xfffffe00095fe6d4: cmp      x9, w9, sxtw
0xfffffe00095fe6d8: add      x25, x8, w9, sxtw
0xfffffe00095fe6dc: add      x16, x8, x9
0xfffffe00095fe6e0: movk     x16, #0x2bad, lsl #48
0xfffffe00095fe6e4: csel     x25, x25, x16, eq
0xfffffe00095fe6e8: ldr      x9, [x25, #0x28]
0xfffffe00095fe6ec: ldr      w8, [x20, #0x180]
0xfffffe00095fe6f0: cbz      x9, #0xfffffe00095fe794
0xfffffe00095fe6f4: mov      x21, x2
0xfffffe00095fe6f8: ubfiz    x9, x19, #2, #0x20
0xfffffe00095fe6fc: add      x9, x9, w19, uxtw
0xfffffe00095fe700: lsl      x9, x9, #3
0xfffffe00095fe704: adrp     x10, #0xfffffe000814e000
0xfffffe00095fe708: add      x10, x10, #0x520
0xfffffe00095fe70c: cmp      x9, w9, sxtw
0xfffffe00095fe710: add      x27, x10, w9, sxtw
0xfffffe00095fe714: add      x16, x10, x9
0xfffffe00095fe718: movk     x16, #0x2bad, lsl #48
0xfffffe00095fe71c: csel     x27, x27, x16, eq
0xfffffe00095fe720: cmp      w8, #3
0xfffffe00095fe724: b.hi     #0xfffffe00095fe7c4
0xfffffe00095fe728: lsl      x8, x8, #3
0xfffffe00095fe72c: adrp     x9, #0xfffffe000814e000
0xfffffe00095fe730: add      x9, x9, #0xed0
0xfffffe00095fe734: cmp      x8, w8, sxtw
0xfffffe00095fe738: add      x10, x9, w8, sxtw
0xfffffe00095fe73c: add      x16, x9, x8
0xfffffe00095fe740: movk     x16, #0x2bad, lsl #48
0xfffffe00095fe744: csel     x10, x10, x16, eq
0xfffffe00095fe748: ldr      x8, [x10]
0xfffffe00095fe74c: b        #0xfffffe00095fe7cc
0xfffffe00095fe750: adrp     x8, #0xfffffe00074b8000
0xfffffe00095fe754: add      x8, x8, #0x69c
0xfffffe00095fe758: mov      w22, #0x2c2
0xfffffe00095fe75c: movk     w22, #0xe000, lsl #16
0xfffffe00095fe760: adrp     x9, #0xfffffe00074c4000
0xfffffe00095fe764: add      x9, x9, #0x7f9
0xfffffe00095fe768: stp      x9, x19, [sp, #8]
0xfffffe00095fe76c: str      x8, [sp]
0xfffffe00095fe770: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fe774: add      x0, x0, #0xec0
0xfffffe00095fe778: adrp     x1, #0xfffffe0008163000
0xfffffe00095fe77c: ldr      x1, [x1, #0xbf8]
0xfffffe00095fe780: adrp     x3, #0xfffffe00074f6000
0xfffffe00095fe784: add      x3, x3, #0x9ea
0xfffffe00095fe788: mov      w2, #0x10
0xfffffe00095fe78c: bl       #0xfffffe000964c288
0xfffffe00095fe790: b        #0xfffffe00095feb0c
0xfffffe00095fe794: cmp      w8, #3
0xfffffe00095fe798: b.hi     #0xfffffe00095fe958
0xfffffe00095fe79c: lsl      x8, x8, #3
0xfffffe00095fe7a0: adrp     x9, #0xfffffe000814e000
0xfffffe00095fe7a4: add      x9, x9, #0xed0
0xfffffe00095fe7a8: cmp      x8, w8, sxtw
0xfffffe00095fe7ac: add      x10, x9, w8, sxtw
0xfffffe00095fe7b0: add      x16, x9, x8
0xfffffe00095fe7b4: movk     x16, #0x2bad, lsl #48
0xfffffe00095fe7b8: csel     x10, x10, x16, eq
0xfffffe00095fe7bc: ldr      x8, [x10]
0xfffffe00095fe7c0: b        #0xfffffe00095fe960
0xfffffe00095fe7c4: adrp     x8, #0xfffffe00074b8000
0xfffffe00095fe7c8: add      x8, x8, #0x69c
0xfffffe00095fe7cc: ldr      x26, [x27, #0x18]
0xfffffe00095fe7d0: ldr      x23, [x27, #8]
0xfffffe00095fe7d4: stp      x26, x23, [sp, #0x18]
0xfffffe00095fe7d8: mov      x9, x19
0xfffffe00095fe7dc: adrp     x24, #0xfffffe00074c4000
0xfffffe00095fe7e0: add      x24, x24, #0x7f9
0xfffffe00095fe7e4: stp      x24, x9, [sp, #8]
0xfffffe00095fe7e8: str      x8, [sp]
0xfffffe00095fe7ec: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fe7f0: add      x0, x0, #0xec0
0xfffffe00095fe7f4: adrp     x1, #0xfffffe0008163000
0xfffffe00095fe7f8: ldr      x1, [x1, #0xbf8]
0xfffffe00095fe7fc: adrp     x3, #0xfffffe00074f6000
0xfffffe00095fe800: add      x3, x3, #0xa44
0xfffffe00095fe804: mov      w2, #0
0xfffffe00095fe808: bl       #0xfffffe000964c288
0xfffffe00095fe80c: str      xzr, [sp, #0x38]
0xfffffe00095fe810: ldr      w4, [x27, #0x10]
0xfffffe00095fe814: str      xzr, [sp, #0x10]
0xfffffe00095fe818: strb     wzr, [sp, #8]
0xfffffe00095fe81c: add      x2, sp, #0x38
0xfffffe00095fe820: str      wzr, [sp, #4]
0xfffffe00095fe824: strb     wzr, [sp]
0xfffffe00095fe828: mov      x0, x20
0xfffffe00095fe82c: mov      x1, x23
0xfffffe00095fe830: mov      w3, #1
0xfffffe00095fe834: mov      w5, #1
0xfffffe00095fe838: mov      w6, #0
0xfffffe00095fe83c: mov      x7, #0
0xfffffe00095fe840: bl       #0xfffffe00095f6674
0xfffffe00095fe844: cbz      w0, #0xfffffe00095fe880
0xfffffe00095fe848: mov      x22, x0
0xfffffe00095fe84c: ldr      w8, [x20, #0x180]
0xfffffe00095fe850: cmp      w8, #3
0xfffffe00095fe854: b.hi     #0xfffffe00095fe924
0xfffffe00095fe858: lsl      x8, x8, #3
0xfffffe00095fe85c: adrp     x9, #0xfffffe000814e000
0xfffffe00095fe860: add      x9, x9, #0xed0
0xfffffe00095fe864: cmp      x8, w8, sxtw
0xfffffe00095fe868: add      x10, x9, w8, sxtw
0xfffffe00095fe86c: add      x16, x9, x8
0xfffffe00095fe870: movk     x16, #0x2bad, lsl #48
0xfffffe00095fe874: csel     x10, x10, x16, eq
0xfffffe00095fe878: ldr      x8, [x10]
0xfffffe00095fe87c: b        #0xfffffe00095fe92c
0xfffffe00095fe880: ldr      x8, [sp, #0x38]
0xfffffe00095fe884: ldr      x0, [x8, #0x38]
0xfffffe00095fe888: mov      x1, x23
0xfffffe00095fe88c: bl       #0xfffffe000964c2d8
0xfffffe00095fe890: ldrb     w8, [x27, #0x20]
0xfffffe00095fe894: tbz      w8, #0, #0xfffffe00095fe8a4
0xfffffe00095fe898: ldr      x1, [sp, #0x38]
0xfffffe00095fe89c: mov      x0, x20
0xfffffe00095fe8a0: bl       #0xfffffe00095fe440
0xfffffe00095fe8a4: ldr      x8, [sp, #0x38]
0xfffffe00095fe8a8: str      x8, [x25, #0x18]
0xfffffe00095fe8ac: ldr      x8, [x8, #0x18]
0xfffffe00095fe8b0: mov      w9, #0x14
0xfffffe00095fe8b4: mov      w10, #0xc
0xfffffe00095fe8b8: cmp      x23, #0x100, lsl #12
0xfffffe00095fe8bc: csel     x9, x10, x9, lo
0xfffffe00095fe8c0: mov      x10, #0x20000000000000
0xfffffe00095fe8c4: mov      x11, #0x10000000000000
0xfffffe00095fe8c8: csel     x10, x11, x10, lo
0xfffffe00095fe8cc: mov      w11, #-1
0xfffffe00095fe8d0: lsl      w11, w11, w9
0xfffffe00095fe8d4: mvn      w11, w11
0xfffffe00095fe8d8: lsr      x9, x23, x9
0xfffffe00095fe8dc: tst      x23, x11
0xfffffe00095fe8e0: cinc     w9, w9, ne
0xfffffe00095fe8e4: bfi      x10, x9, #0x2c, #8
0xfffffe00095fe8e8: bfxil    x10, x8, #0, #0x2c
0xfffffe00095fe8ec: str      x10, [sp, #0x30]
0xfffffe00095fe8f0: ldr      w9, [x20, #0x180]
0xfffffe00095fe8f4: cmp      w9, #3
0xfffffe00095fe8f8: b.hi     #0xfffffe00095fe9a0
0xfffffe00095fe8fc: lsl      x9, x9, #3
0xfffffe00095fe900: adrp     x10, #0xfffffe000814e000
0xfffffe00095fe904: add      x10, x10, #0xed0
0xfffffe00095fe908: cmp      x9, w9, sxtw
0xfffffe00095fe90c: add      x11, x10, w9, sxtw
0xfffffe00095fe910: add      x16, x10, x9
0xfffffe00095fe914: movk     x16, #0x2bad, lsl #48
0xfffffe00095fe918: csel     x11, x11, x16, eq
0xfffffe00095fe91c: ldr      x9, [x11]
0xfffffe00095fe920: b        #0xfffffe00095fe9a8
0xfffffe00095fe924: adrp     x8, #0xfffffe00074b8000
0xfffffe00095fe928: add      x8, x8, #0x69c
0xfffffe00095fe92c: stp      x19, x22, [sp, #0x10]
0xfffffe00095fe930: stp      x8, x24, [sp]
0xfffffe00095fe934: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fe938: add      x0, x0, #0xec0
0xfffffe00095fe93c: adrp     x1, #0xfffffe0008163000
0xfffffe00095fe940: ldr      x1, [x1, #0xbf8]
0xfffffe00095fe944: adrp     x3, #0xfffffe00074f6000
0xfffffe00095fe948: add      x3, x3, #0xa77
0xfffffe00095fe94c: mov      w2, #0x10
0xfffffe00095fe950: bl       #0xfffffe000964c288
0xfffffe00095fe954: b        #0xfffffe00095feb0c
0xfffffe00095fe958: adrp     x8, #0xfffffe00074b8000
0xfffffe00095fe95c: add      x8, x8, #0x69c
0xfffffe00095fe960: adrp     x9, #0xfffffe00074c4000
0xfffffe00095fe964: add      x9, x9, #0x7f9
0xfffffe00095fe968: stp      x9, x19, [sp, #8]
0xfffffe00095fe96c: str      x8, [sp]
0xfffffe00095fe970: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fe974: add      x0, x0, #0xec0
0xfffffe00095fe978: adrp     x1, #0xfffffe0008163000
0xfffffe00095fe97c: ldr      x1, [x1, #0xbf8]
0xfffffe00095fe980: adrp     x3, #0xfffffe00074f6000
0xfffffe00095fe984: add      x3, x3, #0xa16
0xfffffe00095fe988: mov      w2, #0x10
0xfffffe00095fe98c: bl       #0xfffffe000964c288
0xfffffe00095fe990: mov      w8, #0x2c2
0xfffffe00095fe994: movk     w8, #0xe000, lsl #16
0xfffffe00095fe998: add      w22, w8, #0x16
0xfffffe00095fe99c: b        #0xfffffe00095feb0c
0xfffffe00095fe9a0: adrp     x9, #0xfffffe00074b8000
0xfffffe00095fe9a4: add      x9, x9, #0x69c
0xfffffe00095fe9a8: stp      x8, x23, [sp, #0x10]
0xfffffe00095fe9ac: stp      x9, x24, [sp]
0xfffffe00095fe9b0: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fe9b4: add      x0, x0, #0xec0
0xfffffe00095fe9b8: adrp     x1, #0xfffffe0008163000
0xfffffe00095fe9bc: ldr      x1, [x1, #0xbf8]
0xfffffe00095fe9c0: adrp     x3, #0xfffffe00074f6000
0xfffffe00095fe9c4: add      x3, x3, #0xac0
0xfffffe00095fe9c8: mov      w2, #0
0xfffffe00095fe9cc: bl       #0xfffffe000964c288
0xfffffe00095fe9d0: ldr      x0, [x25, #0x28]
0xfffffe00095fe9d4: mov      x17, x0
0xfffffe00095fe9d8: ldr      x16, [x0]
0xfffffe00095fe9dc: movk     x17, #0xcda1, lsl #48
0xfffffe00095fe9e0: autda    x16, x17
0xfffffe00095fe9e4: mov      x17, x16
0xfffffe00095fe9e8: xpacd    x17
0xfffffe00095fe9ec: cmp      x16, x17
0xfffffe00095fe9f0: b.eq     #0xfffffe00095fe9f8
0xfffffe00095fe9f4: brk      #0xc472
0xfffffe00095fe9f8: add      x8, x16, #0x1e8
0xfffffe00095fe9fc: ldr      x9, [x16, #0x1e8]
0xfffffe00095fea00: add      x1, sp, #0x30
0xfffffe00095fea04: mov      x2, #0
0xfffffe00095fea08: mov      w3, #1
0xfffffe00095fea0c: mov      x17, x8
0xfffffe00095fea10: movk     x17, #0xab08, lsl #48
0xfffffe00095fea14: blraa    x9, x17
0xfffffe00095fea18: mov      x22, x0
0xfffffe00095fea1c: ldr      w8, [x20, #0x180]
0xfffffe00095fea20: cmp      w8, #3
0xfffffe00095fea24: cbz      w0, #0xfffffe00095fea54
0xfffffe00095fea28: b.hi     #0xfffffe00095fea80
0xfffffe00095fea2c: lsl      x8, x8, #3
0xfffffe00095fea30: adrp     x9, #0xfffffe000814e000
0xfffffe00095fea34: add      x9, x9, #0xed0
0xfffffe00095fea38: cmp      x8, w8, sxtw
0xfffffe00095fea3c: add      x10, x9, w8, sxtw
0xfffffe00095fea40: add      x16, x9, x8
0xfffffe00095fea44: movk     x16, #0x2bad, lsl #48
0xfffffe00095fea48: csel     x10, x10, x16, eq
0xfffffe00095fea4c: ldr      x8, [x10]
0xfffffe00095fea50: b        #0xfffffe00095fea88
0xfffffe00095fea54: b.hi     #0xfffffe00095fead0
0xfffffe00095fea58: lsl      x8, x8, #3
0xfffffe00095fea5c: adrp     x9, #0xfffffe000814e000
0xfffffe00095fea60: add      x9, x9, #0xed0
0xfffffe00095fea64: cmp      x8, w8, sxtw
0xfffffe00095fea68: add      x10, x9, w8, sxtw
0xfffffe00095fea6c: add      x16, x9, x8
0xfffffe00095fea70: movk     x16, #0x2bad, lsl #48
0xfffffe00095fea74: csel     x10, x10, x16, eq
0xfffffe00095fea78: ldr      x8, [x10]
0xfffffe00095fea7c: b        #0xfffffe00095fead8
0xfffffe00095fea80: adrp     x8, #0xfffffe00074b8000
0xfffffe00095fea84: add      x8, x8, #0x69c
0xfffffe00095fea88: mov      x9, x22
0xfffffe00095fea8c: stp      x19, x9, [sp, #0x10]
0xfffffe00095fea90: stp      x8, x24, [sp]
0xfffffe00095fea94: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fea98: add      x0, x0, #0xec0
0xfffffe00095fea9c: adrp     x1, #0xfffffe0008163000
0xfffffe00095feaa0: ldr      x1, [x1, #0xbf8]
0xfffffe00095feaa4: adrp     x3, #0xfffffe00074f6000
0xfffffe00095feaa8: add      x3, x3, #0xaf5
0xfffffe00095feaac: mov      w2, #0x10
0xfffffe00095feab0: bl       #0xfffffe000964c288
0xfffffe00095feab4: str      xzr, [x25, #0x18]
0xfffffe00095feab8: ldr      x8, [sp, #0x38]
0xfffffe00095feabc: ldr      x1, [x8, #0x18]
0xfffffe00095feac0: mov      x0, x20
0xfffffe00095feac4: mov      w2, #0
0xfffffe00095feac8: bl       #0xfffffe00095f7d2c
0xfffffe00095feacc: b        #0xfffffe00095feb0c
0xfffffe00095fead0: adrp     x8, #0xfffffe00074b8000
0xfffffe00095fead4: add      x8, x8, #0x69c
0xfffffe00095fead8: stp      x19, x26, [sp, #0x10]
0xfffffe00095feadc: stp      x8, x24, [sp]
0xfffffe00095feae0: adrp     x0, #0xfffffe00074b7000
0xfffffe00095feae4: add      x0, x0, #0xec0
0xfffffe00095feae8: adrp     x1, #0xfffffe0008163000
0xfffffe00095feaec: ldr      x1, [x1, #0xbf8]
0xfffffe00095feaf0: adrp     x3, #0xfffffe00074f6000
0xfffffe00095feaf4: add      x3, x3, #0xb33
0xfffffe00095feaf8: mov      w2, #0
0xfffffe00095feafc: bl       #0xfffffe000964c288
0xfffffe00095feb00: cbz      x21, #0xfffffe00095feb0c
0xfffffe00095feb04: ldr      x8, [sp, #0x38]
0xfffffe00095feb08: str      x8, [x21]
0xfffffe00095feb0c: mov      x0, x22
0xfffffe00095feb10: ldp      x29, x30, [sp, #0x90]
0xfffffe00095feb14: ldp      x20, x19, [sp, #0x80]
0xfffffe00095feb18: ldp      x22, x21, [sp, #0x70]
0xfffffe00095feb1c: ldp      x24, x23, [sp, #0x60]
0xfffffe00095feb20: ldp      x26, x25, [sp, #0x50]
0xfffffe00095feb24: ldp      x28, x27, [sp, #0x40]
0xfffffe00095feb28: add      sp, sp, #0xa0
0xfffffe00095feb2c: retab    