; HandleRTBuddyMessage_real [0xfffffe00095feff0-0xfffffe00095ff634) 0x644 bytes
0xfffffe00095feff0: bti      c
0xfffffe00095feff4: pacibsp  
0xfffffe00095feff8: sub      sp, sp, #0xd0
0xfffffe00095feffc: stp      x28, x27, [sp, #0x70]
0xfffffe00095ff000: stp      x26, x25, [sp, #0x80]
0xfffffe00095ff004: stp      x24, x23, [sp, #0x90]
0xfffffe00095ff008: stp      x22, x21, [sp, #0xa0]
0xfffffe00095ff00c: stp      x20, x19, [sp, #0xb0]
0xfffffe00095ff010: stp      x29, x30, [sp, #0xc0]
0xfffffe00095ff014: add      x29, sp, #0xc0
0xfffffe00095ff018: mov      x19, x1
0xfffffe00095ff01c: mov      x20, x0
0xfffffe00095ff020: adrp     x21, #0xfffffe00074c4000
0xfffffe00095ff024: add      x21, x21, #0x870
0xfffffe00095ff028: ldr      x8, [x2]
0xfffffe00095ff02c: str      x8, [sp, #0x60]
0xfffffe00095ff030: cmp      x1, #1
0xfffffe00095ff034: b.lt     #0xfffffe00095ff548
0xfffffe00095ff038: cmp      x19, #7
0xfffffe00095ff03c: b.ge     #0xfffffe00095ff548
0xfffffe00095ff040: add      x8, x20, #0x5c0
0xfffffe00095ff044: add      x25, x8, x19, lsl #6
0xfffffe00095ff048: eor      x16, x8, x25
0xfffffe00095ff04c: tst      x16, #-0x40000000000000
0xfffffe00095ff050: b.eq     #0xfffffe00095ff058
0xfffffe00095ff054: movk     x25, #0xc8a2, lsl #48
0xfffffe00095ff058: ldr      x8, [x25, #0x28]
0xfffffe00095ff05c: cbz      x8, #0xfffffe00095ff5b0
0xfffffe00095ff060: bl       #0xfffffe000964c488
0xfffffe00095ff064: str      wzr, [sp, #0x54]
0xfffffe00095ff068: mov      w8, #0x3a85
0xfffffe00095ff06c: add      x8, x20, x8
0xfffffe00095ff070: stp      x8, x0, [sp, #0x40]
0xfffffe00095ff074: mov      w8, w19
0xfffffe00095ff078: lsl      x8, x8, #2
0xfffffe00095ff07c: add      x8, x8, w19, uxtw
0xfffffe00095ff080: adrp     x9, #0xfffffe000814e000
0xfffffe00095ff084: add      x9, x9, #0x520
0xfffffe00095ff088: add      x10, x9, x8, lsl #3
0xfffffe00095ff08c: eor      x16, x9, x10
0xfffffe00095ff090: tst      x16, #-0x40000000000000
0xfffffe00095ff094: b.eq     #0xfffffe00095ff09c
0xfffffe00095ff098: movk     x10, #0xc8a2, lsl #48
0xfffffe00095ff09c: str      x10, [sp, #0x58]
0xfffffe00095ff0a0: adrp     x28, #0xfffffe00074b8000
0xfffffe00095ff0a4: add      x28, x28, #0x69c
0xfffffe00095ff0a8: adrp     x22, #0xfffffe00074b7000
0xfffffe00095ff0ac: add      x22, x22, #0xec0
0xfffffe00095ff0b0: adrp     x23, #0xfffffe0008163000
0xfffffe00095ff0b4: ldr      x23, [x23, #0xbf8]
0xfffffe00095ff0b8: adrp     x24, #0xfffffe00074f6000
0xfffffe00095ff0bc: add      x24, x24, #0xe17
0xfffffe00095ff0c0: ldr      x8, [x25, #0x18]
0xfffffe00095ff0c4: cbz      x8, #0xfffffe00095ff1c4
0xfffffe00095ff0c8: ldr      x9, [x8, #0x30]
0xfffffe00095ff0cc: cbz      x9, #0xfffffe00095ff1c4
0xfffffe00095ff0d0: ldr      x9, [sp, #0x60]
0xfffffe00095ff0d4: sbfx     x10, x9, #0, #0x2c
0xfffffe00095ff0d8: ubfx     x11, x9, #0x2c, #8
0xfffffe00095ff0dc: ubfx     x12, x9, #0x34, #2
0xfffffe00095ff0e0: lsl      x13, x11, #0x14
0xfffffe00095ff0e4: lsl      x14, x11, #0x15
0xfffffe00095ff0e8: cmp      x12, #2
0xfffffe00095ff0ec: csel     x13, x13, x14, eq
0xfffffe00095ff0f0: lsl      x11, x11, #0xc
0xfffffe00095ff0f4: cmp      x12, #0
0xfffffe00095ff0f8: csel     x11, x12, x11, eq
0xfffffe00095ff0fc: cmp      x12, #1
0xfffffe00095ff100: csel     x12, x13, x11, gt
0xfffffe00095ff104: ldr      x13, [x8, #0x18]
0xfffffe00095ff108: ldr      x11, [x25, #8]
0xfffffe00095ff10c: cmp      x10, x13
0xfffffe00095ff110: ccmp     x12, x11, #0, eq
0xfffffe00095ff114: b.eq     #0xfffffe00095ff218
0xfffffe00095ff118: and      x26, x9, #0xffffff
0xfffffe00095ff11c: ubfx     x27, x9, #0x18, #0x18
0xfffffe00095ff120: cmp      x26, x11
0xfffffe00095ff124: b.hi     #0xfffffe00095ff280
0xfffffe00095ff128: add      x9, x27, x26
0xfffffe00095ff12c: cmp      x9, x11
0xfffffe00095ff130: b.hi     #0xfffffe00095ff280
0xfffffe00095ff134: cmp      x19, #3
0xfffffe00095ff138: b.gt     #0xfffffe00095ff2f0
0xfffffe00095ff13c: sub      x9, x19, #2
0xfffffe00095ff140: cmp      x9, #2
0xfffffe00095ff144: b.hs     #0xfffffe00095ff3f0
0xfffffe00095ff148: ldr      x8, [x8, #0x38]
0xfffffe00095ff14c: add      x26, x8, x26
0xfffffe00095ff150: mov      x0, x20
0xfffffe00095ff154: mov      x1, x26
0xfffffe00095ff158: mov      x2, x27
0xfffffe00095ff15c: mov      x3, #0
0xfffffe00095ff160: bl       #0xfffffe00095ee0d4
0xfffffe00095ff164: cbz      w0, #0xfffffe00095ff2d8
0xfffffe00095ff168: ldr      w9, [x20, #0x180]
0xfffffe00095ff16c: mov      x8, x28
0xfffffe00095ff170: cmp      w9, #3
0xfffffe00095ff174: b.hi     #0xfffffe00095ff19c
0xfffffe00095ff178: lsl      x8, x9, #3
0xfffffe00095ff17c: adrp     x10, #0xfffffe000814e000
0xfffffe00095ff180: add      x10, x10, #0xed0
0xfffffe00095ff184: cmp      x8, w8, sxtw
0xfffffe00095ff188: add      x9, x10, w8, sxtw
0xfffffe00095ff18c: add      x16, x10, x8
0xfffffe00095ff190: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff194: csel     x9, x9, x16, eq
0xfffffe00095ff198: ldr      x8, [x9]
0xfffffe00095ff19c: stp      x27, x0, [sp, #0x20]
0xfffffe00095ff1a0: stp      x19, x26, [sp, #0x10]
0xfffffe00095ff1a4: stp      x8, x21, [sp]
0xfffffe00095ff1a8: mov      x0, x22
0xfffffe00095ff1ac: mov      x1, x23
0xfffffe00095ff1b0: mov      w2, #0x10
0xfffffe00095ff1b4: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ff1b8: add      x3, x3, #0xfab
0xfffffe00095ff1bc: bl       #0xfffffe000964c288
0xfffffe00095ff1c0: b        #0xfffffe00095ff2d8
0xfffffe00095ff1c4: ldr      w9, [x20, #0x180]
0xfffffe00095ff1c8: mov      x8, x28
0xfffffe00095ff1cc: cmp      w9, #3
0xfffffe00095ff1d0: b.hi     #0xfffffe00095ff1f8
0xfffffe00095ff1d4: lsl      x8, x9, #3
0xfffffe00095ff1d8: adrp     x10, #0xfffffe000814e000
0xfffffe00095ff1dc: add      x10, x10, #0xed0
0xfffffe00095ff1e0: cmp      x8, w8, sxtw
0xfffffe00095ff1e4: add      x9, x10, w8, sxtw
0xfffffe00095ff1e8: add      x16, x10, x8
0xfffffe00095ff1ec: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff1f0: csel     x9, x9, x16, eq
0xfffffe00095ff1f4: ldr      x8, [x9]
0xfffffe00095ff1f8: stp      x21, x19, [sp, #8]
0xfffffe00095ff1fc: str      x8, [sp]
0xfffffe00095ff200: mov      x0, x22
0xfffffe00095ff204: mov      x1, x23
0xfffffe00095ff208: mov      w2, #0x10
0xfffffe00095ff20c: mov      x3, x24
0xfffffe00095ff210: bl       #0xfffffe000964c288
0xfffffe00095ff214: b        #0xfffffe00095ff2d8
0xfffffe00095ff218: ldr      w9, [x20, #0x180]
0xfffffe00095ff21c: mov      x8, x28
0xfffffe00095ff220: cmp      w9, #3
0xfffffe00095ff224: b.hi     #0xfffffe00095ff24c
0xfffffe00095ff228: lsl      x8, x9, #3
0xfffffe00095ff22c: adrp     x10, #0xfffffe000814e000
0xfffffe00095ff230: add      x10, x10, #0xed0
0xfffffe00095ff234: cmp      x8, w8, sxtw
0xfffffe00095ff238: add      x9, x10, w8, sxtw
0xfffffe00095ff23c: add      x16, x10, x8
0xfffffe00095ff240: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff244: csel     x9, x9, x16, eq
0xfffffe00095ff248: ldr      x8, [x9]
0xfffffe00095ff24c: ldr      x9, [sp, #0x58]
0xfffffe00095ff250: ldur     x9, [x9, #0x18]
0xfffffe00095ff254: stp      x19, x9, [sp, #0x10]
0xfffffe00095ff258: stp      x8, x21, [sp]
0xfffffe00095ff25c: mov      x0, x22
0xfffffe00095ff260: mov      x1, x23
0xfffffe00095ff264: mov      w2, #0
0xfffffe00095ff268: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ff26c: add      x3, x3, #0xe65
0xfffffe00095ff270: bl       #0xfffffe000964c288
0xfffffe00095ff274: mov      w8, #1
0xfffffe00095ff278: strb     w8, [x25, #0x38]
0xfffffe00095ff27c: b        #0xfffffe00095ff2d8
0xfffffe00095ff280: ldr      w9, [x20, #0x180]
0xfffffe00095ff284: mov      x8, x28
0xfffffe00095ff288: cmp      w9, #3
0xfffffe00095ff28c: b.hi     #0xfffffe00095ff2b4
0xfffffe00095ff290: lsl      x8, x9, #3
0xfffffe00095ff294: adrp     x10, #0xfffffe000814e000
0xfffffe00095ff298: add      x10, x10, #0xed0
0xfffffe00095ff29c: cmp      x8, w8, sxtw
0xfffffe00095ff2a0: add      x9, x10, w8, sxtw
0xfffffe00095ff2a4: add      x16, x10, x8
0xfffffe00095ff2a8: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff2ac: csel     x9, x9, x16, eq
0xfffffe00095ff2b0: ldr      x8, [x9]
0xfffffe00095ff2b4: stp      x27, x19, [sp, #0x18]
0xfffffe00095ff2b8: stp      x21, x26, [sp, #8]
0xfffffe00095ff2bc: str      x8, [sp]
0xfffffe00095ff2c0: mov      x0, x22
0xfffffe00095ff2c4: mov      x1, x23
0xfffffe00095ff2c8: mov      w2, #0x10
0xfffffe00095ff2cc: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ff2d0: add      x3, x3, #0xe9a
0xfffffe00095ff2d4: bl       #0xfffffe000964c288
0xfffffe00095ff2d8: ldr      x0, [x25, #0x28]
0xfffffe00095ff2dc: add      x1, sp, #0x60
0xfffffe00095ff2e0: mov      w2, #0
0xfffffe00095ff2e4: bl       #0xfffffe000964bc78
0xfffffe00095ff2e8: cbz      w0, #0xfffffe00095ff0c0
0xfffffe00095ff2ec: b        #0xfffffe00095ff614
0xfffffe00095ff2f0: cmp      x19, #4
0xfffffe00095ff2f4: b.eq     #0xfffffe00095ff470
0xfffffe00095ff2f8: cmp      x19, #5
0xfffffe00095ff2fc: b.ne     #0xfffffe00095ff4e4
0xfffffe00095ff300: ldr      x11, [x8, #0x38]
0xfffffe00095ff304: adrp     x8, #0xfffffe000cb6d000
0xfffffe00095ff308: add      x8, x8, #0xc60
0xfffffe00095ff30c: ldrb     w8, [x8, #1]
0xfffffe00095ff310: tbz      w8, #2, #0xfffffe00095ff374
0xfffffe00095ff314: ldr      w9, [x20, #0x180]
0xfffffe00095ff318: mov      x8, x28
0xfffffe00095ff31c: cmp      w9, #3
0xfffffe00095ff320: b.hi     #0xfffffe00095ff348
0xfffffe00095ff324: lsl      x8, x9, #3
0xfffffe00095ff328: adrp     x10, #0xfffffe000814e000
0xfffffe00095ff32c: add      x10, x10, #0xed0
0xfffffe00095ff330: cmp      x8, w8, sxtw
0xfffffe00095ff334: add      x9, x10, w8, sxtw
0xfffffe00095ff338: add      x16, x10, x8
0xfffffe00095ff33c: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff340: csel     x9, x9, x16, eq
0xfffffe00095ff344: ldr      x8, [x9]
0xfffffe00095ff348: stp      x26, x27, [sp, #0x18]
0xfffffe00095ff34c: stp      x21, x11, [sp, #8]
0xfffffe00095ff350: str      x8, [sp]
0xfffffe00095ff354: mov      x0, x22
0xfffffe00095ff358: mov      x1, x23
0xfffffe00095ff35c: mov      w2, #0
0xfffffe00095ff360: adrp     x3, #0xfffffe00074f7000
0xfffffe00095ff364: add      x3, x3, #0x1f
0xfffffe00095ff368: str      x11, [sp, #0x38]
0xfffffe00095ff36c: bl       #0xfffffe000964c288
0xfffffe00095ff370: ldr      x11, [sp, #0x38]
0xfffffe00095ff374: add      x26, x11, x26
0xfffffe00095ff378: mov      x0, x20
0xfffffe00095ff37c: mov      x1, x26
0xfffffe00095ff380: mov      x2, x27
0xfffffe00095ff384: mov      x3, #0
0xfffffe00095ff388: bl       #0xfffffe000959c194
0xfffffe00095ff38c: cbz      w0, #0xfffffe00095ff2d8
0xfffffe00095ff390: ldr      w9, [x20, #0x180]
0xfffffe00095ff394: mov      x8, x28
0xfffffe00095ff398: cmp      w9, #3
0xfffffe00095ff39c: b.hi     #0xfffffe00095ff3c4
0xfffffe00095ff3a0: lsl      x8, x9, #3
0xfffffe00095ff3a4: adrp     x10, #0xfffffe000814e000
0xfffffe00095ff3a8: add      x10, x10, #0xed0
0xfffffe00095ff3ac: cmp      x8, w8, sxtw
0xfffffe00095ff3b0: add      x9, x10, w8, sxtw
0xfffffe00095ff3b4: add      x16, x10, x8
0xfffffe00095ff3b8: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff3bc: csel     x9, x9, x16, eq
0xfffffe00095ff3c0: ldr      x8, [x9]
0xfffffe00095ff3c4: stp      x27, x0, [sp, #0x20]
0xfffffe00095ff3c8: mov      w9, #5
0xfffffe00095ff3cc: stp      x9, x26, [sp, #0x10]
0xfffffe00095ff3d0: stp      x8, x21, [sp]
0xfffffe00095ff3d4: mov      x0, x22
0xfffffe00095ff3d8: mov      x1, x23
0xfffffe00095ff3dc: mov      w2, #0x10
0xfffffe00095ff3e0: adrp     x3, #0xfffffe00074f7000
0xfffffe00095ff3e4: add      x3, x3, #0x77
0xfffffe00095ff3e8: bl       #0xfffffe000964c288
0xfffffe00095ff3ec: b        #0xfffffe00095ff2d8
0xfffffe00095ff3f0: ldr      x8, [x8, #0x38]
0xfffffe00095ff3f4: add      x8, x8, x26
0xfffffe00095ff3f8: ldr      w8, [x8]
0xfffffe00095ff3fc: and      w8, w8, #1
0xfffffe00095ff400: ldr      x9, [sp, #0x40]
0xfffffe00095ff404: strb     w8, [x9]
0xfffffe00095ff408: ldr      w10, [x20, #0x180]
0xfffffe00095ff40c: mov      x9, x28
0xfffffe00095ff410: cmp      w10, #3
0xfffffe00095ff414: b.hi     #0xfffffe00095ff43c
0xfffffe00095ff418: lsl      x9, x10, #3
0xfffffe00095ff41c: adrp     x11, #0xfffffe000814e000
0xfffffe00095ff420: add      x11, x11, #0xed0
0xfffffe00095ff424: cmp      x9, w9, sxtw
0xfffffe00095ff428: add      x10, x11, w9, sxtw
0xfffffe00095ff42c: add      x16, x11, x9
0xfffffe00095ff430: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff434: csel     x10, x10, x16, eq
0xfffffe00095ff438: ldr      x9, [x10]
0xfffffe00095ff43c: ldr      x10, [sp, #0x58]
0xfffffe00095ff440: ldur     x11, [x10, #0x18]
0xfffffe00095ff444: mov      w10, #1
0xfffffe00095ff448: stp      x10, x11, [sp, #0x10]
0xfffffe00095ff44c: stp      x9, x21, [sp]
0xfffffe00095ff450: str      x8, [sp, #0x20]
0xfffffe00095ff454: mov      x0, x22
0xfffffe00095ff458: mov      x1, x23
0xfffffe00095ff45c: mov      w2, #0
0xfffffe00095ff460: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ff464: add      x3, x3, #0xef7
0xfffffe00095ff468: bl       #0xfffffe000964c288
0xfffffe00095ff46c: b        #0xfffffe00095ff2d8
0xfffffe00095ff470: mov      x0, x20
0xfffffe00095ff474: mov      x1, x26
0xfffffe00095ff478: mov      x2, x27
0xfffffe00095ff47c: bl       #0xfffffe00095f9400
0xfffffe00095ff480: cbz      w0, #0xfffffe00095ff2d8
0xfffffe00095ff484: ldr      w9, [x20, #0x180]
0xfffffe00095ff488: mov      x8, x28
0xfffffe00095ff48c: cmp      w9, #3
0xfffffe00095ff490: b.hi     #0xfffffe00095ff4b8
0xfffffe00095ff494: lsl      x8, x9, #3
0xfffffe00095ff498: adrp     x10, #0xfffffe000814e000
0xfffffe00095ff49c: add      x10, x10, #0xed0
0xfffffe00095ff4a0: cmp      x8, w8, sxtw
0xfffffe00095ff4a4: add      x9, x10, w8, sxtw
0xfffffe00095ff4a8: add      x16, x10, x8
0xfffffe00095ff4ac: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff4b0: csel     x9, x9, x16, eq
0xfffffe00095ff4b4: ldr      x8, [x9]
0xfffffe00095ff4b8: stp      x27, x0, [sp, #0x20]
0xfffffe00095ff4bc: mov      w9, #4
0xfffffe00095ff4c0: stp      x9, x26, [sp, #0x10]
0xfffffe00095ff4c4: stp      x8, x21, [sp]
0xfffffe00095ff4c8: mov      x0, x22
0xfffffe00095ff4cc: mov      x1, x23
0xfffffe00095ff4d0: mov      w2, #0x10
0xfffffe00095ff4d4: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ff4d8: add      x3, x3, #0xf38
0xfffffe00095ff4dc: bl       #0xfffffe000964c288
0xfffffe00095ff4e0: b        #0xfffffe00095ff2d8
0xfffffe00095ff4e4: ldr      x8, [x8, #0x38]
0xfffffe00095ff4e8: str      x8, [sp, #0x38]
0xfffffe00095ff4ec: bl       #0xfffffe000964c488
0xfffffe00095ff4f0: ldr      x8, [sp, #0x48]
0xfffffe00095ff4f4: sub      x0, x0, x8
0xfffffe00095ff4f8: stur     xzr, [x29, #-0x58]
0xfffffe00095ff4fc: sub      x1, x29, #0x58
0xfffffe00095ff500: bl       #0xfffffe000964c298
0xfffffe00095ff504: ldur     x8, [x29, #-0x58]
0xfffffe00095ff508: mov      w9, #0xf080
0xfffffe00095ff50c: movk     w9, #0x2fa, lsl #16
0xfffffe00095ff510: cmp      x8, x9
0xfffffe00095ff514: b.lo     #0xfffffe00095ff520
0xfffffe00095ff518: ldr      w8, [sp, #0x54]
0xfffffe00095ff51c: cbnz     w8, #0xfffffe00095ff2d8
0xfffffe00095ff520: ldr      w8, [sp, #0x54]
0xfffffe00095ff524: add      w8, w8, #1
0xfffffe00095ff528: str      w8, [sp, #0x54]
0xfffffe00095ff52c: ldr      x8, [sp, #0x38]
0xfffffe00095ff530: add      x1, x8, x26
0xfffffe00095ff534: mov      x0, x20
0xfffffe00095ff538: mov      x2, x27
0xfffffe00095ff53c: mov      x3, #0
0xfffffe00095ff540: bl       #0xfffffe00095e26a0
0xfffffe00095ff544: b        #0xfffffe00095ff2d8
0xfffffe00095ff548: ldr      w8, [x20, #0x180]
0xfffffe00095ff54c: cmp      w8, #3
0xfffffe00095ff550: b.hi     #0xfffffe00095ff57c
0xfffffe00095ff554: lsl      x8, x8, #3
0xfffffe00095ff558: adrp     x9, #0xfffffe000814e000
0xfffffe00095ff55c: add      x9, x9, #0xed0
0xfffffe00095ff560: cmp      x8, w8, sxtw
0xfffffe00095ff564: add      x10, x9, w8, sxtw
0xfffffe00095ff568: add      x16, x9, x8
0xfffffe00095ff56c: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff570: csel     x10, x10, x16, eq
0xfffffe00095ff574: ldr      x8, [x10]
0xfffffe00095ff578: b        #0xfffffe00095ff584
0xfffffe00095ff57c: adrp     x8, #0xfffffe00074b8000
0xfffffe00095ff580: add      x8, x8, #0x69c
0xfffffe00095ff584: stp      x21, x19, [sp, #8]
0xfffffe00095ff588: str      x8, [sp]
0xfffffe00095ff58c: adrp     x0, #0xfffffe00074b7000
0xfffffe00095ff590: add      x0, x0, #0xec0
0xfffffe00095ff594: adrp     x1, #0xfffffe0008163000
0xfffffe00095ff598: ldr      x1, [x1, #0xbf8]
0xfffffe00095ff59c: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ff5a0: add      x3, x3, #0xdb2
0xfffffe00095ff5a4: mov      w2, #0x10
0xfffffe00095ff5a8: bl       #0xfffffe000964c288
0xfffffe00095ff5ac: b        #0xfffffe00095ff614
0xfffffe00095ff5b0: ldr      w8, [x20, #0x180]
0xfffffe00095ff5b4: cmp      w8, #3
0xfffffe00095ff5b8: b.hi     #0xfffffe00095ff5e4
0xfffffe00095ff5bc: lsl      x8, x8, #3
0xfffffe00095ff5c0: adrp     x9, #0xfffffe000814e000
0xfffffe00095ff5c4: add      x9, x9, #0xed0
0xfffffe00095ff5c8: cmp      x8, w8, sxtw
0xfffffe00095ff5cc: add      x10, x9, w8, sxtw
0xfffffe00095ff5d0: add      x16, x9, x8
0xfffffe00095ff5d4: movk     x16, #0x2bad, lsl #48
0xfffffe00095ff5d8: csel     x10, x10, x16, eq
0xfffffe00095ff5dc: ldr      x8, [x10]
0xfffffe00095ff5e0: b        #0xfffffe00095ff5ec
0xfffffe00095ff5e4: adrp     x8, #0xfffffe00074b8000
0xfffffe00095ff5e8: add      x8, x8, #0x69c
0xfffffe00095ff5ec: stp      x21, x19, [sp, #8]
0xfffffe00095ff5f0: str      x8, [sp]
0xfffffe00095ff5f4: adrp     x0, #0xfffffe00074b7000
0xfffffe00095ff5f8: add      x0, x0, #0xec0
0xfffffe00095ff5fc: adrp     x1, #0xfffffe0008163000
0xfffffe00095ff600: ldr      x1, [x1, #0xbf8]
0xfffffe00095ff604: adrp     x3, #0xfffffe00074f6000
0xfffffe00095ff608: add      x3, x3, #0xddf
0xfffffe00095ff60c: mov      w2, #0x10
0xfffffe00095ff610: bl       #0xfffffe000964c288
0xfffffe00095ff614: ldp      x29, x30, [sp, #0xc0]
0xfffffe00095ff618: ldp      x20, x19, [sp, #0xb0]
0xfffffe00095ff61c: ldp      x22, x21, [sp, #0xa0]
0xfffffe00095ff620: ldp      x24, x23, [sp, #0x90]
0xfffffe00095ff624: ldp      x26, x25, [sp, #0x80]
0xfffffe00095ff628: ldp      x28, x27, [sp, #0x70]
0xfffffe00095ff62c: add      sp, sp, #0xd0
0xfffffe00095ff630: retab    