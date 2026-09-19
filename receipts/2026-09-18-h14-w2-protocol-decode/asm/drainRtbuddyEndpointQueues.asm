; drainRtbuddyEndpointQueues [0xfffffe00095ec074-0xfffffe00095ec2c0) 0x24c bytes
0xfffffe00095ec074: bti      c
0xfffffe00095ec078: pacibsp  
0xfffffe00095ec07c: sub      sp, sp, #0xa0
0xfffffe00095ec080: stp      x28, x27, [sp, #0x40]
0xfffffe00095ec084: stp      x26, x25, [sp, #0x50]
0xfffffe00095ec088: stp      x24, x23, [sp, #0x60]
0xfffffe00095ec08c: stp      x22, x21, [sp, #0x70]
0xfffffe00095ec090: stp      x20, x19, [sp, #0x80]
0xfffffe00095ec094: stp      x29, x30, [sp, #0x90]
0xfffffe00095ec098: add      x29, sp, #0x90
0xfffffe00095ec09c: mov      x19, x0
0xfffffe00095ec0a0: add      x8, x0, #0x5c0
0xfffffe00095ec0a4: str      x8, [sp, #0x30]
0xfffffe00095ec0a8: mov      w27, #1
0xfffffe00095ec0ac: adrp     x28, #0xfffffe00074b8000
0xfffffe00095ec0b0: add      x28, x28, #0x69c
0xfffffe00095ec0b4: adrp     x23, #0xfffffe00074c3000
0xfffffe00095ec0b8: add      x23, x23, #0xfc3
0xfffffe00095ec0bc: adrp     x20, #0xfffffe00074b7000
0xfffffe00095ec0c0: add      x20, x20, #0xec0
0xfffffe00095ec0c4: adrp     x21, #0xfffffe0008163000
0xfffffe00095ec0c8: ldr      x21, [x21, #0xbf8]
0xfffffe00095ec0cc: ldr      x8, [sp, #0x30]
0xfffffe00095ec0d0: add      x24, x8, x27, lsl #6
0xfffffe00095ec0d4: str      xzr, [sp, #0x38]
0xfffffe00095ec0d8: ldr      x0, [x24, #0x28]
0xfffffe00095ec0dc: add      x1, sp, #0x38
0xfffffe00095ec0e0: mov      w2, #0
0xfffffe00095ec0e4: bl       #0xfffffe000964bc78
0xfffffe00095ec0e8: cbnz     w0, #0xfffffe00095ec294
0xfffffe00095ec0ec: mov      w26, #0
0xfffffe00095ec0f0: cmp      x27, #6
0xfffffe00095ec0f4: b.ne     #0xfffffe00095ec214
0xfffffe00095ec0f8: ldr      x8, [x24, #0x18]
0xfffffe00095ec0fc: cbz      x8, #0xfffffe00095ec1a4
0xfffffe00095ec100: ldr      x0, [x8, #0x30]
0xfffffe00095ec104: cbz      x0, #0xfffffe00095ec1a4
0xfffffe00095ec108: ldr      x8, [sp, #0x38]
0xfffffe00095ec10c: and      x22, x8, #0xffffff
0xfffffe00095ec110: ubfx     x25, x8, #0x18, #0x18
0xfffffe00095ec114: ldr      x16, [x0]
0xfffffe00095ec118: mov      x17, x0
0xfffffe00095ec11c: movk     x17, #0xcda1, lsl #48
0xfffffe00095ec120: autda    x16, x17
0xfffffe00095ec124: mov      x17, #0x148
0xfffffe00095ec128: add      x16, x16, x17
0xfffffe00095ec12c: ldr      x8, [x16]
0xfffffe00095ec130: movk     x16, #0xfd11, lsl #48
0xfffffe00095ec134: blraa    x8, x16
0xfffffe00095ec138: add      x8, x25, x22
0xfffffe00095ec13c: cmp      x22, x0
0xfffffe00095ec140: ccmp     x8, x0, #2, lo
0xfffffe00095ec144: b.ls     #0xfffffe00095ec1f8
0xfffffe00095ec148: ldr      w9, [x19, #0x180]
0xfffffe00095ec14c: mov      x8, x28
0xfffffe00095ec150: cmp      w9, #4
0xfffffe00095ec154: b.hs     #0xfffffe00095ec17c
0xfffffe00095ec158: lsl      x8, x9, #3
0xfffffe00095ec15c: adrp     x10, #0xfffffe000814d000
0xfffffe00095ec160: add      x10, x10, #0x1a0
0xfffffe00095ec164: cmp      x8, w8, sxtw
0xfffffe00095ec168: add      x9, x10, w8, sxtw
0xfffffe00095ec16c: add      x16, x10, x8
0xfffffe00095ec170: movk     x16, #0x2bad, lsl #48
0xfffffe00095ec174: csel     x9, x9, x16, eq
0xfffffe00095ec178: ldr      x8, [x9]
0xfffffe00095ec17c: stp      x25, x0, [sp, #0x18]
0xfffffe00095ec180: stp      x23, x22, [sp, #8]
0xfffffe00095ec184: str      x8, [sp]
0xfffffe00095ec188: mov      x0, x20
0xfffffe00095ec18c: mov      x1, x21
0xfffffe00095ec190: mov      w2, #0x10
0xfffffe00095ec194: adrp     x3, #0xfffffe00074f3000
0xfffffe00095ec198: add      x3, x3, #0xea0
0xfffffe00095ec19c: bl       #0xfffffe000964c288
0xfffffe00095ec1a0: b        #0xfffffe00095ec214
0xfffffe00095ec1a4: ldr      w9, [x19, #0x180]
0xfffffe00095ec1a8: mov      x8, x28
0xfffffe00095ec1ac: cmp      w9, #3
0xfffffe00095ec1b0: b.hi     #0xfffffe00095ec1d8
0xfffffe00095ec1b4: lsl      x8, x9, #3
0xfffffe00095ec1b8: adrp     x10, #0xfffffe000814d000
0xfffffe00095ec1bc: add      x10, x10, #0x1a0
0xfffffe00095ec1c0: cmp      x8, w8, sxtw
0xfffffe00095ec1c4: add      x9, x10, w8, sxtw
0xfffffe00095ec1c8: add      x16, x10, x8
0xfffffe00095ec1cc: movk     x16, #0x2bad, lsl #48
0xfffffe00095ec1d0: csel     x9, x9, x16, eq
0xfffffe00095ec1d4: ldr      x8, [x9]
0xfffffe00095ec1d8: stp      x8, x23, [sp]
0xfffffe00095ec1dc: mov      x0, x20
0xfffffe00095ec1e0: mov      x1, x21
0xfffffe00095ec1e4: mov      w2, #0x10
0xfffffe00095ec1e8: adrp     x3, #0xfffffe00074f3000
0xfffffe00095ec1ec: add      x3, x3, #0xe4d
0xfffffe00095ec1f0: bl       #0xfffffe000964c288
0xfffffe00095ec1f4: b        #0xfffffe00095ec214
0xfffffe00095ec1f8: ldr      x8, [x24, #0x18]
0xfffffe00095ec1fc: ldr      x8, [x8, #0x38]
0xfffffe00095ec200: add      x1, x8, x22
0xfffffe00095ec204: mov      x0, x19
0xfffffe00095ec208: mov      x2, x25
0xfffffe00095ec20c: mov      x3, #0
0xfffffe00095ec210: bl       #0xfffffe00095e26a0
0xfffffe00095ec214: str      xzr, [sp, #0x38]
0xfffffe00095ec218: ldr      x0, [x24, #0x28]
0xfffffe00095ec21c: add      x1, sp, #0x38
0xfffffe00095ec220: mov      w2, #0
0xfffffe00095ec224: bl       #0xfffffe000964bc78
0xfffffe00095ec228: sub      w26, w26, #1
0xfffffe00095ec22c: cbz      w0, #0xfffffe00095ec0f0
0xfffffe00095ec230: cmp      x27, #6
0xfffffe00095ec234: b.eq     #0xfffffe00095ec294
0xfffffe00095ec238: cbz      w26, #0xfffffe00095ec294
0xfffffe00095ec23c: ldr      w9, [x19, #0x180]
0xfffffe00095ec240: mov      x8, x28
0xfffffe00095ec244: cmp      w9, #3
0xfffffe00095ec248: b.hi     #0xfffffe00095ec270
0xfffffe00095ec24c: lsl      x8, x9, #3
0xfffffe00095ec250: adrp     x10, #0xfffffe000814d000
0xfffffe00095ec254: add      x10, x10, #0x1a0
0xfffffe00095ec258: cmp      x8, w8, sxtw
0xfffffe00095ec25c: add      x9, x10, w8, sxtw
0xfffffe00095ec260: add      x16, x10, x8
0xfffffe00095ec264: movk     x16, #0x2bad, lsl #48
0xfffffe00095ec268: csel     x9, x9, x16, eq
0xfffffe00095ec26c: ldr      x8, [x9]
0xfffffe00095ec270: neg      w9, w26
0xfffffe00095ec274: stp      x9, x27, [sp, #0x10]
0xfffffe00095ec278: stp      x8, x23, [sp]
0xfffffe00095ec27c: mov      x0, x20
0xfffffe00095ec280: mov      x1, x21
0xfffffe00095ec284: mov      w2, #0
0xfffffe00095ec288: adrp     x3, #0xfffffe00074f3000
0xfffffe00095ec28c: add      x3, x3, #0xf11
0xfffffe00095ec290: bl       #0xfffffe000964c288
0xfffffe00095ec294: add      x27, x27, #1
0xfffffe00095ec298: cmp      x27, #7
0xfffffe00095ec29c: b.ne     #0xfffffe00095ec0cc
0xfffffe00095ec2a0: ldp      x29, x30, [sp, #0x90]
0xfffffe00095ec2a4: ldp      x20, x19, [sp, #0x80]
0xfffffe00095ec2a8: ldp      x22, x21, [sp, #0x70]
0xfffffe00095ec2ac: ldp      x24, x23, [sp, #0x60]
0xfffffe00095ec2b0: ldp      x26, x25, [sp, #0x50]
0xfffffe00095ec2b4: ldp      x28, x27, [sp, #0x40]
0xfffffe00095ec2b8: add      sp, sp, #0xa0
0xfffffe00095ec2bc: retab    