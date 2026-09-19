; processTargetToHostIOCommand [0xfffffe000959c194-0xfffffe000959d85c) 0x16c8 bytes
0xfffffe000959c194: bti      c
0xfffffe000959c198: pacibsp  
0xfffffe000959c19c: sub      sp, sp, #0x90
0xfffffe000959c1a0: stp      x28, x27, [sp, #0x30]
0xfffffe000959c1a4: stp      x26, x25, [sp, #0x40]
0xfffffe000959c1a8: stp      x24, x23, [sp, #0x50]
0xfffffe000959c1ac: stp      x22, x21, [sp, #0x60]
0xfffffe000959c1b0: stp      x20, x19, [sp, #0x70]
0xfffffe000959c1b4: stp      x29, x30, [sp, #0x80]
0xfffffe000959c1b8: add      x29, sp, #0x80
0xfffffe000959c1bc: mov      x22, x3
0xfffffe000959c1c0: mov      x21, x2
0xfffffe000959c1c4: mov      x20, x1
0xfffffe000959c1c8: mov      x19, x0
0xfffffe000959c1cc: str      xzr, [sp, #0x28]
0xfffffe000959c1d0: ldr      x8, [x0, #0x208]
0xfffffe000959c1d4: add      x8, x8, #1
0xfffffe000959c1d8: str      x8, [x0, #0x208]
0xfffffe000959c1dc: ldrb     w8, [x0, #0x781]
0xfffffe000959c1e0: tbz      w8, #0, #0xfffffe000959c1f4
0xfffffe000959c1e4: ldr      x8, [x19, #0x718]
0xfffffe000959c1e8: str      x8, [sp, #0x28]
0xfffffe000959c1ec: mov      x23, x20
0xfffffe000959c1f0: b        #0xfffffe000959c214
0xfffffe000959c1f4: add      x3, sp, #0x28
0xfffffe000959c1f8: mov      x0, x19
0xfffffe000959c1fc: mov      x1, x20
0xfffffe000959c200: mov      w2, #0xc
0xfffffe000959c204: mov      x4, #0
0xfffffe000959c208: bl       #0xfffffe00095f73cc
0xfffffe000959c20c: mov      x23, x0
0xfffffe000959c210: ldr      x8, [sp, #0x28]
0xfffffe000959c214: cmp      x8, #0
0xfffffe000959c218: mov      w8, #0xdadd
0xfffffe000959c21c: movk     w8, #0xba, lsl #16
0xfffffe000959c220: ccmp     x23, x8, #4, ne
0xfffffe000959c224: ccmp     x23, #0, #4, ne
0xfffffe000959c228: b.ne     #0xfffffe000959c2e8
0xfffffe000959c22c: mov      w0, #0x20
0xfffffe000959c230: movk     w0, #0x61b, lsl #16
0xfffffe000959c234: mov      x1, #0
0xfffffe000959c238: mov      x2, #0
0xfffffe000959c23c: mov      x3, #0
0xfffffe000959c240: mov      x4, #0
0xfffffe000959c244: mov      x5, #0
0xfffffe000959c248: bl       #0xfffffe000964c418
0xfffffe000959c24c: ldr      w8, [x19, #0x180]
0xfffffe000959c250: cmp      w8, #3
0xfffffe000959c254: b.hi     #0xfffffe000959c280
0xfffffe000959c258: lsl      x8, x8, #3
0xfffffe000959c25c: adrp     x9, #0xfffffe0008142000
0xfffffe000959c260: add      x9, x9, #0xc98
0xfffffe000959c264: cmp      x8, w8, sxtw
0xfffffe000959c268: add      x10, x9, w8, sxtw
0xfffffe000959c26c: add      x16, x9, x8
0xfffffe000959c270: movk     x16, #0x2bad, lsl #48
0xfffffe000959c274: csel     x10, x10, x16, eq
0xfffffe000959c278: ldr      x8, [x10]
0xfffffe000959c27c: b        #0xfffffe000959c288
0xfffffe000959c280: adrp     x8, #0xfffffe00074b8000
0xfffffe000959c284: add      x8, x8, #0x69c
0xfffffe000959c288: stp      x20, x23, [sp, #0x10]
0xfffffe000959c28c: adrp     x9, #0xfffffe00074be000
0xfffffe000959c290: add      x9, x9, #0x538
0xfffffe000959c294: stp      x8, x9, [sp]
0xfffffe000959c298: adrp     x0, #0xfffffe00074b7000
0xfffffe000959c29c: add      x0, x0, #0xec0
0xfffffe000959c2a0: adrp     x1, #0xfffffe0008163000
0xfffffe000959c2a4: ldr      x1, [x1, #0xbf8]
0xfffffe000959c2a8: adrp     x3, #0xfffffe00074e5000
0xfffffe000959c2ac: add      x3, x3, #0xe96
0xfffffe000959c2b0: mov      w2, #0x10
0xfffffe000959c2b4: bl       #0xfffffe000964c288
0xfffffe000959c2b8: mov      w8, #0x2e8
0xfffffe000959c2bc: movk     w8, #0xe000, lsl #16
0xfffffe000959c2c0: sub      w24, w8, #0x2c
0xfffffe000959c2c4: mov      x0, x24
0xfffffe000959c2c8: ldp      x29, x30, [sp, #0x80]
0xfffffe000959c2cc: ldp      x20, x19, [sp, #0x70]
0xfffffe000959c2d0: ldp      x22, x21, [sp, #0x60]
0xfffffe000959c2d4: ldp      x24, x23, [sp, #0x50]
0xfffffe000959c2d8: ldp      x26, x25, [sp, #0x40]
0xfffffe000959c2dc: ldp      x28, x27, [sp, #0x30]
0xfffffe000959c2e0: add      sp, sp, #0x90
0xfffffe000959c2e4: retab    
0xfffffe000959c2e8: mov      w8, #0xe3ec
0xfffffe000959c2ec: add      x25, x19, x8
0xfffffe000959c2f0: ldrh     w8, [x23, #4]
0xfffffe000959c2f4: cmp      w8, #0x106
0xfffffe000959c2f8: b.le     #0xfffffe000959c394
0xfffffe000959c2fc: cmp      w8, #0x302
0xfffffe000959c300: b.gt     #0xfffffe000959c4c0
0xfffffe000959c304: cmp      w8, #0x2ff
0xfffffe000959c308: b.le     #0xfffffe000959c550
0xfffffe000959c30c: cmp      w8, #0x300
0xfffffe000959c310: b.eq     #0xfffffe000959c5d0
0xfffffe000959c314: cmp      w8, #0x302
0xfffffe000959c318: b.ne     #0xfffffe000959cf88
0xfffffe000959c31c: mov      w0, #0x20
0xfffffe000959c320: movk     w0, #0x61b, lsl #16
0xfffffe000959c324: mov      w1, #0xb
0xfffffe000959c328: mov      x2, #0
0xfffffe000959c32c: mov      x3, #0
0xfffffe000959c330: mov      x4, #0
0xfffffe000959c334: mov      x5, #0
0xfffffe000959c338: bl       #0xfffffe000964c418
0xfffffe000959c33c: ldr      x8, [sp, #0x28]
0xfffffe000959c340: ldr      x9, [x8, #0x38]
0xfffffe000959c344: cmp      x9, x23
0xfffffe000959c348: b.hi     #0xfffffe000959c360
0xfffffe000959c34c: add      x10, x23, #0x28
0xfffffe000959c350: ldr      x8, [x8]
0xfffffe000959c354: add      x8, x8, x9
0xfffffe000959c358: cmp      x10, x8
0xfffffe000959c35c: b.ls     #0xfffffe000959cc68
0xfffffe000959c360: ldr      w8, [x19, #0x180]
0xfffffe000959c364: cmp      w8, #3
0xfffffe000959c368: b.hi     #0xfffffe000959c9cc
0xfffffe000959c36c: lsl      x8, x8, #3
0xfffffe000959c370: adrp     x9, #0xfffffe0008142000
0xfffffe000959c374: add      x9, x9, #0xc98
0xfffffe000959c378: cmp      x8, w8, sxtw
0xfffffe000959c37c: add      x10, x9, w8, sxtw
0xfffffe000959c380: add      x16, x9, x8
0xfffffe000959c384: movk     x16, #0x2bad, lsl #48
0xfffffe000959c388: csel     x10, x10, x16, eq
0xfffffe000959c38c: ldr      x8, [x10]
0xfffffe000959c390: b        #0xfffffe000959c9d4
0xfffffe000959c394: cmp      w8, #0x103
0xfffffe000959c398: b.gt     #0xfffffe000959c42c
0xfffffe000959c39c: cmp      w8, #0x100
0xfffffe000959c3a0: b.eq     #0xfffffe000959c654
0xfffffe000959c3a4: cmp      w8, #0x102
0xfffffe000959c3a8: b.eq     #0xfffffe000959c774
0xfffffe000959c3ac: cmp      w8, #0x103
0xfffffe000959c3b0: b.ne     #0xfffffe000959cf88
0xfffffe000959c3b4: mov      w0, #0x20
0xfffffe000959c3b8: movk     w0, #0x61b, lsl #16
0xfffffe000959c3bc: mov      w1, #8
0xfffffe000959c3c0: mov      x2, #0
0xfffffe000959c3c4: mov      x3, #0
0xfffffe000959c3c8: mov      x4, #0
0xfffffe000959c3cc: mov      x5, #0
0xfffffe000959c3d0: bl       #0xfffffe000964c418
0xfffffe000959c3d4: ldr      x8, [sp, #0x28]
0xfffffe000959c3d8: ldr      x9, [x8, #0x38]
0xfffffe000959c3dc: cmp      x9, x23
0xfffffe000959c3e0: b.hi     #0xfffffe000959c3f8
0xfffffe000959c3e4: add      x10, x23, #0xc10
0xfffffe000959c3e8: ldr      x8, [x8]
0xfffffe000959c3ec: add      x8, x8, x9
0xfffffe000959c3f0: cmp      x10, x8
0xfffffe000959c3f4: b.ls     #0xfffffe000959ccd4
0xfffffe000959c3f8: ldr      w8, [x19, #0x180]
0xfffffe000959c3fc: cmp      w8, #3
0xfffffe000959c400: b.hi     #0xfffffe000959ca4c
0xfffffe000959c404: lsl      x8, x8, #3
0xfffffe000959c408: adrp     x9, #0xfffffe0008142000
0xfffffe000959c40c: add      x9, x9, #0xc98
0xfffffe000959c410: cmp      x8, w8, sxtw
0xfffffe000959c414: add      x10, x9, w8, sxtw
0xfffffe000959c418: add      x16, x9, x8
0xfffffe000959c41c: movk     x16, #0x2bad, lsl #48
0xfffffe000959c420: csel     x10, x10, x16, eq
0xfffffe000959c424: ldr      x8, [x10]
0xfffffe000959c428: b        #0xfffffe000959ca54
0xfffffe000959c42c: cmp      w8, #0x104
0xfffffe000959c430: b.eq     #0xfffffe000959c6a8
0xfffffe000959c434: cmp      w8, #0x105
0xfffffe000959c438: b.eq     #0xfffffe000959c7ec
0xfffffe000959c43c: cmp      w8, #0x106
0xfffffe000959c440: b.ne     #0xfffffe000959cf88
0xfffffe000959c444: mov      w0, #0x20
0xfffffe000959c448: movk     w0, #0x61b, lsl #16
0xfffffe000959c44c: mov      w1, #0xa
0xfffffe000959c450: mov      x2, #0
0xfffffe000959c454: mov      x3, #0
0xfffffe000959c458: mov      x4, #0
0xfffffe000959c45c: mov      x5, #0
0xfffffe000959c460: bl       #0xfffffe000964c418
0xfffffe000959c464: ldr      x8, [sp, #0x28]
0xfffffe000959c468: ldr      x9, [x8, #0x38]
0xfffffe000959c46c: cmp      x9, x23
0xfffffe000959c470: b.hi     #0xfffffe000959c48c
0xfffffe000959c474: mov      w10, #0x1010
0xfffffe000959c478: add      x10, x23, x10
0xfffffe000959c47c: ldr      x8, [x8]
0xfffffe000959c480: add      x8, x8, x9
0xfffffe000959c484: cmp      x10, x8
0xfffffe000959c488: b.ls     #0xfffffe000959cd1c
0xfffffe000959c48c: ldr      w8, [x19, #0x180]
0xfffffe000959c490: cmp      w8, #3
0xfffffe000959c494: b.hi     #0xfffffe000959ca8c
0xfffffe000959c498: lsl      x8, x8, #3
0xfffffe000959c49c: adrp     x9, #0xfffffe0008142000
0xfffffe000959c4a0: add      x9, x9, #0xc98
0xfffffe000959c4a4: cmp      x8, w8, sxtw
0xfffffe000959c4a8: add      x10, x9, w8, sxtw
0xfffffe000959c4ac: add      x16, x9, x8
0xfffffe000959c4b0: movk     x16, #0x2bad, lsl #48
0xfffffe000959c4b4: csel     x10, x10, x16, eq
0xfffffe000959c4b8: ldr      x8, [x10]
0xfffffe000959c4bc: b        #0xfffffe000959ca94
0xfffffe000959c4c0: cmp      w8, #0x303
0xfffffe000959c4c4: b.eq     #0xfffffe000959c6fc
0xfffffe000959c4c8: cmp      w8, #0x305
0xfffffe000959c4cc: b.eq     #0xfffffe000959c864
0xfffffe000959c4d0: cmp      w8, #7, lsl #12
0xfffffe000959c4d4: b.ne     #0xfffffe000959cf88
0xfffffe000959c4d8: mov      w0, #0x20
0xfffffe000959c4dc: movk     w0, #0x61b, lsl #16
0xfffffe000959c4e0: mov      w1, #1
0xfffffe000959c4e4: mov      x2, #0
0xfffffe000959c4e8: mov      x3, #0
0xfffffe000959c4ec: mov      x4, #0
0xfffffe000959c4f0: mov      x5, #0
0xfffffe000959c4f4: bl       #0xfffffe000964c418
0xfffffe000959c4f8: ldr      x8, [sp, #0x28]
0xfffffe000959c4fc: ldr      x9, [x8, #0x38]
0xfffffe000959c500: cmp      x9, x23
0xfffffe000959c504: b.hi     #0xfffffe000959c51c
0xfffffe000959c508: add      x10, x23, #0xc
0xfffffe000959c50c: ldr      x8, [x8]
0xfffffe000959c510: add      x8, x8, x9
0xfffffe000959c514: cmp      x10, x8
0xfffffe000959c518: b.ls     #0xfffffe000959cd64
0xfffffe000959c51c: ldr      w8, [x19, #0x180]
0xfffffe000959c520: cmp      w8, #3
0xfffffe000959c524: b.hi     #0xfffffe000959cacc
0xfffffe000959c528: lsl      x8, x8, #3
0xfffffe000959c52c: adrp     x9, #0xfffffe0008142000
0xfffffe000959c530: add      x9, x9, #0xc98
0xfffffe000959c534: cmp      x8, w8, sxtw
0xfffffe000959c538: add      x10, x9, w8, sxtw
0xfffffe000959c53c: add      x16, x9, x8
0xfffffe000959c540: movk     x16, #0x2bad, lsl #48
0xfffffe000959c544: csel     x10, x10, x16, eq
0xfffffe000959c548: ldr      x8, [x10]
0xfffffe000959c54c: b        #0xfffffe000959cad4
0xfffffe000959c550: cmp      w8, #0x107
0xfffffe000959c554: b.ne     #0xfffffe000959cf80
0xfffffe000959c558: mov      w0, #0x20
0xfffffe000959c55c: movk     w0, #0x61b, lsl #16
0xfffffe000959c560: mov      w1, #0xc
0xfffffe000959c564: mov      x2, #0
0xfffffe000959c568: mov      x3, #0
0xfffffe000959c56c: mov      x4, #0
0xfffffe000959c570: mov      x5, #0
0xfffffe000959c574: bl       #0xfffffe000964c418
0xfffffe000959c578: ldr      x8, [sp, #0x28]
0xfffffe000959c57c: ldr      x9, [x8, #0x38]
0xfffffe000959c580: cmp      x9, x23
0xfffffe000959c584: b.hi     #0xfffffe000959c59c
0xfffffe000959c588: add      x10, x23, #0xc
0xfffffe000959c58c: ldr      x8, [x8]
0xfffffe000959c590: add      x8, x8, x9
0xfffffe000959c594: cmp      x10, x8
0xfffffe000959c598: b.ls     #0xfffffe000959cc04
0xfffffe000959c59c: ldr      w8, [x19, #0x180]
0xfffffe000959c5a0: cmp      w8, #3
0xfffffe000959c5a4: b.hi     #0xfffffe000959c98c
0xfffffe000959c5a8: lsl      x8, x8, #3
0xfffffe000959c5ac: adrp     x9, #0xfffffe0008142000
0xfffffe000959c5b0: add      x9, x9, #0xc98
0xfffffe000959c5b4: cmp      x8, w8, sxtw
0xfffffe000959c5b8: add      x10, x9, w8, sxtw
0xfffffe000959c5bc: add      x16, x9, x8
0xfffffe000959c5c0: movk     x16, #0x2bad, lsl #48
0xfffffe000959c5c4: csel     x10, x10, x16, eq
0xfffffe000959c5c8: ldr      x8, [x10]
0xfffffe000959c5cc: b        #0xfffffe000959c994
0xfffffe000959c5d0: ldr      x0, [x23, #0x28]
0xfffffe000959c5d4: bl       #0xfffffe000964c338
0xfffffe000959c5d8: str      x0, [x23, #0x28]
0xfffffe000959c5dc: ldr      w2, [x23, #0x1c]
0xfffffe000959c5e0: mov      w0, #0x20
0xfffffe000959c5e4: movk     w0, #0x61b, lsl #16
0xfffffe000959c5e8: mov      w1, #4
0xfffffe000959c5ec: mov      x3, #0
0xfffffe000959c5f0: mov      x4, #0
0xfffffe000959c5f4: mov      x5, #0
0xfffffe000959c5f8: bl       #0xfffffe000964c418
0xfffffe000959c5fc: ldr      x8, [sp, #0x28]
0xfffffe000959c600: ldr      x9, [x8, #0x38]
0xfffffe000959c604: cmp      x9, x23
0xfffffe000959c608: b.hi     #0xfffffe000959c620
0xfffffe000959c60c: add      x10, x23, #0x60
0xfffffe000959c610: ldr      x8, [x8]
0xfffffe000959c614: add      x8, x8, x9
0xfffffe000959c618: cmp      x10, x8
0xfffffe000959c61c: b.ls     #0xfffffe000959cc78
0xfffffe000959c620: ldr      w8, [x19, #0x180]
0xfffffe000959c624: cmp      w8, #4
0xfffffe000959c628: b.hs     #0xfffffe000959ca0c
0xfffffe000959c62c: lsl      x8, x8, #3
0xfffffe000959c630: adrp     x9, #0xfffffe0008142000
0xfffffe000959c634: add      x9, x9, #0xc98
0xfffffe000959c638: cmp      x8, w8, sxtw
0xfffffe000959c63c: add      x10, x9, w8, sxtw
0xfffffe000959c640: add      x16, x9, x8
0xfffffe000959c644: movk     x16, #0x2bad, lsl #48
0xfffffe000959c648: csel     x10, x10, x16, eq
0xfffffe000959c64c: ldr      x8, [x10]
0xfffffe000959c650: b        #0xfffffe000959ca14
0xfffffe000959c654: mov      w0, #0x20
0xfffffe000959c658: movk     w0, #0x61b, lsl #16
0xfffffe000959c65c: mov      w1, #3
0xfffffe000959c660: mov      x2, #0
0xfffffe000959c664: mov      x3, #0
0xfffffe000959c668: mov      x4, #0
0xfffffe000959c66c: mov      x5, #0
0xfffffe000959c670: bl       #0xfffffe000964c418
0xfffffe000959c674: ldr      w8, [x19, #0x180]
0xfffffe000959c678: cmp      w8, #3
0xfffffe000959c67c: b.hi     #0xfffffe000959c8c8
0xfffffe000959c680: lsl      x8, x8, #3
0xfffffe000959c684: adrp     x9, #0xfffffe0008142000
0xfffffe000959c688: add      x9, x9, #0xc98
0xfffffe000959c68c: cmp      x8, w8, sxtw
0xfffffe000959c690: add      x10, x9, w8, sxtw
0xfffffe000959c694: add      x16, x9, x8
0xfffffe000959c698: movk     x16, #0x2bad, lsl #48
0xfffffe000959c69c: csel     x10, x10, x16, eq
0xfffffe000959c6a0: ldr      x8, [x10]
0xfffffe000959c6a4: b        #0xfffffe000959c8d0
0xfffffe000959c6a8: mov      w0, #0x20
0xfffffe000959c6ac: movk     w0, #0x61b, lsl #16
0xfffffe000959c6b0: mov      w1, #5
0xfffffe000959c6b4: mov      x2, #0
0xfffffe000959c6b8: mov      x3, #0
0xfffffe000959c6bc: mov      x4, #0
0xfffffe000959c6c0: mov      x5, #0
0xfffffe000959c6c4: bl       #0xfffffe000964c418
0xfffffe000959c6c8: ldr      w8, [x19, #0x180]
0xfffffe000959c6cc: cmp      w8, #3
0xfffffe000959c6d0: b.hi     #0xfffffe000959c900
0xfffffe000959c6d4: lsl      x8, x8, #3
0xfffffe000959c6d8: adrp     x9, #0xfffffe0008142000
0xfffffe000959c6dc: add      x9, x9, #0xc98
0xfffffe000959c6e0: cmp      x8, w8, sxtw
0xfffffe000959c6e4: add      x10, x9, w8, sxtw
0xfffffe000959c6e8: add      x16, x9, x8
0xfffffe000959c6ec: movk     x16, #0x2bad, lsl #48
0xfffffe000959c6f0: csel     x10, x10, x16, eq
0xfffffe000959c6f4: ldr      x8, [x10]
0xfffffe000959c6f8: b        #0xfffffe000959c908
0xfffffe000959c6fc: mov      w0, #0x20
0xfffffe000959c700: movk     w0, #0x61b, lsl #16
0xfffffe000959c704: mov      w1, #6
0xfffffe000959c708: mov      x2, #0
0xfffffe000959c70c: mov      x3, #0
0xfffffe000959c710: mov      x4, #0
0xfffffe000959c714: mov      x5, #0
0xfffffe000959c718: bl       #0xfffffe000964c418
0xfffffe000959c71c: ldr      x8, [sp, #0x28]
0xfffffe000959c720: ldr      x9, [x8, #0x38]
0xfffffe000959c724: cmp      x9, x23
0xfffffe000959c728: b.hi     #0xfffffe000959c740
0xfffffe000959c72c: add      x10, x23, #0x470
0xfffffe000959c730: ldr      x8, [x8]
0xfffffe000959c734: add      x8, x8, x9
0xfffffe000959c738: cmp      x10, x8
0xfffffe000959c73c: b.ls     #0xfffffe000959cd88
0xfffffe000959c740: ldr      w8, [x19, #0x180]
0xfffffe000959c744: cmp      w8, #3
0xfffffe000959c748: b.hi     #0xfffffe000959cb44
0xfffffe000959c74c: lsl      x8, x8, #3
0xfffffe000959c750: adrp     x9, #0xfffffe0008142000
0xfffffe000959c754: add      x9, x9, #0xc98
0xfffffe000959c758: cmp      x8, w8, sxtw
0xfffffe000959c75c: add      x10, x9, w8, sxtw
0xfffffe000959c760: add      x16, x9, x8
0xfffffe000959c764: movk     x16, #0x2bad, lsl #48
0xfffffe000959c768: csel     x10, x10, x16, eq
0xfffffe000959c76c: ldr      x8, [x10]
0xfffffe000959c770: b        #0xfffffe000959cb4c
0xfffffe000959c774: mov      w0, #0x20
0xfffffe000959c778: movk     w0, #0x61b, lsl #16
0xfffffe000959c77c: mov      w1, #7
0xfffffe000959c780: mov      x2, #0
0xfffffe000959c784: mov      x3, #0
0xfffffe000959c788: mov      x4, #0
0xfffffe000959c78c: mov      x5, #0
0xfffffe000959c790: bl       #0xfffffe000964c418
0xfffffe000959c794: ldr      x8, [sp, #0x28]
0xfffffe000959c798: ldr      x9, [x8, #0x38]
0xfffffe000959c79c: cmp      x9, x23
0xfffffe000959c7a0: b.hi     #0xfffffe000959c7b8
0xfffffe000959c7a4: add      x10, x23, #0x30
0xfffffe000959c7a8: ldr      x8, [x8]
0xfffffe000959c7ac: add      x8, x8, x9
0xfffffe000959c7b0: cmp      x10, x8
0xfffffe000959c7b4: b.ls     #0xfffffe000959cdf0
0xfffffe000959c7b8: ldr      w8, [x19, #0x180]
0xfffffe000959c7bc: cmp      w8, #3
0xfffffe000959c7c0: b.hi     #0xfffffe000959cb84
0xfffffe000959c7c4: lsl      x8, x8, #3
0xfffffe000959c7c8: adrp     x9, #0xfffffe0008142000
0xfffffe000959c7cc: add      x9, x9, #0xc98
0xfffffe000959c7d0: cmp      x8, w8, sxtw
0xfffffe000959c7d4: add      x10, x9, w8, sxtw
0xfffffe000959c7d8: add      x16, x9, x8
0xfffffe000959c7dc: movk     x16, #0x2bad, lsl #48
0xfffffe000959c7e0: csel     x10, x10, x16, eq
0xfffffe000959c7e4: ldr      x8, [x10]
0xfffffe000959c7e8: b        #0xfffffe000959cb8c
0xfffffe000959c7ec: mov      w0, #0x20
0xfffffe000959c7f0: movk     w0, #0x61b, lsl #16
0xfffffe000959c7f4: mov      w1, #9
0xfffffe000959c7f8: mov      x2, #0
0xfffffe000959c7fc: mov      x3, #0
0xfffffe000959c800: mov      x4, #0
0xfffffe000959c804: mov      x5, #0
0xfffffe000959c808: bl       #0xfffffe000964c418
0xfffffe000959c80c: ldr      x8, [sp, #0x28]
0xfffffe000959c810: ldr      x9, [x8, #0x38]
0xfffffe000959c814: cmp      x9, x23
0xfffffe000959c818: b.hi     #0xfffffe000959c830
0xfffffe000959c81c: add      x10, x23, #0x40
0xfffffe000959c820: ldr      x8, [x8]
0xfffffe000959c824: add      x8, x8, x9
0xfffffe000959c828: cmp      x10, x8
0xfffffe000959c82c: b.ls     #0xfffffe000959ce2c
0xfffffe000959c830: ldr      w8, [x19, #0x180]
0xfffffe000959c834: cmp      w8, #3
0xfffffe000959c838: b.hi     #0xfffffe000959cbc4
0xfffffe000959c83c: lsl      x8, x8, #3
0xfffffe000959c840: adrp     x9, #0xfffffe0008142000
0xfffffe000959c844: add      x9, x9, #0xc98
0xfffffe000959c848: cmp      x8, w8, sxtw
0xfffffe000959c84c: add      x10, x9, w8, sxtw
0xfffffe000959c850: add      x16, x9, x8
0xfffffe000959c854: movk     x16, #0x2bad, lsl #48
0xfffffe000959c858: csel     x10, x10, x16, eq
0xfffffe000959c85c: ldr      x8, [x10]
0xfffffe000959c860: b        #0xfffffe000959cbcc
0xfffffe000959c864: mov      w0, #0x20
0xfffffe000959c868: movk     w0, #0x61b, lsl #16
0xfffffe000959c86c: mov      w1, #0xd
0xfffffe000959c870: mov      x2, #0
0xfffffe000959c874: mov      x3, #0
0xfffffe000959c878: mov      x4, #0
0xfffffe000959c87c: mov      x5, #0
0xfffffe000959c880: bl       #0xfffffe000964c418
0xfffffe000959c884: adrp     x24, #0xfffffe000cb6d000
0xfffffe000959c888: add      x24, x24, #0xc60
0xfffffe000959c88c: ldrb     w8, [x24, #1]
0xfffffe000959c890: tbz      w8, #2, #0xfffffe000959ceac
0xfffffe000959c894: ldr      w8, [x19, #0x180]
0xfffffe000959c898: cmp      w8, #3
0xfffffe000959c89c: b.hi     #0xfffffe000959ce70
0xfffffe000959c8a0: lsl      x8, x8, #3
0xfffffe000959c8a4: adrp     x9, #0xfffffe0008142000
0xfffffe000959c8a8: add      x9, x9, #0xc98
0xfffffe000959c8ac: cmp      x8, w8, sxtw
0xfffffe000959c8b0: add      x10, x9, w8, sxtw
0xfffffe000959c8b4: add      x16, x9, x8
0xfffffe000959c8b8: movk     x16, #0x2bad, lsl #48
0xfffffe000959c8bc: csel     x10, x10, x16, eq
0xfffffe000959c8c0: ldr      x8, [x10]
0xfffffe000959c8c4: b        #0xfffffe000959ce78
0xfffffe000959c8c8: adrp     x8, #0xfffffe00074b8000
0xfffffe000959c8cc: add      x8, x8, #0x69c
0xfffffe000959c8d0: adrp     x9, #0xfffffe00074be000
0xfffffe000959c8d4: add      x9, x9, #0x538
0xfffffe000959c8d8: stp      x8, x9, [sp]
0xfffffe000959c8dc: adrp     x0, #0xfffffe00074b7000
0xfffffe000959c8e0: add      x0, x0, #0xec0
0xfffffe000959c8e4: adrp     x1, #0xfffffe0008163000
0xfffffe000959c8e8: ldr      x1, [x1, #0xbf8]
0xfffffe000959c8ec: adrp     x3, #0xfffffe00074e5000
0xfffffe000959c8f0: add      x3, x3, #0xf7d
0xfffffe000959c8f4: mov      w2, #0
0xfffffe000959c8f8: bl       #0xfffffe000964c288
0xfffffe000959c8fc: b        #0xfffffe000959d620
0xfffffe000959c900: adrp     x8, #0xfffffe00074b8000
0xfffffe000959c904: add      x8, x8, #0x69c
0xfffffe000959c908: adrp     x26, #0xfffffe00074be000
0xfffffe000959c90c: add      x26, x26, #0x538
0xfffffe000959c910: stp      x8, x26, [sp]
0xfffffe000959c914: adrp     x0, #0xfffffe00074b7000
0xfffffe000959c918: add      x0, x0, #0xec0
0xfffffe000959c91c: adrp     x1, #0xfffffe0008163000
0xfffffe000959c920: ldr      x1, [x1, #0xbf8]
0xfffffe000959c924: adrp     x3, #0xfffffe00074e5000
0xfffffe000959c928: add      x3, x3, #0xf99
0xfffffe000959c92c: mov      w2, #0
0xfffffe000959c930: bl       #0xfffffe000964c288
0xfffffe000959c934: ldr      x8, [sp, #0x28]
0xfffffe000959c938: ldr      x9, [x8, #0x38]
0xfffffe000959c93c: cmp      x9, x23
0xfffffe000959c940: b.hi     #0xfffffe000959c958
0xfffffe000959c944: add      x10, x23, #0x34
0xfffffe000959c948: ldr      x8, [x8]
0xfffffe000959c94c: add      x8, x8, x9
0xfffffe000959c950: cmp      x10, x8
0xfffffe000959c954: b.ls     #0xfffffe000959cd78
0xfffffe000959c958: ldr      w8, [x19, #0x180]
0xfffffe000959c95c: cmp      w8, #3
0xfffffe000959c960: b.hi     #0xfffffe000959cb0c
0xfffffe000959c964: lsl      x8, x8, #3
0xfffffe000959c968: adrp     x9, #0xfffffe0008142000
0xfffffe000959c96c: add      x9, x9, #0xc98
0xfffffe000959c970: cmp      x8, w8, sxtw
0xfffffe000959c974: add      x10, x9, w8, sxtw
0xfffffe000959c978: add      x16, x9, x8
0xfffffe000959c97c: movk     x16, #0x2bad, lsl #48
0xfffffe000959c980: csel     x10, x10, x16, eq
0xfffffe000959c984: ldr      x8, [x10]
0xfffffe000959c988: b        #0xfffffe000959cb14
0xfffffe000959c98c: adrp     x8, #0xfffffe00074b8000
0xfffffe000959c990: add      x8, x8, #0x69c
0xfffffe000959c994: mov      w24, #0x2e8
0xfffffe000959c998: movk     w24, #0xe000, lsl #16
0xfffffe000959c99c: adrp     x9, #0xfffffe00074be000
0xfffffe000959c9a0: add      x9, x9, #0x538
0xfffffe000959c9a4: stp      x8, x9, [sp]
0xfffffe000959c9a8: adrp     x0, #0xfffffe00074b7000
0xfffffe000959c9ac: add      x0, x0, #0xec0
0xfffffe000959c9b0: adrp     x1, #0xfffffe0008163000
0xfffffe000959c9b4: ldr      x1, [x1, #0xbf8]
0xfffffe000959c9b8: adrp     x3, #0xfffffe00074e6000
0xfffffe000959c9bc: add      x3, x3, #0x24a
0xfffffe000959c9c0: mov      w2, #0x10
0xfffffe000959c9c4: bl       #0xfffffe000964c288
0xfffffe000959c9c8: b        #0xfffffe000959c2c4
0xfffffe000959c9cc: adrp     x8, #0xfffffe00074b8000
0xfffffe000959c9d0: add      x8, x8, #0x69c
0xfffffe000959c9d4: mov      w24, #0x2e8
0xfffffe000959c9d8: movk     w24, #0xe000, lsl #16
0xfffffe000959c9dc: adrp     x9, #0xfffffe00074be000
0xfffffe000959c9e0: add      x9, x9, #0x538
0xfffffe000959c9e4: stp      x8, x9, [sp]
0xfffffe000959c9e8: adrp     x0, #0xfffffe00074b7000
0xfffffe000959c9ec: add      x0, x0, #0xec0
0xfffffe000959c9f0: adrp     x1, #0xfffffe0008163000
0xfffffe000959c9f4: ldr      x1, [x1, #0xbf8]
0xfffffe000959c9f8: adrp     x3, #0xfffffe00074e6000
0xfffffe000959c9fc: add      x3, x3, #0x31b
0xfffffe000959ca00: mov      w2, #0x10
0xfffffe000959ca04: bl       #0xfffffe000964c288
0xfffffe000959ca08: b        #0xfffffe000959c2c4
0xfffffe000959ca0c: adrp     x8, #0xfffffe00074b8000
0xfffffe000959ca10: add      x8, x8, #0x69c
0xfffffe000959ca14: mov      w24, #0x2e8
0xfffffe000959ca18: movk     w24, #0xe000, lsl #16
0xfffffe000959ca1c: adrp     x9, #0xfffffe00074be000
0xfffffe000959ca20: add      x9, x9, #0x538
0xfffffe000959ca24: stp      x8, x9, [sp]
0xfffffe000959ca28: adrp     x0, #0xfffffe00074b7000
0xfffffe000959ca2c: add      x0, x0, #0xec0
0xfffffe000959ca30: adrp     x1, #0xfffffe0008163000
0xfffffe000959ca34: ldr      x1, [x1, #0xbf8]
0xfffffe000959ca38: adrp     x3, #0xfffffe00074e6000
0xfffffe000959ca3c: add      x3, x3, #0x3fb
0xfffffe000959ca40: mov      w2, #0x10
0xfffffe000959ca44: bl       #0xfffffe000964c288
0xfffffe000959ca48: b        #0xfffffe000959c2c4
0xfffffe000959ca4c: adrp     x8, #0xfffffe00074b8000
0xfffffe000959ca50: add      x8, x8, #0x69c
0xfffffe000959ca54: mov      w24, #0x2e8
0xfffffe000959ca58: movk     w24, #0xe000, lsl #16
0xfffffe000959ca5c: adrp     x9, #0xfffffe00074be000
0xfffffe000959ca60: add      x9, x9, #0x538
0xfffffe000959ca64: stp      x8, x9, [sp]
0xfffffe000959ca68: adrp     x0, #0xfffffe00074b7000
0xfffffe000959ca6c: add      x0, x0, #0xec0
0xfffffe000959ca70: adrp     x1, #0xfffffe0008163000
0xfffffe000959ca74: ldr      x1, [x1, #0xbf8]
0xfffffe000959ca78: adrp     x3, #0xfffffe00074e6000
0xfffffe000959ca7c: add      x3, x3, #0x50
0xfffffe000959ca80: mov      w2, #0x10
0xfffffe000959ca84: bl       #0xfffffe000964c288
0xfffffe000959ca88: b        #0xfffffe000959c2c4
0xfffffe000959ca8c: adrp     x8, #0xfffffe00074b8000
0xfffffe000959ca90: add      x8, x8, #0x69c
0xfffffe000959ca94: mov      w24, #0x2e8
0xfffffe000959ca98: movk     w24, #0xe000, lsl #16
0xfffffe000959ca9c: adrp     x9, #0xfffffe00074be000
0xfffffe000959caa0: add      x9, x9, #0x538
0xfffffe000959caa4: stp      x8, x9, [sp]
0xfffffe000959caa8: adrp     x0, #0xfffffe00074b7000
0xfffffe000959caac: add      x0, x0, #0xec0
0xfffffe000959cab0: adrp     x1, #0xfffffe0008163000
0xfffffe000959cab4: ldr      x1, [x1, #0xbf8]
0xfffffe000959cab8: adrp     x3, #0xfffffe00074e6000
0xfffffe000959cabc: add      x3, x3, #0x177
0xfffffe000959cac0: mov      w2, #0x10
0xfffffe000959cac4: bl       #0xfffffe000964c288
0xfffffe000959cac8: b        #0xfffffe000959c2c4
0xfffffe000959cacc: adrp     x8, #0xfffffe00074b8000
0xfffffe000959cad0: add      x8, x8, #0x69c
0xfffffe000959cad4: mov      w24, #0x2e8
0xfffffe000959cad8: movk     w24, #0xe000, lsl #16
0xfffffe000959cadc: adrp     x9, #0xfffffe00074be000
0xfffffe000959cae0: add      x9, x9, #0x538
0xfffffe000959cae4: stp      x8, x9, [sp]
0xfffffe000959cae8: adrp     x0, #0xfffffe00074b7000
0xfffffe000959caec: add      x0, x0, #0xec0
0xfffffe000959caf0: adrp     x1, #0xfffffe0008163000
0xfffffe000959caf4: ldr      x1, [x1, #0xbf8]
0xfffffe000959caf8: adrp     x3, #0xfffffe00074e5000
0xfffffe000959cafc: add      x3, x3, #0xed7
0xfffffe000959cb00: mov      w2, #0x10
0xfffffe000959cb04: bl       #0xfffffe000964c288
0xfffffe000959cb08: b        #0xfffffe000959c2c4
0xfffffe000959cb0c: adrp     x8, #0xfffffe00074b8000
0xfffffe000959cb10: add      x8, x8, #0x69c
0xfffffe000959cb14: mov      w24, #0x2e8
0xfffffe000959cb18: movk     w24, #0xe000, lsl #16
0xfffffe000959cb1c: stp      x8, x26, [sp]
0xfffffe000959cb20: adrp     x0, #0xfffffe00074b7000
0xfffffe000959cb24: add      x0, x0, #0xec0
0xfffffe000959cb28: adrp     x1, #0xfffffe0008163000
0xfffffe000959cb2c: ldr      x1, [x1, #0xbf8]
0xfffffe000959cb30: adrp     x3, #0xfffffe00074e5000
0xfffffe000959cb34: add      x3, x3, #0xfb5
0xfffffe000959cb38: mov      w2, #0x10
0xfffffe000959cb3c: bl       #0xfffffe000964c288
0xfffffe000959cb40: b        #0xfffffe000959c2c4
0xfffffe000959cb44: adrp     x8, #0xfffffe00074b8000
0xfffffe000959cb48: add      x8, x8, #0x69c
0xfffffe000959cb4c: mov      w24, #0x2e8
0xfffffe000959cb50: movk     w24, #0xe000, lsl #16
0xfffffe000959cb54: adrp     x9, #0xfffffe00074be000
0xfffffe000959cb58: add      x9, x9, #0x538
0xfffffe000959cb5c: stp      x8, x9, [sp]
0xfffffe000959cb60: adrp     x0, #0xfffffe00074b7000
0xfffffe000959cb64: add      x0, x0, #0xec0
0xfffffe000959cb68: adrp     x1, #0xfffffe0008163000
0xfffffe000959cb6c: ldr      x1, [x1, #0xbf8]
0xfffffe000959cb70: adrp     x3, #0xfffffe00074e6000
0xfffffe000959cb74: add      x3, x3, #0x35e
0xfffffe000959cb78: mov      w2, #0x10
0xfffffe000959cb7c: bl       #0xfffffe000964c288
0xfffffe000959cb80: b        #0xfffffe000959c2c4
0xfffffe000959cb84: adrp     x8, #0xfffffe00074b8000
0xfffffe000959cb88: add      x8, x8, #0x69c
0xfffffe000959cb8c: mov      w24, #0x2e8
0xfffffe000959cb90: movk     w24, #0xe000, lsl #16
0xfffffe000959cb94: adrp     x9, #0xfffffe00074be000
0xfffffe000959cb98: add      x9, x9, #0x538
0xfffffe000959cb9c: stp      x8, x9, [sp]
0xfffffe000959cba0: adrp     x0, #0xfffffe00074b7000
0xfffffe000959cba4: add      x0, x0, #0xec0
0xfffffe000959cba8: adrp     x1, #0xfffffe0008163000
0xfffffe000959cbac: ldr      x1, [x1, #0xbf8]
0xfffffe000959cbb0: adrp     x3, #0xfffffe00074e6000
0xfffffe000959cbb4: add      x3, x3, #1
0xfffffe000959cbb8: mov      w2, #0x10
0xfffffe000959cbbc: bl       #0xfffffe000964c288
0xfffffe000959cbc0: b        #0xfffffe000959c2c4
0xfffffe000959cbc4: adrp     x8, #0xfffffe00074b8000
0xfffffe000959cbc8: add      x8, x8, #0x69c
0xfffffe000959cbcc: mov      w24, #0x2e8
0xfffffe000959cbd0: movk     w24, #0xe000, lsl #16
0xfffffe000959cbd4: adrp     x9, #0xfffffe00074be000
0xfffffe000959cbd8: add      x9, x9, #0x538
0xfffffe000959cbdc: stp      x8, x9, [sp]
0xfffffe000959cbe0: adrp     x0, #0xfffffe00074b7000
0xfffffe000959cbe4: add      x0, x0, #0xec0
0xfffffe000959cbe8: adrp     x1, #0xfffffe0008163000
0xfffffe000959cbec: ldr      x1, [x1, #0xbf8]
0xfffffe000959cbf0: adrp     x3, #0xfffffe00074e6000
0xfffffe000959cbf4: add      x3, x3, #0x126
0xfffffe000959cbf8: mov      w2, #0x10
0xfffffe000959cbfc: bl       #0xfffffe000964c288
0xfffffe000959cc00: b        #0xfffffe000959c2c4
0xfffffe000959cc04: ldr      x0, [x19, #0x3fb8]
0xfffffe000959cc08: cbz      x0, #0xfffffe000959cc14
0xfffffe000959cc0c: ldr      w1, [x23, #8]
0xfffffe000959cc10: bl       #0xfffffe00095da5e0  ; _iopAddrFixup+0xb81c
0xfffffe000959cc14: ldr      w8, [x19, #0x8d0]
0xfffffe000959cc18: ldr      w9, [x23, #8]
0xfffffe000959cc1c: cmp      w8, w9
0xfffffe000959cc20: b.ne     #0xfffffe000959d01c
0xfffffe000959cc24: adrp     x9, #0xfffffe000cb6d000
0xfffffe000959cc28: add      x9, x9, #0xc60
0xfffffe000959cc2c: ldrb     w9, [x9, #1]
0xfffffe000959cc30: tbz      w9, #2, #0xfffffe000959d620
0xfffffe000959cc34: ldr      w9, [x19, #0x180]
0xfffffe000959cc38: cmp      w9, #3
0xfffffe000959cc3c: b.hi     #0xfffffe000959d460
0xfffffe000959cc40: lsl      x9, x9, #3
0xfffffe000959cc44: adrp     x10, #0xfffffe0008142000
0xfffffe000959cc48: add      x10, x10, #0xc98
0xfffffe000959cc4c: cmp      x9, w9, sxtw
0xfffffe000959cc50: add      x11, x10, w9, sxtw
0xfffffe000959cc54: add      x16, x10, x9
0xfffffe000959cc58: movk     x16, #0x2bad, lsl #48
0xfffffe000959cc5c: csel     x11, x11, x16, eq
0xfffffe000959cc60: ldr      x9, [x11]
0xfffffe000959cc64: b        #0xfffffe000959d468
0xfffffe000959cc68: mov      x0, x19
0xfffffe000959cc6c: mov      x1, x23
0xfffffe000959cc70: bl       #0xfffffe00095f3fc4
0xfffffe000959cc74: b        #0xfffffe000959d620
0xfffffe000959cc78: ldrb     w8, [x19, #0x8cd]
0xfffffe000959cc7c: tbz      w8, #0, #0xfffffe000959d4e8
0xfffffe000959cc80: ldr      w8, [x23, #0x20]
0xfffffe000959cc84: str      w8, [x19, #0x8d0]
0xfffffe000959cc88: adrp     x9, #0xfffffe000cb6d000
0xfffffe000959cc8c: add      x9, x9, #0xc60
0xfffffe000959cc90: ldrb     w9, [x9, #1]
0xfffffe000959cc94: tbz      w9, #2, #0xfffffe000959d4d8
0xfffffe000959cc98: ldr      w9, [x23, #0x14]
0xfffffe000959cc9c: ldr      w10, [x23, #0x1c]
0xfffffe000959cca0: ldr      w11, [x19, #0x180]
0xfffffe000959cca4: cmp      w11, #3
0xfffffe000959cca8: b.hi     #0xfffffe000959d49c
0xfffffe000959ccac: lsl      x11, x11, #3
0xfffffe000959ccb0: adrp     x12, #0xfffffe0008142000
0xfffffe000959ccb4: add      x12, x12, #0xc98
0xfffffe000959ccb8: cmp      x11, w11, sxtw
0xfffffe000959ccbc: add      x13, x12, w11, sxtw
0xfffffe000959ccc0: add      x16, x12, x11
0xfffffe000959ccc4: movk     x16, #0x2bad, lsl #48
0xfffffe000959ccc8: csel     x13, x13, x16, eq
0xfffffe000959cccc: ldr      x11, [x13]
0xfffffe000959ccd0: b        #0xfffffe000959d4a4
0xfffffe000959ccd4: add      x24, x23, #0x10
0xfffffe000959ccd8: adrp     x8, #0xfffffe000cb6d000
0xfffffe000959ccdc: add      x8, x8, #0xc60
0xfffffe000959cce0: ldrb     w8, [x8, #1]
0xfffffe000959cce4: tbz      w8, #2, #0xfffffe000959d194
0xfffffe000959cce8: ldr      w8, [x19, #0x180]
0xfffffe000959ccec: cmp      w8, #3
0xfffffe000959ccf0: b.hi     #0xfffffe000959d158
0xfffffe000959ccf4: lsl      x8, x8, #3
0xfffffe000959ccf8: adrp     x9, #0xfffffe0008142000
0xfffffe000959ccfc: add      x9, x9, #0xc98
0xfffffe000959cd00: cmp      x8, w8, sxtw
0xfffffe000959cd04: add      x10, x9, w8, sxtw
0xfffffe000959cd08: add      x16, x9, x8
0xfffffe000959cd0c: movk     x16, #0x2bad, lsl #48
0xfffffe000959cd10: csel     x10, x10, x16, eq
0xfffffe000959cd14: ldr      x8, [x10]
0xfffffe000959cd18: b        #0xfffffe000959d160
0xfffffe000959cd1c: add      x24, x23, #0x10
0xfffffe000959cd20: adrp     x8, #0xfffffe000cb6d000
0xfffffe000959cd24: add      x8, x8, #0xc60
0xfffffe000959cd28: ldrb     w8, [x8, #1]
0xfffffe000959cd2c: tbz      w8, #2, #0xfffffe000959d23c
0xfffffe000959cd30: ldr      w8, [x19, #0x180]
0xfffffe000959cd34: cmp      w8, #3
0xfffffe000959cd38: b.hi     #0xfffffe000959d200
0xfffffe000959cd3c: lsl      x8, x8, #3
0xfffffe000959cd40: adrp     x9, #0xfffffe0008142000
0xfffffe000959cd44: add      x9, x9, #0xc98
0xfffffe000959cd48: cmp      x8, w8, sxtw
0xfffffe000959cd4c: add      x10, x9, w8, sxtw
0xfffffe000959cd50: add      x16, x9, x8
0xfffffe000959cd54: movk     x16, #0x2bad, lsl #48
0xfffffe000959cd58: csel     x10, x10, x16, eq
0xfffffe000959cd5c: ldr      x8, [x10]
0xfffffe000959cd60: b        #0xfffffe000959d208
0xfffffe000959cd64: bl       #0xfffffe000959d85c
0xfffffe000959cd68: mov      x25, x0
0xfffffe000959cd6c: cbz      x0, #0xfffffe000959d0e8
0xfffffe000959cd70: mov      w24, #0
0xfffffe000959cd74: b        #0xfffffe000959d420
0xfffffe000959cd78: mov      x0, x19
0xfffffe000959cd7c: mov      x1, x23
0xfffffe000959cd80: bl       #0xfffffe00095f3e08
0xfffffe000959cd84: b        #0xfffffe000959d620
0xfffffe000959cd88: ldr      x0, [x23, #0x430]
0xfffffe000959cd8c: bl       #0xfffffe000964c338
0xfffffe000959cd90: str      x0, [x23, #0x430]
0xfffffe000959cd94: ldrb     w8, [x19, #0x8cd]
0xfffffe000959cd98: tbz      w8, #0, #0xfffffe000959d5b0
0xfffffe000959cd9c: ldr      w8, [x23, #0x428]
0xfffffe000959cda0: str      w8, [x19, #0x8d0]
0xfffffe000959cda4: adrp     x9, #0xfffffe000cb6d000
0xfffffe000959cda8: add      x9, x9, #0xc60
0xfffffe000959cdac: ldrb     w9, [x9, #1]
0xfffffe000959cdb0: tbz      w9, #2, #0xfffffe000959d5a0
0xfffffe000959cdb4: ldr      w9, [x23, #0x14]
0xfffffe000959cdb8: ldr      w10, [x23, #0x1c]
0xfffffe000959cdbc: ldr      w11, [x19, #0x180]
0xfffffe000959cdc0: cmp      w11, #3
0xfffffe000959cdc4: b.hi     #0xfffffe000959d564
0xfffffe000959cdc8: lsl      x11, x11, #3
0xfffffe000959cdcc: adrp     x12, #0xfffffe0008142000
0xfffffe000959cdd0: add      x12, x12, #0xc98
0xfffffe000959cdd4: cmp      x11, w11, sxtw
0xfffffe000959cdd8: add      x13, x12, w11, sxtw
0xfffffe000959cddc: add      x16, x12, x11
0xfffffe000959cde0: movk     x16, #0x2bad, lsl #48
0xfffffe000959cde4: csel     x13, x13, x16, eq
0xfffffe000959cde8: ldr      x11, [x13]
0xfffffe000959cdec: b        #0xfffffe000959d56c
0xfffffe000959cdf0: ldur     d0, [x25, #0xc]
0xfffffe000959cdf4: scvtf    d0, d0
0xfffffe000959cdf8: ldur     d1, [x25, #0x1c]
0xfffffe000959cdfc: ldr      d2, [x23, #0x20]
0xfffffe000959ce00: ucvtf    d2, d2
0xfffffe000959ce04: fmadd    d0, d1, d2, d0
0xfffffe000959ce08: fcvtzu   x2, d0
0xfffffe000959ce0c: ldr      w0, [x19, #0x3bc4]
0xfffffe000959ce10: ldrh     w8, [x23, #0xc]
0xfffffe000959ce14: mov      w1, #0x8000
0xfffffe000959ce18: movk     w1, #0x61b, lsl #16
0xfffffe000959ce1c: bfxil    w1, w8, #0, #0xc
0xfffffe000959ce20: ldp      w3, w4, [x23, #0x10]
0xfffffe000959ce24: ldp      w5, w6, [x23, #0x18]
0xfffffe000959ce28: b        #0xfffffe000959ce64
0xfffffe000959ce2c: ldur     d0, [x25, #0xc]
0xfffffe000959ce30: scvtf    d0, d0
0xfffffe000959ce34: ldur     d1, [x25, #0x1c]
0xfffffe000959ce38: ldr      d2, [x23, #0x30]
0xfffffe000959ce3c: ucvtf    d2, d2
0xfffffe000959ce40: fmadd    d0, d1, d2, d0
0xfffffe000959ce44: fcvtzu   x2, d0
0xfffffe000959ce48: ldr      w0, [x19, #0x3bc4]
0xfffffe000959ce4c: ldrh     w8, [x23, #0xc]
0xfffffe000959ce50: mov      w1, #0x8000
0xfffffe000959ce54: movk     w1, #0x61b, lsl #16
0xfffffe000959ce58: bfxil    w1, w8, #0, #0xc
0xfffffe000959ce5c: ldp      x3, x4, [x23, #0x10]
0xfffffe000959ce60: ldp      x5, x6, [x23, #0x20]
0xfffffe000959ce64: mov      x7, #0
0xfffffe000959ce68: bl       #0xfffffe000964c428
0xfffffe000959ce6c: b        #0xfffffe000959d620
0xfffffe000959ce70: adrp     x8, #0xfffffe00074b8000
0xfffffe000959ce74: add      x8, x8, #0x69c
0xfffffe000959ce78: ldrh     w9, [x23, #4]
0xfffffe000959ce7c: str      x9, [sp, #0x10]
0xfffffe000959ce80: adrp     x9, #0xfffffe00074be000
0xfffffe000959ce84: add      x9, x9, #0x538
0xfffffe000959ce88: stp      x8, x9, [sp]
0xfffffe000959ce8c: adrp     x0, #0xfffffe00074b7000
0xfffffe000959ce90: add      x0, x0, #0xec0
0xfffffe000959ce94: adrp     x1, #0xfffffe0008163000
0xfffffe000959ce98: ldr      x1, [x1, #0xbf8]
0xfffffe000959ce9c: adrp     x3, #0xfffffe00074e6000
0xfffffe000959cea0: add      x3, x3, #0x477
0xfffffe000959cea4: mov      w2, #0
0xfffffe000959cea8: bl       #0xfffffe000964c288
0xfffffe000959ceac: ldr      x8, [sp, #0x28]
0xfffffe000959ceb0: ldr      x9, [x8, #0x38]
0xfffffe000959ceb4: cmp      x9, x23
0xfffffe000959ceb8: b.hi     #0xfffffe000959ced0
0xfffffe000959cebc: add      x10, x23, #0x18
0xfffffe000959cec0: ldr      x8, [x8]
0xfffffe000959cec4: add      x8, x8, x9
0xfffffe000959cec8: cmp      x10, x8
0xfffffe000959cecc: b.ls     #0xfffffe000959cf44
0xfffffe000959ced0: ldr      w8, [x19, #0x180]
0xfffffe000959ced4: cmp      w8, #3
0xfffffe000959ced8: b.hi     #0xfffffe000959cf04
0xfffffe000959cedc: lsl      x8, x8, #3
0xfffffe000959cee0: adrp     x9, #0xfffffe0008142000
0xfffffe000959cee4: add      x9, x9, #0xc98
0xfffffe000959cee8: cmp      x8, w8, sxtw
0xfffffe000959ceec: add      x10, x9, w8, sxtw
0xfffffe000959cef0: add      x16, x9, x8
0xfffffe000959cef4: movk     x16, #0x2bad, lsl #48
0xfffffe000959cef8: csel     x10, x10, x16, eq
0xfffffe000959cefc: ldr      x8, [x10]
0xfffffe000959cf00: b        #0xfffffe000959cf0c
0xfffffe000959cf04: adrp     x8, #0xfffffe00074b8000
0xfffffe000959cf08: add      x8, x8, #0x69c
0xfffffe000959cf0c: mov      w24, #0x2e8
0xfffffe000959cf10: movk     w24, #0xe000, lsl #16
0xfffffe000959cf14: adrp     x9, #0xfffffe00074be000
0xfffffe000959cf18: add      x9, x9, #0x538
0xfffffe000959cf1c: stp      x8, x9, [sp]
0xfffffe000959cf20: adrp     x0, #0xfffffe00074b7000
0xfffffe000959cf24: add      x0, x0, #0xec0
0xfffffe000959cf28: adrp     x1, #0xfffffe0008163000
0xfffffe000959cf2c: ldr      x1, [x1, #0xbf8]
0xfffffe000959cf30: adrp     x3, #0xfffffe00074e6000
0xfffffe000959cf34: add      x3, x3, #0x4b0
0xfffffe000959cf38: mov      w2, #0x10
0xfffffe000959cf3c: bl       #0xfffffe000964c288
0xfffffe000959cf40: b        #0xfffffe000959c2c4
0xfffffe000959cf44: mov      w8, #0x3f69
0xfffffe000959cf48: add      x27, x19, x8
0xfffffe000959cf4c: ldr      w8, [x19, #0x180]
0xfffffe000959cf50: cmp      w8, #3
0xfffffe000959cf54: b.hi     #0xfffffe000959d054
0xfffffe000959cf58: lsl      x8, x8, #3
0xfffffe000959cf5c: adrp     x9, #0xfffffe0008142000
0xfffffe000959cf60: add      x9, x9, #0xc98
0xfffffe000959cf64: cmp      x8, w8, sxtw
0xfffffe000959cf68: add      x10, x9, w8, sxtw
0xfffffe000959cf6c: add      x16, x9, x8
0xfffffe000959cf70: movk     x16, #0x2bad, lsl #48
0xfffffe000959cf74: csel     x10, x10, x16, eq
0xfffffe000959cf78: ldr      x8, [x10]
0xfffffe000959cf7c: b        #0xfffffe000959d05c
0xfffffe000959cf80: cmp      w8, #0x108
0xfffffe000959cf84: b.eq     #0xfffffe000959d854
0xfffffe000959cf88: mov      w0, #0x20
0xfffffe000959cf8c: movk     w0, #0x61b, lsl #16
0xfffffe000959cf90: mov      w1, #0xe
0xfffffe000959cf94: mov      x2, #0
0xfffffe000959cf98: mov      x3, #0
0xfffffe000959cf9c: mov      x4, #0
0xfffffe000959cfa0: mov      x5, #0
0xfffffe000959cfa4: bl       #0xfffffe000964c418
0xfffffe000959cfa8: ldr      w8, [x19, #0x180]
0xfffffe000959cfac: cmp      w8, #3
0xfffffe000959cfb0: b.hi     #0xfffffe000959cfdc
0xfffffe000959cfb4: lsl      x8, x8, #3
0xfffffe000959cfb8: adrp     x9, #0xfffffe0008142000
0xfffffe000959cfbc: add      x9, x9, #0xc98
0xfffffe000959cfc0: cmp      x8, w8, sxtw
0xfffffe000959cfc4: add      x10, x9, w8, sxtw
0xfffffe000959cfc8: add      x16, x9, x8
0xfffffe000959cfcc: movk     x16, #0x2bad, lsl #48
0xfffffe000959cfd0: csel     x10, x10, x16, eq
0xfffffe000959cfd4: ldr      x8, [x10]
0xfffffe000959cfd8: b        #0xfffffe000959cfe4
0xfffffe000959cfdc: adrp     x8, #0xfffffe00074b8000
0xfffffe000959cfe0: add      x8, x8, #0x69c
0xfffffe000959cfe4: ldrh     w9, [x23, #4]
0xfffffe000959cfe8: str      x9, [sp, #0x10]
0xfffffe000959cfec: adrp     x9, #0xfffffe00074be000
0xfffffe000959cff0: add      x9, x9, #0x538
0xfffffe000959cff4: stp      x8, x9, [sp]
0xfffffe000959cff8: adrp     x0, #0xfffffe00074b7000
0xfffffe000959cffc: add      x0, x0, #0xec0
0xfffffe000959d000: adrp     x1, #0xfffffe0008163000
0xfffffe000959d004: ldr      x1, [x1, #0xbf8]
0xfffffe000959d008: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d00c: add      x3, x3, #0x55a
0xfffffe000959d010: mov      w2, #0
0xfffffe000959d014: bl       #0xfffffe000964c288
0xfffffe000959d018: b        #0xfffffe000959d620
0xfffffe000959d01c: str      w9, [x19, #0x8d0]
0xfffffe000959d020: ldr      w8, [x19, #0x180]
0xfffffe000959d024: cmp      w8, #3
0xfffffe000959d028: b.hi     #0xfffffe000959d11c
0xfffffe000959d02c: lsl      x8, x8, #3
0xfffffe000959d030: adrp     x10, #0xfffffe0008142000
0xfffffe000959d034: add      x10, x10, #0xc98
0xfffffe000959d038: cmp      x8, w8, sxtw
0xfffffe000959d03c: add      x11, x10, w8, sxtw
0xfffffe000959d040: add      x16, x10, x8
0xfffffe000959d044: movk     x16, #0x2bad, lsl #48
0xfffffe000959d048: csel     x11, x11, x16, eq
0xfffffe000959d04c: ldr      x8, [x11]
0xfffffe000959d050: b        #0xfffffe000959d124
0xfffffe000959d054: adrp     x8, #0xfffffe00074b8000
0xfffffe000959d058: add      x8, x8, #0x69c
0xfffffe000959d05c: ldr      w9, [x23, #8]
0xfffffe000959d060: adrp     x26, #0xfffffe00074be000
0xfffffe000959d064: add      x26, x26, #0x538
0xfffffe000959d068: stp      x26, x9, [sp, #8]
0xfffffe000959d06c: str      x8, [sp]
0xfffffe000959d070: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d074: add      x0, x0, #0xec0
0xfffffe000959d078: adrp     x1, #0xfffffe0008163000
0xfffffe000959d07c: ldr      x1, [x1, #0xbf8]
0xfffffe000959d080: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d084: add      x3, x3, #0x4f3
0xfffffe000959d088: mov      w2, #0
0xfffffe000959d08c: bl       #0xfffffe000964c288
0xfffffe000959d090: ldrb     w8, [x27]
0xfffffe000959d094: tbz      w8, #0, #0xfffffe000959d620
0xfffffe000959d098: ldr      x0, [x19, #0x858]
0xfffffe000959d09c: cbz      x0, #0xfffffe000959d620
0xfffffe000959d0a0: ldr      x8, [x19, #0x178]
0xfffffe000959d0a4: ldrb     w8, [x8, #0x199]
0xfffffe000959d0a8: tbz      w8, #0, #0xfffffe000959d620
0xfffffe000959d0ac: ldrb     w8, [x24, #1]
0xfffffe000959d0b0: tbz      w8, #2, #0xfffffe000959d820
0xfffffe000959d0b4: ldr      w8, [x19, #0x180]
0xfffffe000959d0b8: cmp      w8, #3
0xfffffe000959d0bc: b.hi     #0xfffffe000959d7e8
0xfffffe000959d0c0: lsl      x8, x8, #3
0xfffffe000959d0c4: adrp     x9, #0xfffffe0008142000
0xfffffe000959d0c8: add      x9, x9, #0xc98
0xfffffe000959d0cc: cmp      x8, w8, sxtw
0xfffffe000959d0d0: add      x10, x9, w8, sxtw
0xfffffe000959d0d4: add      x16, x9, x8
0xfffffe000959d0d8: movk     x16, #0x2bad, lsl #48
0xfffffe000959d0dc: csel     x10, x10, x16, eq
0xfffffe000959d0e0: ldr      x8, [x10]
0xfffffe000959d0e4: b        #0xfffffe000959d7f0
0xfffffe000959d0e8: ldr      w8, [x19, #0x180]
0xfffffe000959d0ec: cmp      w8, #3
0xfffffe000959d0f0: b.hi     #0xfffffe000959d3e0
0xfffffe000959d0f4: lsl      x8, x8, #3
0xfffffe000959d0f8: adrp     x9, #0xfffffe0008142000
0xfffffe000959d0fc: add      x9, x9, #0xc98
0xfffffe000959d100: cmp      x8, w8, sxtw
0xfffffe000959d104: add      x10, x9, w8, sxtw
0xfffffe000959d108: add      x16, x9, x8
0xfffffe000959d10c: movk     x16, #0x2bad, lsl #48
0xfffffe000959d110: csel     x10, x10, x16, eq
0xfffffe000959d114: ldr      x8, [x10]
0xfffffe000959d118: b        #0xfffffe000959d3e8
0xfffffe000959d11c: adrp     x8, #0xfffffe00074b8000
0xfffffe000959d120: add      x8, x8, #0x69c
0xfffffe000959d124: str      x9, [sp, #0x10]
0xfffffe000959d128: adrp     x9, #0xfffffe00074be000
0xfffffe000959d12c: add      x9, x9, #0x538
0xfffffe000959d130: stp      x8, x9, [sp]
0xfffffe000959d134: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d138: add      x0, x0, #0xec0
0xfffffe000959d13c: adrp     x1, #0xfffffe0008163000
0xfffffe000959d140: ldr      x1, [x1, #0xbf8]
0xfffffe000959d144: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d148: add      x3, x3, #0x299
0xfffffe000959d14c: mov      w2, #0
0xfffffe000959d150: bl       #0xfffffe000964c288
0xfffffe000959d154: b        #0xfffffe000959d620
0xfffffe000959d158: adrp     x8, #0xfffffe00074b8000
0xfffffe000959d15c: add      x8, x8, #0x69c
0xfffffe000959d160: ldr      w9, [x23, #0xc]
0xfffffe000959d164: str      x9, [sp, #0x10]
0xfffffe000959d168: adrp     x9, #0xfffffe00074be000
0xfffffe000959d16c: add      x9, x9, #0x538
0xfffffe000959d170: stp      x8, x9, [sp]
0xfffffe000959d174: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d178: add      x0, x0, #0xec0
0xfffffe000959d17c: adrp     x1, #0xfffffe0008163000
0xfffffe000959d180: ldr      x1, [x1, #0xbf8]
0xfffffe000959d184: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d188: add      x3, x3, #0xa5
0xfffffe000959d18c: mov      w2, #0
0xfffffe000959d190: bl       #0xfffffe000964c288
0xfffffe000959d194: ldr      w26, [x23, #0xc]
0xfffffe000959d198: cmp      w26, #0x41
0xfffffe000959d19c: b.lo     #0xfffffe000959d1d4
0xfffffe000959d1a0: ldr      w8, [x19, #0x180]
0xfffffe000959d1a4: cmp      w8, #3
0xfffffe000959d1a8: b.hi     #0xfffffe000959d2a4
0xfffffe000959d1ac: lsl      x8, x8, #3
0xfffffe000959d1b0: adrp     x9, #0xfffffe0008142000
0xfffffe000959d1b4: add      x9, x9, #0xc98
0xfffffe000959d1b8: cmp      x8, w8, sxtw
0xfffffe000959d1bc: add      x10, x9, w8, sxtw
0xfffffe000959d1c0: add      x16, x9, x8
0xfffffe000959d1c4: movk     x16, #0x2bad, lsl #48
0xfffffe000959d1c8: csel     x10, x10, x16, eq
0xfffffe000959d1cc: ldr      x8, [x10]
0xfffffe000959d1d0: b        #0xfffffe000959d2ac
0xfffffe000959d1d4: add      x8, x26, x26, lsl #1
0xfffffe000959d1d8: lsl      x8, x8, #4
0xfffffe000959d1dc: cmp      x8, w8, sxtw
0xfffffe000959d1e0: add      x1, x24, w8, sxtw
0xfffffe000959d1e4: add      x16, x24, x8
0xfffffe000959d1e8: movk     x16, #0x2bad, lsl #48
0xfffffe000959d1ec: csel     x1, x1, x16, eq
0xfffffe000959d1f0: mov      x0, x24
0xfffffe000959d1f4: bl       #0xfffffe000959d904
0xfffffe000959d1f8: cbnz     w26, #0xfffffe000959d2ec
0xfffffe000959d1fc: b        #0xfffffe000959d620
0xfffffe000959d200: adrp     x8, #0xfffffe00074b8000
0xfffffe000959d204: add      x8, x8, #0x69c
0xfffffe000959d208: ldr      w9, [x23, #0xc]
0xfffffe000959d20c: str      x9, [sp, #0x10]
0xfffffe000959d210: adrp     x9, #0xfffffe00074be000
0xfffffe000959d214: add      x9, x9, #0x538
0xfffffe000959d218: stp      x8, x9, [sp]
0xfffffe000959d21c: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d220: add      x0, x0, #0xec0
0xfffffe000959d224: adrp     x1, #0xfffffe0008163000
0xfffffe000959d228: ldr      x1, [x1, #0xbf8]
0xfffffe000959d22c: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d230: add      x3, x3, #0x1ce
0xfffffe000959d234: mov      w2, #0
0xfffffe000959d238: bl       #0xfffffe000964c288
0xfffffe000959d23c: ldr      w26, [x23, #0xc]
0xfffffe000959d240: cmp      w26, #0x41
0xfffffe000959d244: b.lo     #0xfffffe000959d27c
0xfffffe000959d248: ldr      w8, [x19, #0x180]
0xfffffe000959d24c: cmp      w8, #3
0xfffffe000959d250: b.hi     #0xfffffe000959d340
0xfffffe000959d254: lsl      x8, x8, #3
0xfffffe000959d258: adrp     x9, #0xfffffe0008142000
0xfffffe000959d25c: add      x9, x9, #0xc98
0xfffffe000959d260: cmp      x8, w8, sxtw
0xfffffe000959d264: add      x10, x9, w8, sxtw
0xfffffe000959d268: add      x16, x9, x8
0xfffffe000959d26c: movk     x16, #0x2bad, lsl #48
0xfffffe000959d270: csel     x10, x10, x16, eq
0xfffffe000959d274: ldr      x8, [x10]
0xfffffe000959d278: b        #0xfffffe000959d348
0xfffffe000959d27c: lsl      x8, x26, #6
0xfffffe000959d280: cmp      x8, w8, sxtw
0xfffffe000959d284: add      x1, x24, w8, sxtw
0xfffffe000959d288: add      x16, x24, x8
0xfffffe000959d28c: movk     x16, #0x2bad, lsl #48
0xfffffe000959d290: csel     x1, x1, x16, eq
0xfffffe000959d294: mov      x0, x24
0xfffffe000959d298: bl       #0xfffffe000959d93c
0xfffffe000959d29c: cbnz     w26, #0xfffffe000959d38c
0xfffffe000959d2a0: b        #0xfffffe000959d620
0xfffffe000959d2a4: adrp     x8, #0xfffffe00074b8000
0xfffffe000959d2a8: add      x8, x8, #0x69c
0xfffffe000959d2ac: adrp     x9, #0xfffffe00074be000
0xfffffe000959d2b0: add      x9, x9, #0x538
0xfffffe000959d2b4: stp      x9, x26, [sp, #8]
0xfffffe000959d2b8: str      x8, [sp]
0xfffffe000959d2bc: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d2c0: add      x0, x0, #0xec0
0xfffffe000959d2c4: adrp     x1, #0xfffffe0008163000
0xfffffe000959d2c8: ldr      x1, [x1, #0xbf8]
0xfffffe000959d2cc: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d2d0: add      x3, x3, #0xdd
0xfffffe000959d2d4: mov      w2, #0x10
0xfffffe000959d2d8: bl       #0xfffffe000964c288
0xfffffe000959d2dc: add      x1, x23, #0xc10
0xfffffe000959d2e0: mov      x0, x24
0xfffffe000959d2e4: bl       #0xfffffe000959d904
0xfffffe000959d2e8: mov      w26, #0x40
0xfffffe000959d2ec: mov      w23, #0x8000
0xfffffe000959d2f0: movk     w23, #0x61b, lsl #16
0xfffffe000959d2f4: ldur     d0, [x25, #0xc]
0xfffffe000959d2f8: scvtf    d0, d0
0xfffffe000959d2fc: ldur     d1, [x25, #0x1c]
0xfffffe000959d300: ldr      d2, [x24, #0x20]
0xfffffe000959d304: ucvtf    d2, d2
0xfffffe000959d308: fmadd    d0, d1, d2, d0
0xfffffe000959d30c: fcvtzu   x2, d0
0xfffffe000959d310: ldr      w0, [x19, #0x3bc4]
0xfffffe000959d314: ldrh     w8, [x24, #0xc]
0xfffffe000959d318: and      w8, w8, #0xfff
0xfffffe000959d31c: ldp      w3, w4, [x24, #0x10]
0xfffffe000959d320: ldp      w5, w6, [x24, #0x18]
0xfffffe000959d324: orr      w1, w8, w23
0xfffffe000959d328: mov      x7, #0
0xfffffe000959d32c: bl       #0xfffffe000964c428
0xfffffe000959d330: add      x24, x24, #0x30
0xfffffe000959d334: subs     w26, w26, #1
0xfffffe000959d338: b.ne     #0xfffffe000959d2f4
0xfffffe000959d33c: b        #0xfffffe000959d620
0xfffffe000959d340: adrp     x8, #0xfffffe00074b8000
0xfffffe000959d344: add      x8, x8, #0x69c
0xfffffe000959d348: adrp     x9, #0xfffffe00074be000
0xfffffe000959d34c: add      x9, x9, #0x538
0xfffffe000959d350: stp      x9, x26, [sp, #8]
0xfffffe000959d354: str      x8, [sp]
0xfffffe000959d358: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d35c: add      x0, x0, #0xec0
0xfffffe000959d360: adrp     x1, #0xfffffe0008163000
0xfffffe000959d364: ldr      x1, [x1, #0xbf8]
0xfffffe000959d368: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d36c: add      x3, x3, #0x208
0xfffffe000959d370: mov      w2, #0
0xfffffe000959d374: bl       #0xfffffe000964c288
0xfffffe000959d378: mov      w8, #0x1010
0xfffffe000959d37c: add      x1, x23, x8
0xfffffe000959d380: mov      x0, x24
0xfffffe000959d384: bl       #0xfffffe000959d93c
0xfffffe000959d388: mov      w26, #0x40
0xfffffe000959d38c: mov      w23, #0x8000
0xfffffe000959d390: movk     w23, #0x61b, lsl #16
0xfffffe000959d394: ldur     d0, [x25, #0xc]
0xfffffe000959d398: scvtf    d0, d0
0xfffffe000959d39c: ldur     d1, [x25, #0x1c]
0xfffffe000959d3a0: ldr      d2, [x24, #0x30]
0xfffffe000959d3a4: ucvtf    d2, d2
0xfffffe000959d3a8: fmadd    d0, d1, d2, d0
0xfffffe000959d3ac: fcvtzu   x2, d0
0xfffffe000959d3b0: ldr      w0, [x19, #0x3bc4]
0xfffffe000959d3b4: ldrh     w8, [x24, #0xc]
0xfffffe000959d3b8: and      w8, w8, #0xfff
0xfffffe000959d3bc: ldp      x3, x4, [x24, #0x10]
0xfffffe000959d3c0: ldp      x5, x6, [x24, #0x20]
0xfffffe000959d3c4: orr      w1, w8, w23
0xfffffe000959d3c8: mov      x7, #0
0xfffffe000959d3cc: bl       #0xfffffe000964c428
0xfffffe000959d3d0: add      x24, x24, #0x40
0xfffffe000959d3d4: subs     w26, w26, #1
0xfffffe000959d3d8: b.ne     #0xfffffe000959d394
0xfffffe000959d3dc: b        #0xfffffe000959d620
0xfffffe000959d3e0: adrp     x8, #0xfffffe00074b8000
0xfffffe000959d3e4: add      x8, x8, #0x69c
0xfffffe000959d3e8: adrp     x9, #0xfffffe00074be000
0xfffffe000959d3ec: add      x9, x9, #0x538
0xfffffe000959d3f0: stp      x8, x9, [sp]
0xfffffe000959d3f4: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d3f8: add      x0, x0, #0xec0
0xfffffe000959d3fc: adrp     x1, #0xfffffe0008163000
0xfffffe000959d400: ldr      x1, [x1, #0xbf8]
0xfffffe000959d404: adrp     x3, #0xfffffe00074e5000
0xfffffe000959d408: add      x3, x3, #0xf21
0xfffffe000959d40c: mov      w2, #0x10
0xfffffe000959d410: bl       #0xfffffe000964c288
0xfffffe000959d414: mov      w8, #0x2e8
0xfffffe000959d418: movk     w8, #0xe000, lsl #16
0xfffffe000959d41c: sub      w24, w8, #0x2b
0xfffffe000959d420: stp      x20, x21, [x25, #0x28]
0xfffffe000959d424: ldr      x8, [sp, #0x28]
0xfffffe000959d428: stp      x22, x8, [x25, #0x38]
0xfffffe000959d42c: stp      x23, x19, [x25, #0x48]
0xfffffe000959d430: ldr      x0, [x19, #0xd0]
0xfffffe000959d434: mov      x1, x25
0xfffffe000959d438: bl       #0xfffffe0009581b1c  ; __ZNSt3__110__function6__funcIZN37RtUnaryExpressionOperationDescription2
0xfffffe000959d43c: ldr      x16, [x25]
0xfffffe000959d440: mov      x17, x25
0xfffffe000959d444: movk     x17, #0xcda1, lsl #48
0xfffffe000959d448: autda    x16, x17
0xfffffe000959d44c: ldr      x8, [x16, #0x28]!
0xfffffe000959d450: mov      x0, x25
0xfffffe000959d454: movk     x16, #0x3a87, lsl #48
0xfffffe000959d458: blraa    x8, x16
0xfffffe000959d45c: b        #0xfffffe000959c2c4
0xfffffe000959d460: adrp     x9, #0xfffffe00074b8000
0xfffffe000959d464: add      x9, x9, #0x69c
0xfffffe000959d468: str      x8, [sp, #0x10]
0xfffffe000959d46c: adrp     x8, #0xfffffe00074be000
0xfffffe000959d470: add      x8, x8, #0x538
0xfffffe000959d474: stp      x9, x8, [sp]
0xfffffe000959d478: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d47c: add      x0, x0, #0xec0
0xfffffe000959d480: adrp     x1, #0xfffffe0008163000
0xfffffe000959d484: ldr      x1, [x1, #0xbf8]
0xfffffe000959d488: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d48c: add      x3, x3, #0x2d5
0xfffffe000959d490: mov      w2, #0
0xfffffe000959d494: bl       #0xfffffe000964c288
0xfffffe000959d498: b        #0xfffffe000959d620
0xfffffe000959d49c: adrp     x11, #0xfffffe00074b8000
0xfffffe000959d4a0: add      x11, x11, #0x69c
0xfffffe000959d4a4: stp      x10, x8, [sp, #0x18]
0xfffffe000959d4a8: adrp     x8, #0xfffffe00074be000
0xfffffe000959d4ac: add      x8, x8, #0x538
0xfffffe000959d4b0: stp      x8, x9, [sp, #8]
0xfffffe000959d4b4: str      x11, [sp]
0xfffffe000959d4b8: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d4bc: add      x0, x0, #0xec0
0xfffffe000959d4c0: adrp     x1, #0xfffffe0008163000
0xfffffe000959d4c4: ldr      x1, [x1, #0xbf8]
0xfffffe000959d4c8: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d4cc: add      x3, x3, #0x442
0xfffffe000959d4d0: mov      w2, #0
0xfffffe000959d4d4: bl       #0xfffffe000964c288
0xfffffe000959d4d8: ldr      x0, [x19, #0x3fb8]
0xfffffe000959d4dc: cbz      x0, #0xfffffe000959d4e8
0xfffffe000959d4e0: ldr      w1, [x23, #0x20]
0xfffffe000959d4e4: bl       #0xfffffe00095da5e0  ; _iopAddrFixup+0xb81c
0xfffffe000959d4e8: ldrb     w8, [x23, #0x30]
0xfffffe000959d4ec: cbz      w8, #0xfffffe000959d508
0xfffffe000959d4f0: cmp      w8, #1
0xfffffe000959d4f4: b.ne     #0xfffffe000959d620
0xfffffe000959d4f8: mov      x0, x19
0xfffffe000959d4fc: mov      x1, x23
0xfffffe000959d500: bl       #0xfffffe000961ad6c
0xfffffe000959d504: b        #0xfffffe000959d620
0xfffffe000959d508: bl       #0xfffffe000959da10
0xfffffe000959d50c: mov      x24, x0
0xfffffe000959d510: ldr      x16, [x19]
0xfffffe000959d514: mov      x17, x19
0xfffffe000959d518: movk     x17, #0xcda1, lsl #48
0xfffffe000959d51c: autda    x16, x17
0xfffffe000959d520: mov      x17, #0x890
0xfffffe000959d524: add      x16, x16, x17
0xfffffe000959d528: ldr      x8, [x16]
0xfffffe000959d52c: mov      x0, x19
0xfffffe000959d530: movk     x16, #0xa7ec, lsl #48
0xfffffe000959d534: blraa    x8, x16
0xfffffe000959d538: strb     w0, [x24, #0x20]
0xfffffe000959d53c: ldp      q1, q0, [x23]
0xfffffe000959d540: stur     q1, [x24, #0x28]
0xfffffe000959d544: stur     q0, [x24, #0x38]
0xfffffe000959d548: ldp      q0, q1, [x23, #0x40]
0xfffffe000959d54c: ldp      q3, q2, [x23, #0x20]
0xfffffe000959d550: stur     q3, [x24, #0x48]
0xfffffe000959d554: stur     q1, [x24, #0x78]
0xfffffe000959d558: stur     q0, [x24, #0x68]
0xfffffe000959d55c: stur     q2, [x24, #0x58]
0xfffffe000959d560: b        #0xfffffe000959d5f4
0xfffffe000959d564: adrp     x11, #0xfffffe00074b8000
0xfffffe000959d568: add      x11, x11, #0x69c
0xfffffe000959d56c: stp      x10, x8, [sp, #0x18]
0xfffffe000959d570: adrp     x8, #0xfffffe00074be000
0xfffffe000959d574: add      x8, x8, #0x538
0xfffffe000959d578: stp      x8, x9, [sp, #8]
0xfffffe000959d57c: str      x11, [sp]
0xfffffe000959d580: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d584: add      x0, x0, #0xec0
0xfffffe000959d588: adrp     x1, #0xfffffe0008163000
0xfffffe000959d58c: ldr      x1, [x1, #0xbf8]
0xfffffe000959d590: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d594: add      x3, x3, #0x3ab
0xfffffe000959d598: mov      w2, #0
0xfffffe000959d59c: bl       #0xfffffe000964c288
0xfffffe000959d5a0: ldr      x0, [x19, #0x3fb8]
0xfffffe000959d5a4: cbz      x0, #0xfffffe000959d5b0
0xfffffe000959d5a8: ldr      w1, [x23, #0x428]
0xfffffe000959d5ac: bl       #0xfffffe00095da5e0  ; _iopAddrFixup+0xb81c
0xfffffe000959d5b0: bl       #0xfffffe000959d968
0xfffffe000959d5b4: mov      x24, x0
0xfffffe000959d5b8: ldr      x16, [x19]
0xfffffe000959d5bc: mov      x17, x19
0xfffffe000959d5c0: movk     x17, #0xcda1, lsl #48
0xfffffe000959d5c4: autda    x16, x17
0xfffffe000959d5c8: mov      x17, #0x890
0xfffffe000959d5cc: add      x16, x16, x17
0xfffffe000959d5d0: ldr      x8, [x16]
0xfffffe000959d5d4: mov      x0, x19
0xfffffe000959d5d8: movk     x16, #0xa7ec, lsl #48
0xfffffe000959d5dc: blraa    x8, x16
0xfffffe000959d5e0: strb     w0, [x24, #0x20]
0xfffffe000959d5e4: add      x0, x24, #0x28
0xfffffe000959d5e8: mov      x1, x23
0xfffffe000959d5ec: mov      w2, #0x470
0xfffffe000959d5f0: bl       #0xfffffe000964c518
0xfffffe000959d5f4: ldr      x0, [x19, #0xd0]
0xfffffe000959d5f8: mov      x1, x24
0xfffffe000959d5fc: bl       #0xfffffe0009581b1c  ; __ZNSt3__110__function6__funcIZN37RtUnaryExpressionOperationDescription2
0xfffffe000959d600: ldr      x16, [x24]
0xfffffe000959d604: mov      x17, x24
0xfffffe000959d608: movk     x17, #0xcda1, lsl #48
0xfffffe000959d60c: autda    x16, x17
0xfffffe000959d610: ldr      x8, [x16, #0x28]!
0xfffffe000959d614: mov      x0, x24
0xfffffe000959d618: movk     x16, #0x3a87, lsl #48
0xfffffe000959d61c: blraa    x8, x16
0xfffffe000959d620: ldrb     w8, [x19, #0x781]
0xfffffe000959d624: tbz      w8, #0, #0xfffffe000959d678
0xfffffe000959d628: ldr      x8, [x19, #0x718]
0xfffffe000959d62c: ldr      x8, [x8, #0x38]
0xfffffe000959d630: subs     x8, x20, x8
0xfffffe000959d634: csel     x2, xzr, x8, lo
0xfffffe000959d638: ldr      x8, [x19, #0x708]
0xfffffe000959d63c: cmp      x2, x8
0xfffffe000959d640: b.ls     #0xfffffe000959d6cc
0xfffffe000959d644: ldr      w8, [x19, #0x180]
0xfffffe000959d648: cmp      w8, #3
0xfffffe000959d64c: b.hi     #0xfffffe000959d768
0xfffffe000959d650: lsl      x8, x8, #3
0xfffffe000959d654: adrp     x9, #0xfffffe0008142000
0xfffffe000959d658: add      x9, x9, #0xc98
0xfffffe000959d65c: cmp      x8, w8, sxtw
0xfffffe000959d660: add      x10, x9, w8, sxtw
0xfffffe000959d664: add      x16, x9, x8
0xfffffe000959d668: movk     x16, #0x2bad, lsl #48
0xfffffe000959d66c: csel     x10, x10, x16, eq
0xfffffe000959d670: ldr      x8, [x10]
0xfffffe000959d674: b        #0xfffffe000959d770
0xfffffe000959d678: ldrb     w1, [x25]
0xfffffe000959d67c: mov      x0, x19
0xfffffe000959d680: mov      x2, x20
0xfffffe000959d684: mov      x3, x21
0xfffffe000959d688: mov      x4, x22
0xfffffe000959d68c: mov      w5, #0
0xfffffe000959d690: bl       #0xfffffe00095f2cf8
0xfffffe000959d694: cbz      w0, #0xfffffe000959d720
0xfffffe000959d698: ldr      w8, [x19, #0x180]
0xfffffe000959d69c: cmp      w8, #3
0xfffffe000959d6a0: b.hi     #0xfffffe000959d728
0xfffffe000959d6a4: lsl      x8, x8, #3
0xfffffe000959d6a8: adrp     x9, #0xfffffe0008142000
0xfffffe000959d6ac: add      x9, x9, #0xc98
0xfffffe000959d6b0: cmp      x8, w8, sxtw
0xfffffe000959d6b4: add      x10, x9, w8, sxtw
0xfffffe000959d6b8: add      x16, x9, x8
0xfffffe000959d6bc: movk     x16, #0x2bad, lsl #48
0xfffffe000959d6c0: csel     x10, x10, x16, eq
0xfffffe000959d6c4: ldr      x8, [x10]
0xfffffe000959d6c8: b        #0xfffffe000959d730
0xfffffe000959d6cc: mov      x0, x19
0xfffffe000959d6d0: mov      w1, #5
0xfffffe000959d6d4: mov      x3, x21
0xfffffe000959d6d8: mov      x4, #0
0xfffffe000959d6dc: mov      w5, #0
0xfffffe000959d6e0: bl       #0xfffffe00095f3314
0xfffffe000959d6e4: mov      x24, x0
0xfffffe000959d6e8: cbz      w0, #0xfffffe000959c2c4
0xfffffe000959d6ec: ldr      w8, [x19, #0x180]
0xfffffe000959d6f0: cmp      w8, #3
0xfffffe000959d6f4: b.hi     #0xfffffe000959d7ac
0xfffffe000959d6f8: lsl      x8, x8, #3
0xfffffe000959d6fc: adrp     x9, #0xfffffe0008142000
0xfffffe000959d700: add      x9, x9, #0xc98
0xfffffe000959d704: cmp      x8, w8, sxtw
0xfffffe000959d708: add      x10, x9, w8, sxtw
0xfffffe000959d70c: add      x16, x9, x8
0xfffffe000959d710: movk     x16, #0x2bad, lsl #48
0xfffffe000959d714: csel     x10, x10, x16, eq
0xfffffe000959d718: ldr      x8, [x10]
0xfffffe000959d71c: b        #0xfffffe000959d7b4
0xfffffe000959d720: mov      w24, #0
0xfffffe000959d724: b        #0xfffffe000959c2c4
0xfffffe000959d728: adrp     x8, #0xfffffe00074b8000
0xfffffe000959d72c: add      x8, x8, #0x69c
0xfffffe000959d730: adrp     x9, #0xfffffe00074be000
0xfffffe000959d734: add      x9, x9, #0x538
0xfffffe000959d738: stp      x9, x0, [sp, #8]
0xfffffe000959d73c: str      x8, [sp]
0xfffffe000959d740: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d744: add      x0, x0, #0xec0
0xfffffe000959d748: adrp     x1, #0xfffffe0008163000
0xfffffe000959d74c: ldr      x1, [x1, #0xbf8]
0xfffffe000959d750: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d754: add      x3, x3, #0x654
0xfffffe000959d758: mov      w2, #0
0xfffffe000959d75c: bl       #0xfffffe000964c288
0xfffffe000959d760: mov      w24, #0
0xfffffe000959d764: b        #0xfffffe000959c2c4
0xfffffe000959d768: adrp     x8, #0xfffffe00074b8000
0xfffffe000959d76c: add      x8, x8, #0x69c
0xfffffe000959d770: adrp     x9, #0xfffffe00074be000
0xfffffe000959d774: add      x9, x9, #0x538
0xfffffe000959d778: stp      x8, x9, [sp]
0xfffffe000959d77c: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d780: add      x0, x0, #0xec0
0xfffffe000959d784: adrp     x1, #0xfffffe0008163000
0xfffffe000959d788: ldr      x1, [x1, #0xbf8]
0xfffffe000959d78c: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d790: add      x3, x3, #0x589
0xfffffe000959d794: mov      w2, #0x10
0xfffffe000959d798: bl       #0xfffffe000964c288
0xfffffe000959d79c: mov      w8, #0x2e8
0xfffffe000959d7a0: movk     w8, #0xe000, lsl #16
0xfffffe000959d7a4: sub      w24, w8, #0x26
0xfffffe000959d7a8: b        #0xfffffe000959c2c4
0xfffffe000959d7ac: adrp     x8, #0xfffffe00074b8000
0xfffffe000959d7b0: add      x8, x8, #0x69c
0xfffffe000959d7b4: adrp     x9, #0xfffffe00074be000
0xfffffe000959d7b8: add      x9, x9, #0x538
0xfffffe000959d7bc: stp      x9, x24, [sp, #8]
0xfffffe000959d7c0: str      x8, [sp]
0xfffffe000959d7c4: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d7c8: add      x0, x0, #0xec0
0xfffffe000959d7cc: adrp     x1, #0xfffffe0008163000
0xfffffe000959d7d0: ldr      x1, [x1, #0xbf8]
0xfffffe000959d7d4: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d7d8: add      x3, x3, #0x5ea
0xfffffe000959d7dc: mov      w2, #0x10
0xfffffe000959d7e0: bl       #0xfffffe000964c288
0xfffffe000959d7e4: b        #0xfffffe000959c2c4
0xfffffe000959d7e8: adrp     x8, #0xfffffe00074b8000
0xfffffe000959d7ec: add      x8, x8, #0x69c
0xfffffe000959d7f0: ldr      w9, [x23, #8]
0xfffffe000959d7f4: stp      x26, x9, [sp, #8]
0xfffffe000959d7f8: str      x8, [sp]
0xfffffe000959d7fc: adrp     x0, #0xfffffe00074b7000
0xfffffe000959d800: add      x0, x0, #0xec0
0xfffffe000959d804: adrp     x1, #0xfffffe0008163000
0xfffffe000959d808: ldr      x1, [x1, #0xbf8]
0xfffffe000959d80c: adrp     x3, #0xfffffe00074e6000
0xfffffe000959d810: add      x3, x3, #0x51c
0xfffffe000959d814: mov      w2, #0
0xfffffe000959d818: bl       #0xfffffe000964c288
0xfffffe000959d81c: ldr      x0, [x19, #0x858]
0xfffffe000959d820: ldr      x16, [x0]
0xfffffe000959d824: mov      x17, x0
0xfffffe000959d828: movk     x17, #0xcda1, lsl #48
0xfffffe000959d82c: autda    x16, x17
0xfffffe000959d830: mov      x17, #0x1f8
0xfffffe000959d834: add      x16, x16, x17
0xfffffe000959d838: ldr      x8, [x16]
0xfffffe000959d83c: mov      x1, #0
0xfffffe000959d840: mov      x2, #0
0xfffffe000959d844: mov      w3, #0
0xfffffe000959d848: movk     x16, #0xa28c, lsl #48
0xfffffe000959d84c: blraa    x8, x16
0xfffffe000959d850: b        #0xfffffe000959d620
0xfffffe000959d854: mov      x0, x19
0xfffffe000959d858: bl       #0xfffffe000964a980