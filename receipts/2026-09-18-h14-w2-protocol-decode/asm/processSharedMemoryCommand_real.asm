; processSharedMemoryCommand_real [0xfffffe00095f8f08-0xfffffe00095f933c) 0x434 bytes
0xfffffe00095f8f08: bti      c
0xfffffe00095f8f0c: pacibsp  
0xfffffe00095f8f10: sub      sp, sp, #0x60
0xfffffe00095f8f14: stp      x24, x23, [sp, #0x20]
0xfffffe00095f8f18: stp      x22, x21, [sp, #0x30]
0xfffffe00095f8f1c: stp      x20, x19, [sp, #0x40]
0xfffffe00095f8f20: stp      x29, x30, [sp, #0x50]
0xfffffe00095f8f24: add      x29, sp, #0x50
0xfffffe00095f8f28: mov      x22, x6
0xfffffe00095f8f2c: mov      x23, x5
0xfffffe00095f8f30: mov      x21, x4
0xfffffe00095f8f34: mov      x20, x3
0xfffffe00095f8f38: mov      x24, x2
0xfffffe00095f8f3c: mov      x19, x0
0xfffffe00095f8f40: cmp      w1, #0x502
0xfffffe00095f8f44: b.eq     #0xfffffe00095f8fe0
0xfffffe00095f8f48: cmp      w1, #0x501
0xfffffe00095f8f4c: b.eq     #0xfffffe00095f8f9c
0xfffffe00095f8f50: cmp      w1, #0x500
0xfffffe00095f8f54: b.ne     #0xfffffe00095f91cc
0xfffffe00095f8f58: adrp     x8, #0xfffffe000cb6d000
0xfffffe00095f8f5c: add      x8, x8, #0xc60
0xfffffe00095f8f60: ldrb     w8, [x8]
0xfffffe00095f8f64: tbz      w8, #2, #0xfffffe00095f9170
0xfffffe00095f8f68: ldr      w8, [x19, #0x180]
0xfffffe00095f8f6c: cmp      w8, #3
0xfffffe00095f8f70: b.hi     #0xfffffe00095f9138
0xfffffe00095f8f74: lsl      x8, x8, #3
0xfffffe00095f8f78: adrp     x9, #0xfffffe000814d000
0xfffffe00095f8f7c: add      x9, x9, #0x938
0xfffffe00095f8f80: cmp      x8, w8, sxtw
0xfffffe00095f8f84: add      x10, x9, w8, sxtw
0xfffffe00095f8f88: add      x16, x9, x8
0xfffffe00095f8f8c: movk     x16, #0x2bad, lsl #48
0xfffffe00095f8f90: csel     x10, x10, x16, eq
0xfffffe00095f8f94: ldr      x8, [x10]
0xfffffe00095f8f98: b        #0xfffffe00095f9140
0xfffffe00095f8f9c: adrp     x8, #0xfffffe000cb6d000
0xfffffe00095f8fa0: add      x8, x8, #0xc60
0xfffffe00095f8fa4: ldrb     w8, [x8]
0xfffffe00095f8fa8: tbz      w8, #2, #0xfffffe00095f909c
0xfffffe00095f8fac: ldr      w8, [x19, #0x180]
0xfffffe00095f8fb0: cmp      w8, #3
0xfffffe00095f8fb4: b.hi     #0xfffffe00095f9064
0xfffffe00095f8fb8: lsl      x8, x8, #3
0xfffffe00095f8fbc: adrp     x9, #0xfffffe000814d000
0xfffffe00095f8fc0: add      x9, x9, #0x938
0xfffffe00095f8fc4: cmp      x8, w8, sxtw
0xfffffe00095f8fc8: add      x10, x9, w8, sxtw
0xfffffe00095f8fcc: add      x16, x9, x8
0xfffffe00095f8fd0: movk     x16, #0x2bad, lsl #48
0xfffffe00095f8fd4: csel     x10, x10, x16, eq
0xfffffe00095f8fd8: ldr      x8, [x10]
0xfffffe00095f8fdc: b        #0xfffffe00095f906c
0xfffffe00095f8fe0: mov      x0, x23
0xfffffe00095f8fe4: mov      x1, x22
0xfffffe00095f8fe8: mov      w2, #0
0xfffffe00095f8fec: bl       #0xfffffe00095f933c
0xfffffe00095f8ff0: cbz      x0, #0xfffffe00095f9030
0xfffffe00095f8ff4: mov      x22, x0
0xfffffe00095f8ff8: mov      w8, #2
0xfffffe00095f8ffc: str      w8, [x0, #0x24]
0xfffffe00095f9000: stp      x24, x20, [x0, #0x28]
0xfffffe00095f9004: str      w21, [x0, #0x38]
0xfffffe00095f9008: ldr      x0, [x19, #0x140]
0xfffffe00095f900c: mov      x1, x22
0xfffffe00095f9010: bl       #0xfffffe00095013c0
0xfffffe00095f9014: ldr      x16, [x22]
0xfffffe00095f9018: mov      x17, x22
0xfffffe00095f901c: movk     x17, #0xcda1, lsl #48
0xfffffe00095f9020: autda    x16, x17
0xfffffe00095f9024: ldr      x8, [x16, #0x28]!
0xfffffe00095f9028: mov      x0, x22
0xfffffe00095f902c: b        #0xfffffe00095f91c4
0xfffffe00095f9030: ldr      w8, [x19, #0x180]
0xfffffe00095f9034: cmp      w8, #3
0xfffffe00095f9038: b.hi     #0xfffffe00095f925c
0xfffffe00095f903c: lsl      x8, x8, #3
0xfffffe00095f9040: adrp     x9, #0xfffffe000814d000
0xfffffe00095f9044: add      x9, x9, #0x938
0xfffffe00095f9048: cmp      x8, w8, sxtw
0xfffffe00095f904c: add      x10, x9, w8, sxtw
0xfffffe00095f9050: add      x16, x9, x8
0xfffffe00095f9054: movk     x16, #0x2bad, lsl #48
0xfffffe00095f9058: csel     x10, x10, x16, eq
0xfffffe00095f905c: ldr      x8, [x10]
0xfffffe00095f9060: b        #0xfffffe00095f9264
0xfffffe00095f9064: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f9068: add      x8, x8, #0x69c
0xfffffe00095f906c: adrp     x9, #0xfffffe00074c4000
0xfffffe00095f9070: add      x9, x9, #0x50b
0xfffffe00095f9074: stp      x9, x24, [sp, #8]
0xfffffe00095f9078: str      x8, [sp]
0xfffffe00095f907c: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f9080: add      x0, x0, #0xec0
0xfffffe00095f9084: adrp     x1, #0xfffffe0008163000
0xfffffe00095f9088: ldr      x1, [x1, #0xbf8]
0xfffffe00095f908c: adrp     x3, #0xfffffe00074f5000
0xfffffe00095f9090: add      x3, x3, #0x680
0xfffffe00095f9094: mov      w2, #0
0xfffffe00095f9098: bl       #0xfffffe000964c288
0xfffffe00095f909c: mov      w0, #0x40
0xfffffe00095f90a0: movk     w0, #0x61b, lsl #16
0xfffffe00095f90a4: mov      x1, x24
0xfffffe00095f90a8: mov      x2, #0
0xfffffe00095f90ac: mov      x3, #0
0xfffffe00095f90b0: mov      x4, #0
0xfffffe00095f90b4: mov      x5, #0
0xfffffe00095f90b8: bl       #0xfffffe000964c418
0xfffffe00095f90bc: ldr      x8, [x19, #0x1f0]
0xfffffe00095f90c0: add      x8, x8, #1
0xfffffe00095f90c4: str      x8, [x19, #0x1f0]
0xfffffe00095f90c8: mov      w8, #0x5546
0xfffffe00095f90cc: movk     w8, #0x5442, lsl #16
0xfffffe00095f90d0: cmp      x21, x8
0xfffffe00095f90d4: b.ne     #0xfffffe00095f90dc
0xfffffe00095f90d8: str      xzr, [x19, #0x3f60]
0xfffffe00095f90dc: mov      x0, x23
0xfffffe00095f90e0: mov      x1, x22
0xfffffe00095f90e4: mov      w2, #0
0xfffffe00095f90e8: bl       #0xfffffe00095f933c
0xfffffe00095f90ec: cbz      x0, #0xfffffe00095f9104
0xfffffe00095f90f0: mov      x21, x0
0xfffffe00095f90f4: mov      w8, #1
0xfffffe00095f90f8: str      w8, [x0, #0x24]
0xfffffe00095f90fc: stp      x24, x20, [x0, #0x28]
0xfffffe00095f9100: b        #0xfffffe00095f91a0
0xfffffe00095f9104: ldr      w8, [x19, #0x180]
0xfffffe00095f9108: cmp      w8, #3
0xfffffe00095f910c: b.hi     #0xfffffe00095f9220
0xfffffe00095f9110: lsl      x8, x8, #3
0xfffffe00095f9114: adrp     x9, #0xfffffe000814d000
0xfffffe00095f9118: add      x9, x9, #0x938
0xfffffe00095f911c: cmp      x8, w8, sxtw
0xfffffe00095f9120: add      x10, x9, w8, sxtw
0xfffffe00095f9124: add      x16, x9, x8
0xfffffe00095f9128: movk     x16, #0x2bad, lsl #48
0xfffffe00095f912c: csel     x10, x10, x16, eq
0xfffffe00095f9130: ldr      x8, [x10]
0xfffffe00095f9134: b        #0xfffffe00095f9228
0xfffffe00095f9138: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f913c: add      x8, x8, #0x69c
0xfffffe00095f9140: stp      x20, x21, [sp, #0x10]
0xfffffe00095f9144: adrp     x9, #0xfffffe00074c4000
0xfffffe00095f9148: add      x9, x9, #0x50b
0xfffffe00095f914c: stp      x8, x9, [sp]
0xfffffe00095f9150: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f9154: add      x0, x0, #0xec0
0xfffffe00095f9158: adrp     x1, #0xfffffe0008163000
0xfffffe00095f915c: ldr      x1, [x1, #0xbf8]
0xfffffe00095f9160: adrp     x3, #0xfffffe00074f5000
0xfffffe00095f9164: add      x3, x3, #0x5b9
0xfffffe00095f9168: mov      w2, #0
0xfffffe00095f916c: bl       #0xfffffe000964c288
0xfffffe00095f9170: ldr      x24, [x19, #0x3a90]
0xfffffe00095f9174: mov      x0, x23
0xfffffe00095f9178: mov      x1, x22
0xfffffe00095f917c: mov      x2, x21
0xfffffe00095f9180: bl       #0xfffffe00095f933c
0xfffffe00095f9184: cbz      x0, #0xfffffe00095f91ec
0xfffffe00095f9188: mov      x21, x0
0xfffffe00095f918c: cmp      x24, w20, uxtw
0xfffffe00095f9190: csel     x8, x24, x20, hi
0xfffffe00095f9194: str      wzr, [x0, #0x24]
0xfffffe00095f9198: mov      w8, w8
0xfffffe00095f919c: stp      xzr, x8, [x0, #0x28]
0xfffffe00095f91a0: ldr      x0, [x19, #0x140]
0xfffffe00095f91a4: mov      x1, x21
0xfffffe00095f91a8: bl       #0xfffffe00095013c0
0xfffffe00095f91ac: ldr      x16, [x21]
0xfffffe00095f91b0: mov      x17, x21
0xfffffe00095f91b4: movk     x17, #0xcda1, lsl #48
0xfffffe00095f91b8: autda    x16, x17
0xfffffe00095f91bc: ldr      x8, [x16, #0x28]!
0xfffffe00095f91c0: mov      x0, x21
0xfffffe00095f91c4: movk     x16, #0x3a87, lsl #48
0xfffffe00095f91c8: blraa    x8, x16
0xfffffe00095f91cc: mov      w19, #0
0xfffffe00095f91d0: mov      x0, x19
0xfffffe00095f91d4: ldp      x29, x30, [sp, #0x50]
0xfffffe00095f91d8: ldp      x20, x19, [sp, #0x40]
0xfffffe00095f91dc: ldp      x22, x21, [sp, #0x30]
0xfffffe00095f91e0: ldp      x24, x23, [sp, #0x20]
0xfffffe00095f91e4: add      sp, sp, #0x60
0xfffffe00095f91e8: retab    
0xfffffe00095f91ec: ldr      w8, [x19, #0x180]
0xfffffe00095f91f0: cmp      w8, #4
0xfffffe00095f91f4: b.hs     #0xfffffe00095f9298
0xfffffe00095f91f8: lsl      x8, x8, #3
0xfffffe00095f91fc: adrp     x9, #0xfffffe000814d000
0xfffffe00095f9200: add      x9, x9, #0x938
0xfffffe00095f9204: cmp      x8, w8, sxtw
0xfffffe00095f9208: add      x10, x9, w8, sxtw
0xfffffe00095f920c: add      x16, x9, x8
0xfffffe00095f9210: movk     x16, #0x2bad, lsl #48
0xfffffe00095f9214: csel     x10, x10, x16, eq
0xfffffe00095f9218: ldr      x8, [x10]
0xfffffe00095f921c: b        #0xfffffe00095f92a0
0xfffffe00095f9220: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f9224: add      x8, x8, #0x69c
0xfffffe00095f9228: adrp     x9, #0xfffffe00074c4000
0xfffffe00095f922c: add      x9, x9, #0x50b
0xfffffe00095f9230: stp      x8, x9, [sp]
0xfffffe00095f9234: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f9238: add      x0, x0, #0xec0
0xfffffe00095f923c: adrp     x1, #0xfffffe0008163000
0xfffffe00095f9240: ldr      x1, [x1, #0xbf8]
0xfffffe00095f9244: adrp     x3, #0xfffffe00074f5000
0xfffffe00095f9248: add      x3, x3, #0x6b5
0xfffffe00095f924c: mov      w2, #0x10
0xfffffe00095f9250: bl       #0xfffffe000964c288
0xfffffe00095f9254: mov      w19, #0
0xfffffe00095f9258: b        #0xfffffe00095f91d0
0xfffffe00095f925c: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f9260: add      x8, x8, #0x69c
0xfffffe00095f9264: adrp     x9, #0xfffffe00074c4000
0xfffffe00095f9268: add      x9, x9, #0x50b
0xfffffe00095f926c: stp      x8, x9, [sp]
0xfffffe00095f9270: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f9274: add      x0, x0, #0xec0
0xfffffe00095f9278: adrp     x1, #0xfffffe0008163000
0xfffffe00095f927c: ldr      x1, [x1, #0xbf8]
0xfffffe00095f9280: adrp     x3, #0xfffffe00074f5000
0xfffffe00095f9284: add      x3, x3, #0x6f7
0xfffffe00095f9288: mov      w2, #0x10
0xfffffe00095f928c: bl       #0xfffffe000964c288
0xfffffe00095f9290: mov      w19, #0
0xfffffe00095f9294: b        #0xfffffe00095f91d0
0xfffffe00095f9298: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f929c: add      x8, x8, #0x69c
0xfffffe00095f92a0: adrp     x20, #0xfffffe00074c4000
0xfffffe00095f92a4: add      x20, x20, #0x50b
0xfffffe00095f92a8: stp      x8, x20, [sp]
0xfffffe00095f92ac: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f92b0: add      x0, x0, #0xec0
0xfffffe00095f92b4: adrp     x1, #0xfffffe0008163000
0xfffffe00095f92b8: ldr      x1, [x1, #0xbf8]
0xfffffe00095f92bc: adrp     x3, #0xfffffe00074f5000
0xfffffe00095f92c0: add      x3, x3, #0x5fe
0xfffffe00095f92c4: mov      w2, #0x10
0xfffffe00095f92c8: bl       #0xfffffe000964c288
0xfffffe00095f92cc: ldr      w8, [x19, #0x180]
0xfffffe00095f92d0: cmp      w8, #3
0xfffffe00095f92d4: b.hi     #0xfffffe00095f9300
0xfffffe00095f92d8: lsl      x8, x8, #3
0xfffffe00095f92dc: adrp     x9, #0xfffffe000814d000
0xfffffe00095f92e0: add      x9, x9, #0x938
0xfffffe00095f92e4: cmp      x8, w8, sxtw
0xfffffe00095f92e8: add      x10, x9, w8, sxtw
0xfffffe00095f92ec: add      x16, x9, x8
0xfffffe00095f92f0: movk     x16, #0x2bad, lsl #48
0xfffffe00095f92f4: csel     x10, x10, x16, eq
0xfffffe00095f92f8: ldr      x8, [x10]
0xfffffe00095f92fc: b        #0xfffffe00095f9308
0xfffffe00095f9300: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f9304: add      x8, x8, #0x69c
0xfffffe00095f9308: mov      w19, #0x2bd
0xfffffe00095f930c: movk     w19, #0xe000, lsl #16
0xfffffe00095f9310: stp      x20, x19, [sp, #8]
0xfffffe00095f9314: str      x8, [sp]
0xfffffe00095f9318: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f931c: add      x0, x0, #0xec0
0xfffffe00095f9320: adrp     x1, #0xfffffe0008163000
0xfffffe00095f9324: ldr      x1, [x1, #0xbf8]
0xfffffe00095f9328: adrp     x3, #0xfffffe00074f5000
0xfffffe00095f932c: add      x3, x3, #0x640
0xfffffe00095f9330: mov      w2, #0x10
0xfffffe00095f9334: bl       #0xfffffe000964c288
0xfffffe00095f9338: b        #0xfffffe00095f91d0