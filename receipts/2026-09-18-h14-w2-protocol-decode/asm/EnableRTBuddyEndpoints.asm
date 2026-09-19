; EnableRTBuddyEndpoints [0xfffffe00095feb30-0xfffffe00095feff0) 0x4c0 bytes
0xfffffe00095feb30: bti      c
0xfffffe00095feb34: pacibsp  
0xfffffe00095feb38: sub      sp, sp, #0xb0
0xfffffe00095feb3c: stp      x24, x23, [sp, #0x70]
0xfffffe00095feb40: stp      x22, x21, [sp, #0x80]
0xfffffe00095feb44: stp      x20, x19, [sp, #0x90]
0xfffffe00095feb48: stp      x29, x30, [sp, #0xa0]
0xfffffe00095feb4c: add      x29, sp, #0xa0
0xfffffe00095feb50: adrp     x8, #0xfffffe0008163000
0xfffffe00095feb54: ldr      x8, [x8, #0xbf0]
0xfffffe00095feb58: ldr      x8, [x8]
0xfffffe00095feb5c: stur     x8, [x29, #-0x38]
0xfffffe00095feb60: cbz      x1, #0xfffffe00095febac
0xfffffe00095feb64: mov      x20, x2
0xfffffe00095feb68: mov      x21, x0
0xfffffe00095feb6c: sub      w8, w2, #8
0xfffffe00095feb70: cmn      w8, #8
0xfffffe00095feb74: b.hi     #0xfffffe00095febb4
0xfffffe00095feb78: ldr      w8, [x21, #0x180]
0xfffffe00095feb7c: cmp      w8, #3
0xfffffe00095feb80: b.hi     #0xfffffe00095fec24
0xfffffe00095feb84: lsl      x8, x8, #3
0xfffffe00095feb88: adrp     x9, #0xfffffe000814e000
0xfffffe00095feb8c: add      x9, x9, #0xed0
0xfffffe00095feb90: cmp      x8, w8, sxtw
0xfffffe00095feb94: add      x10, x9, w8, sxtw
0xfffffe00095feb98: add      x16, x9, x8
0xfffffe00095feb9c: movk     x16, #0x2bad, lsl #48
0xfffffe00095feba0: csel     x10, x10, x16, eq
0xfffffe00095feba4: ldr      x8, [x10]
0xfffffe00095feba8: b        #0xfffffe00095fec2c
0xfffffe00095febac: mov      w20, #0
0xfffffe00095febb0: b        #0xfffffe00095fefb8
0xfffffe00095febb4: mov      x22, x1
0xfffffe00095febb8: movi     v0.2d, #0000000000000000
0xfffffe00095febbc: stp      q0, q0, [sp, #0x40]
0xfffffe00095febc0: stp      q0, q0, [sp, #0x20]
0xfffffe00095febc4: mov      x8, x20
0xfffffe00095febc8: stp      x1, x8, [sp]
0xfffffe00095febcc: adrp     x2, #0xfffffe00074c4000
0xfffffe00095febd0: add      x2, x2, #0x81f
0xfffffe00095febd4: add      x0, sp, #0x20
0xfffffe00095febd8: mov      w1, #0x40
0xfffffe00095febdc: bl       #0xfffffe000964c638
0xfffffe00095febe0: adrp     x8, #0xfffffe000cb6d000
0xfffffe00095febe4: add      x8, x8, #0xc60
0xfffffe00095febe8: ldrb     w8, [x8, #1]
0xfffffe00095febec: tbz      w8, #2, #0xfffffe00095feca0
0xfffffe00095febf0: ldr      w8, [x21, #0x180]
0xfffffe00095febf4: cmp      w8, #3
0xfffffe00095febf8: b.hi     #0xfffffe00095fec64
0xfffffe00095febfc: lsl      x8, x8, #3
0xfffffe00095fec00: adrp     x9, #0xfffffe000814e000
0xfffffe00095fec04: add      x9, x9, #0xed0
0xfffffe00095fec08: cmp      x8, w8, sxtw
0xfffffe00095fec0c: add      x10, x9, w8, sxtw
0xfffffe00095fec10: add      x16, x9, x8
0xfffffe00095fec14: movk     x16, #0x2bad, lsl #48
0xfffffe00095fec18: csel     x10, x10, x16, eq
0xfffffe00095fec1c: ldr      x8, [x10]
0xfffffe00095fec20: b        #0xfffffe00095fec6c
0xfffffe00095fec24: adrp     x8, #0xfffffe00074b8000
0xfffffe00095fec28: add      x8, x8, #0x69c
0xfffffe00095fec2c: adrp     x9, #0xfffffe00074c4000
0xfffffe00095fec30: add      x9, x9, #0x808
0xfffffe00095fec34: stp      x9, x20, [sp, #8]
0xfffffe00095fec38: str      x8, [sp]
0xfffffe00095fec3c: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fec40: add      x0, x0, #0xec0
0xfffffe00095fec44: adrp     x1, #0xfffffe0008163000
0xfffffe00095fec48: ldr      x1, [x1, #0xbf8]
0xfffffe00095fec4c: adrp     x3, #0xfffffe00074f6000
0xfffffe00095fec50: add      x3, x3, #0xb60
0xfffffe00095fec54: mov      w2, #0x10
0xfffffe00095fec58: bl       #0xfffffe000964c288
0xfffffe00095fec5c: mov      w20, #0
0xfffffe00095fec60: b        #0xfffffe00095fefb8
0xfffffe00095fec64: adrp     x8, #0xfffffe00074b8000
0xfffffe00095fec68: add      x8, x8, #0x69c
0xfffffe00095fec6c: add      x9, sp, #0x20
0xfffffe00095fec70: str      x9, [sp, #0x10]
0xfffffe00095fec74: adrp     x9, #0xfffffe00074c4000
0xfffffe00095fec78: add      x9, x9, #0x808
0xfffffe00095fec7c: stp      x8, x9, [sp]
0xfffffe00095fec80: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fec84: add      x0, x0, #0xec0
0xfffffe00095fec88: adrp     x1, #0xfffffe0008163000
0xfffffe00095fec8c: ldr      x1, [x1, #0xbf8]
0xfffffe00095fec90: adrp     x3, #0xfffffe00074f6000
0xfffffe00095fec94: add      x3, x3, #0xb93
0xfffffe00095fec98: mov      w2, #0
0xfffffe00095fec9c: bl       #0xfffffe000964c288
0xfffffe00095feca0: add      x0, sp, #0x20
0xfffffe00095feca4: mov      x1, #0
0xfffffe00095feca8: bl       #0xfffffe000964bfd8
0xfffffe00095fecac: cbz      x0, #0xfffffe00095fedd8
0xfffffe00095fecb0: mov      x19, x0
0xfffffe00095fecb4: mov      x1, #0xe400
0xfffffe00095fecb8: movk     x1, #0x540b, lsl #16
0xfffffe00095fecbc: movk     x1, #2, lsl #32
0xfffffe00095fecc0: bl       #0xfffffe000964c038
0xfffffe00095fecc4: cbz      x0, #0xfffffe00095fee0c
0xfffffe00095fecc8: mov      x23, x0
0xfffffe00095feccc: ldr      x22, [x0, #0x88]
0xfffffe00095fecd0: cbz      x22, #0xfffffe00095fee7c
0xfffffe00095fecd4: mov      w24, w20
0xfffffe00095fecd8: adrp     x16, #0xfffffe00095fe000
0xfffffe00095fecdc: add      x16, x16, #0xff0
0xfffffe00095fece0: mov      x17, #0x1810
0xfffffe00095fece4: pacia    x16, x17
0xfffffe00095fece8: mov      x2, x16
0xfffffe00095fecec: mov      x0, x22
0xfffffe00095fecf0: mov      x1, x21
0xfffffe00095fecf4: mov      x3, x24
0xfffffe00095fecf8: bl       #0xfffffe000964bc68
0xfffffe00095fecfc: cbz      w0, #0xfffffe00095feeb0
0xfffffe00095fed00: ldr      x16, [x21]
0xfffffe00095fed04: mov      x17, x21
0xfffffe00095fed08: movk     x17, #0xcda1, lsl #48
0xfffffe00095fed0c: autda    x16, x17
0xfffffe00095fed10: mov      x17, #0x6b8
0xfffffe00095fed14: add      x16, x16, x17
0xfffffe00095fed18: ldr      x8, [x16]
0xfffffe00095fed1c: mov      x0, x21
0xfffffe00095fed20: movk     x16, #0x638e, lsl #48
0xfffffe00095fed24: blraa    x8, x16
0xfffffe00095fed28: ldr      x16, [x0]
0xfffffe00095fed2c: mov      x17, x0
0xfffffe00095fed30: movk     x17, #0xcda1, lsl #48
0xfffffe00095fed34: autda    x16, x17
0xfffffe00095fed38: mov      x17, #0x160
0xfffffe00095fed3c: add      x16, x16, x17
0xfffffe00095fed40: ldr      x8, [x16]
0xfffffe00095fed44: mov      x1, x22
0xfffffe00095fed48: movk     x16, #0x11e8, lsl #48
0xfffffe00095fed4c: blraa    x8, x16
0xfffffe00095fed50: adrp     x16, #0xfffffe00095ff000
0xfffffe00095fed54: add      x16, x16, #0x634
0xfffffe00095fed58: mov      x17, #0xd507
0xfffffe00095fed5c: pacia    x16, x17
0xfffffe00095fed60: mov      x17, x22
0xfffffe00095fed64: str      x16, [x22, #0xd0]
0xfffffe00095fed68: ldr      x16, [x22]
0xfffffe00095fed6c: movk     x17, #0xcda1, lsl #48
0xfffffe00095fed70: autda    x16, x17
0xfffffe00095fed74: mov      x17, x16
0xfffffe00095fed78: xpacd    x17
0xfffffe00095fed7c: cmp      x16, x17
0xfffffe00095fed80: b.eq     #0xfffffe00095fed88
0xfffffe00095fed84: brk      #0xc472
0xfffffe00095fed88: add      x8, x16, #0x170
0xfffffe00095fed8c: ldr      x9, [x16, #0x170]
0xfffffe00095fed90: mov      x0, x22
0xfffffe00095fed94: mov      x17, x8
0xfffffe00095fed98: movk     x17, #0x9b16, lsl #48
0xfffffe00095fed9c: blraa    x9, x17
0xfffffe00095feda0: add      x8, x21, #0x5c0
0xfffffe00095feda4: add      x9, x8, x24, lsl #6
0xfffffe00095feda8: stp      x22, x23, [x9, #0x28]
0xfffffe00095fedac: str      w20, [x9]
0xfffffe00095fedb0: add      x8, x24, x24, lsl #2
0xfffffe00095fedb4: adrp     x10, #0xfffffe000814e000
0xfffffe00095fedb8: add      x10, x10, #0x520
0xfffffe00095fedbc: add      x11, x10, x8, lsl #3
0xfffffe00095fedc0: ldr      x8, [x11, #8]
0xfffffe00095fedc4: str      wzr, [x9, #0x20]
0xfffffe00095fedc8: ldr      x10, [x11, #0x18]
0xfffffe00095fedcc: stp      x8, x10, [x9, #8]
0xfffffe00095fedd0: mov      w20, #1
0xfffffe00095fedd4: b        #0xfffffe00095fef98
0xfffffe00095fedd8: ldr      w8, [x21, #0x180]
0xfffffe00095feddc: cmp      w8, #3
0xfffffe00095fede0: b.hi     #0xfffffe00095fee40
0xfffffe00095fede4: lsl      x8, x8, #3
0xfffffe00095fede8: adrp     x9, #0xfffffe000814e000
0xfffffe00095fedec: add      x9, x9, #0xed0
0xfffffe00095fedf0: cmp      x8, w8, sxtw
0xfffffe00095fedf4: add      x10, x9, w8, sxtw
0xfffffe00095fedf8: add      x16, x9, x8
0xfffffe00095fedfc: movk     x16, #0x2bad, lsl #48
0xfffffe00095fee00: csel     x10, x10, x16, eq
0xfffffe00095fee04: ldr      x8, [x10]
0xfffffe00095fee08: b        #0xfffffe00095fee48
0xfffffe00095fee0c: ldr      w8, [x21, #0x180]
0xfffffe00095fee10: cmp      w8, #3
0xfffffe00095fee14: b.hi     #0xfffffe00095feee4
0xfffffe00095fee18: lsl      x8, x8, #3
0xfffffe00095fee1c: adrp     x9, #0xfffffe000814e000
0xfffffe00095fee20: add      x9, x9, #0xed0
0xfffffe00095fee24: cmp      x8, w8, sxtw
0xfffffe00095fee28: add      x10, x9, w8, sxtw
0xfffffe00095fee2c: add      x16, x9, x8
0xfffffe00095fee30: movk     x16, #0x2bad, lsl #48
0xfffffe00095fee34: csel     x10, x10, x16, eq
0xfffffe00095fee38: ldr      x8, [x10]
0xfffffe00095fee3c: b        #0xfffffe00095feeec
0xfffffe00095fee40: adrp     x8, #0xfffffe00074b8000
0xfffffe00095fee44: add      x8, x8, #0x69c
0xfffffe00095fee48: adrp     x9, #0xfffffe00074c4000
0xfffffe00095fee4c: add      x9, x9, #0x808
0xfffffe00095fee50: stp      x8, x9, [sp]
0xfffffe00095fee54: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fee58: add      x0, x0, #0xec0
0xfffffe00095fee5c: adrp     x1, #0xfffffe0008163000
0xfffffe00095fee60: ldr      x1, [x1, #0xbf8]
0xfffffe00095fee64: adrp     x3, #0xfffffe00074f6000
0xfffffe00095fee68: add      x3, x3, #0xc4d
0xfffffe00095fee6c: mov      w2, #0x10
0xfffffe00095fee70: bl       #0xfffffe000964c288
0xfffffe00095fee74: mov      w20, #0
0xfffffe00095fee78: b        #0xfffffe00095fefb8
0xfffffe00095fee7c: ldr      w8, [x21, #0x180]
0xfffffe00095fee80: cmp      w8, #3
0xfffffe00095fee84: b.hi     #0xfffffe00095fef24
0xfffffe00095fee88: lsl      x8, x8, #3
0xfffffe00095fee8c: adrp     x9, #0xfffffe000814e000
0xfffffe00095fee90: add      x9, x9, #0xed0
0xfffffe00095fee94: cmp      x8, w8, sxtw
0xfffffe00095fee98: add      x10, x9, w8, sxtw
0xfffffe00095fee9c: add      x16, x9, x8
0xfffffe00095feea0: movk     x16, #0x2bad, lsl #48
0xfffffe00095feea4: csel     x10, x10, x16, eq
0xfffffe00095feea8: ldr      x8, [x10]
0xfffffe00095feeac: b        #0xfffffe00095fef2c
0xfffffe00095feeb0: ldr      w8, [x21, #0x180]
0xfffffe00095feeb4: cmp      w8, #3
0xfffffe00095feeb8: b.hi     #0xfffffe00095fef60
0xfffffe00095feebc: lsl      x8, x8, #3
0xfffffe00095feec0: adrp     x9, #0xfffffe000814e000
0xfffffe00095feec4: add      x9, x9, #0xed0
0xfffffe00095feec8: cmp      x8, w8, sxtw
0xfffffe00095feecc: add      x10, x9, w8, sxtw
0xfffffe00095feed0: add      x16, x9, x8
0xfffffe00095feed4: movk     x16, #0x2bad, lsl #48
0xfffffe00095feed8: csel     x10, x10, x16, eq
0xfffffe00095feedc: ldr      x8, [x10]
0xfffffe00095feee0: b        #0xfffffe00095fef68
0xfffffe00095feee4: adrp     x8, #0xfffffe00074b8000
0xfffffe00095feee8: add      x8, x8, #0x69c
0xfffffe00095feeec: adrp     x9, #0xfffffe00074c4000
0xfffffe00095feef0: add      x9, x9, #0x808
0xfffffe00095feef4: stp      x9, x22, [sp, #8]
0xfffffe00095feef8: str      x8, [sp]
0xfffffe00095feefc: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fef00: add      x0, x0, #0xec0
0xfffffe00095fef04: adrp     x1, #0xfffffe0008163000
0xfffffe00095fef08: ldr      x1, [x1, #0xbf8]
0xfffffe00095fef0c: adrp     x3, #0xfffffe00074f6000
0xfffffe00095fef10: add      x3, x3, #0xc1b
0xfffffe00095fef14: mov      w2, #0x10
0xfffffe00095fef18: bl       #0xfffffe000964c288
0xfffffe00095fef1c: mov      w20, #0
0xfffffe00095fef20: b        #0xfffffe00095fef98
0xfffffe00095fef24: adrp     x8, #0xfffffe00074b8000
0xfffffe00095fef28: add      x8, x8, #0x69c
0xfffffe00095fef2c: adrp     x9, #0xfffffe00074c4000
0xfffffe00095fef30: add      x9, x9, #0x808
0xfffffe00095fef34: stp      x8, x9, [sp]
0xfffffe00095fef38: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fef3c: add      x0, x0, #0xec0
0xfffffe00095fef40: adrp     x1, #0xfffffe0008163000
0xfffffe00095fef44: ldr      x1, [x1, #0xbf8]
0xfffffe00095fef48: adrp     x3, #0xfffffe00074f6000
0xfffffe00095fef4c: add      x3, x3, #0xbe2
0xfffffe00095fef50: mov      w2, #0x10
0xfffffe00095fef54: bl       #0xfffffe000964c288
0xfffffe00095fef58: mov      w20, #0
0xfffffe00095fef5c: b        #0xfffffe00095fef98
0xfffffe00095fef60: adrp     x8, #0xfffffe00074b8000
0xfffffe00095fef64: add      x8, x8, #0x69c
0xfffffe00095fef68: adrp     x9, #0xfffffe00074c4000
0xfffffe00095fef6c: add      x9, x9, #0x808
0xfffffe00095fef70: stp      x8, x9, [sp]
0xfffffe00095fef74: adrp     x0, #0xfffffe00074b7000
0xfffffe00095fef78: add      x0, x0, #0xec0
0xfffffe00095fef7c: adrp     x1, #0xfffffe0008163000
0xfffffe00095fef80: ldr      x1, [x1, #0xbf8]
0xfffffe00095fef84: adrp     x3, #0xfffffe00074f6000
0xfffffe00095fef88: add      x3, x3, #0xbb8
0xfffffe00095fef8c: mov      w2, #0x10
0xfffffe00095fef90: bl       #0xfffffe000964c288
0xfffffe00095fef94: mov      w20, #0
0xfffffe00095fef98: ldr      x16, [x19]
0xfffffe00095fef9c: mov      x17, x19
0xfffffe00095fefa0: movk     x17, #0xcda1, lsl #48
0xfffffe00095fefa4: autda    x16, x17
0xfffffe00095fefa8: ldr      x8, [x16, #0x28]!
0xfffffe00095fefac: mov      x0, x19
0xfffffe00095fefb0: movk     x16, #0x3a87, lsl #48
0xfffffe00095fefb4: blraa    x8, x16
0xfffffe00095fefb8: ldur     x8, [x29, #-0x38]
0xfffffe00095fefbc: adrp     x9, #0xfffffe0008163000
0xfffffe00095fefc0: ldr      x9, [x9, #0xbf0]
0xfffffe00095fefc4: ldr      x9, [x9]
0xfffffe00095fefc8: cmp      x9, x8
0xfffffe00095fefcc: b.ne     #0xfffffe00095fefec
0xfffffe00095fefd0: mov      x0, x20
0xfffffe00095fefd4: ldp      x29, x30, [sp, #0xa0]
0xfffffe00095fefd8: ldp      x20, x19, [sp, #0x90]
0xfffffe00095fefdc: ldp      x22, x21, [sp, #0x80]
0xfffffe00095fefe0: ldp      x24, x23, [sp, #0x70]
0xfffffe00095fefe4: add      sp, sp, #0xb0
0xfffffe00095fefe8: retab    
0xfffffe00095fefec: bl       #0xfffffe000964c278