; rtbuddyEndpointSendInPlace [0xfffffe00095f3314-0xfffffe00095f3544) 0x230 bytes
0xfffffe00095f3314: bti      c
0xfffffe00095f3318: pacibsp  
0xfffffe00095f331c: sub      sp, sp, #0x80
0xfffffe00095f3320: stp      x24, x23, [sp, #0x40]
0xfffffe00095f3324: stp      x22, x21, [sp, #0x50]
0xfffffe00095f3328: stp      x20, x19, [sp, #0x60]
0xfffffe00095f332c: stp      x29, x30, [sp, #0x70]
0xfffffe00095f3330: add      x29, sp, #0x70
0xfffffe00095f3334: mov      x22, x3
0xfffffe00095f3338: mov      x23, x2
0xfffffe00095f333c: mov      x20, x1
0xfffffe00095f3340: mov      x21, x0
0xfffffe00095f3344: mov      w19, #0x2d8
0xfffffe00095f3348: movk     w19, #0xe000, lsl #16
0xfffffe00095f334c: tbnz     w5, #0, #0xfffffe00095f338c
0xfffffe00095f3350: ldrb     w8, [x21, #0x404]
0xfffffe00095f3354: tbnz     w8, #0, #0xfffffe00095f338c
0xfffffe00095f3358: ldr      w8, [x21, #0x180]
0xfffffe00095f335c: cmp      w8, #3
0xfffffe00095f3360: b.hi     #0xfffffe00095f33d0
0xfffffe00095f3364: lsl      x8, x8, #3
0xfffffe00095f3368: adrp     x9, #0xfffffe000814d000
0xfffffe00095f336c: add      x9, x9, #0x1a0
0xfffffe00095f3370: cmp      x8, w8, sxtw
0xfffffe00095f3374: add      x10, x9, w8, sxtw
0xfffffe00095f3378: add      x16, x9, x8
0xfffffe00095f337c: movk     x16, #0x2bad, lsl #48
0xfffffe00095f3380: csel     x10, x10, x16, eq
0xfffffe00095f3384: ldr      x8, [x10]
0xfffffe00095f3388: b        #0xfffffe00095f33d8
0xfffffe00095f338c: adrp     x8, #0xfffffe000cb6d000
0xfffffe00095f3390: add      x8, x8, #0xc60
0xfffffe00095f3394: ldrb     w8, [x8, #1]
0xfffffe00095f3398: tbz      w8, #2, #0xfffffe00095f3454
0xfffffe00095f339c: ldr      w8, [x21, #0x180]
0xfffffe00095f33a0: cmp      w8, #3
0xfffffe00095f33a4: b.hi     #0xfffffe00095f3414
0xfffffe00095f33a8: lsl      x8, x8, #3
0xfffffe00095f33ac: adrp     x9, #0xfffffe000814d000
0xfffffe00095f33b0: add      x9, x9, #0x1a0
0xfffffe00095f33b4: cmp      x8, w8, sxtw
0xfffffe00095f33b8: add      x10, x9, w8, sxtw
0xfffffe00095f33bc: add      x16, x9, x8
0xfffffe00095f33c0: movk     x16, #0x2bad, lsl #48
0xfffffe00095f33c4: csel     x10, x10, x16, eq
0xfffffe00095f33c8: ldr      x8, [x10]
0xfffffe00095f33cc: b        #0xfffffe00095f341c
0xfffffe00095f33d0: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f33d4: add      x8, x8, #0x69c
0xfffffe00095f33d8: ldr      x9, [x21, #0x178]
0xfffffe00095f33dc: ldr      w9, [x9, #0x84]
0xfffffe00095f33e0: stp      x9, x20, [sp, #0x10]
0xfffffe00095f33e4: adrp     x9, #0xfffffe00074c4000
0xfffffe00095f33e8: add      x9, x9, #0xcd
0xfffffe00095f33ec: stp      x8, x9, [sp]
0xfffffe00095f33f0: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f33f4: add      x0, x0, #0xec0
0xfffffe00095f33f8: adrp     x1, #0xfffffe0008163000
0xfffffe00095f33fc: ldr      x1, [x1, #0xbf8]
0xfffffe00095f3400: adrp     x3, #0xfffffe00074f4000
0xfffffe00095f3404: add      x3, x3, #0x999
0xfffffe00095f3408: mov      w2, #0x10
0xfffffe00095f340c: bl       #0xfffffe000964c288
0xfffffe00095f3410: b        #0xfffffe00095f3528
0xfffffe00095f3414: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f3418: add      x8, x8, #0x69c
0xfffffe00095f341c: stp      x22, x4, [sp, #0x20]
0xfffffe00095f3420: mov      x9, x20
0xfffffe00095f3424: stp      x9, x23, [sp, #0x10]
0xfffffe00095f3428: adrp     x9, #0xfffffe00074c4000
0xfffffe00095f342c: add      x9, x9, #0xcd
0xfffffe00095f3430: stp      x8, x9, [sp]
0xfffffe00095f3434: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f3438: add      x0, x0, #0xec0
0xfffffe00095f343c: adrp     x1, #0xfffffe0008163000
0xfffffe00095f3440: ldr      x1, [x1, #0xbf8]
0xfffffe00095f3444: adrp     x3, #0xfffffe00074f4000
0xfffffe00095f3448: add      x3, x3, #0x9f5
0xfffffe00095f344c: mov      w2, #0
0xfffffe00095f3450: bl       #0xfffffe000964c288
0xfffffe00095f3454: add      x9, x21, #0x5c0
0xfffffe00095f3458: mov      w10, w20
0xfffffe00095f345c: add      x8, x9, x10, lsl #6
0xfffffe00095f3460: ldr      x9, [x8, #8]
0xfffffe00095f3464: cmp      x22, x9
0xfffffe00095f3468: b.ls     #0xfffffe00095f3474
0xfffffe00095f346c: add      w19, w19, #9
0xfffffe00095f3470: b        #0xfffffe00095f3528
0xfffffe00095f3474: and      x9, x23, #0xffffff
0xfffffe00095f3478: bfi      x9, x22, #0x18, #0x18
0xfffffe00095f347c: str      x9, [sp, #0x38]
0xfffffe00095f3480: ldr      x0, [x8, #0x28]
0xfffffe00095f3484: ldr      x16, [x0]
0xfffffe00095f3488: mov      x17, x0
0xfffffe00095f348c: movk     x17, #0xcda1, lsl #48
0xfffffe00095f3490: autda    x16, x17
0xfffffe00095f3494: mov      x17, #0x1e8
0xfffffe00095f3498: add      x16, x16, x17
0xfffffe00095f349c: ldr      x8, [x16]
0xfffffe00095f34a0: add      x1, sp, #0x38
0xfffffe00095f34a4: mov      x2, #0
0xfffffe00095f34a8: mov      w3, #1
0xfffffe00095f34ac: movk     x16, #0xab08, lsl #48
0xfffffe00095f34b0: blraa    x8, x16
0xfffffe00095f34b4: mov      x19, x0
0xfffffe00095f34b8: cbz      w0, #0xfffffe00095f3528
0xfffffe00095f34bc: ldr      w8, [x21, #0x180]
0xfffffe00095f34c0: cmp      w8, #3
0xfffffe00095f34c4: b.hi     #0xfffffe00095f34f0
0xfffffe00095f34c8: lsl      x8, x8, #3
0xfffffe00095f34cc: adrp     x9, #0xfffffe000814d000
0xfffffe00095f34d0: add      x9, x9, #0x1a0
0xfffffe00095f34d4: cmp      x8, w8, sxtw
0xfffffe00095f34d8: add      x10, x9, w8, sxtw
0xfffffe00095f34dc: add      x16, x9, x8
0xfffffe00095f34e0: movk     x16, #0x2bad, lsl #48
0xfffffe00095f34e4: csel     x10, x10, x16, eq
0xfffffe00095f34e8: ldr      x8, [x10]
0xfffffe00095f34ec: b        #0xfffffe00095f34f8
0xfffffe00095f34f0: adrp     x8, #0xfffffe00074b8000
0xfffffe00095f34f4: add      x8, x8, #0x69c
0xfffffe00095f34f8: adrp     x9, #0xfffffe00074c4000
0xfffffe00095f34fc: add      x9, x9, #0xcd
0xfffffe00095f3500: stp      x9, x20, [sp, #8]
0xfffffe00095f3504: str      x8, [sp]
0xfffffe00095f3508: adrp     x0, #0xfffffe00074b7000
0xfffffe00095f350c: add      x0, x0, #0xec0
0xfffffe00095f3510: adrp     x1, #0xfffffe0008163000
0xfffffe00095f3514: ldr      x1, [x1, #0xbf8]
0xfffffe00095f3518: adrp     x3, #0xfffffe00074f4000
0xfffffe00095f351c: add      x3, x3, #0xa52
0xfffffe00095f3520: mov      w2, #0x10
0xfffffe00095f3524: bl       #0xfffffe000964c288
0xfffffe00095f3528: mov      x0, x19
0xfffffe00095f352c: ldp      x29, x30, [sp, #0x70]
0xfffffe00095f3530: ldp      x20, x19, [sp, #0x60]
0xfffffe00095f3534: ldp      x22, x21, [sp, #0x50]
0xfffffe00095f3538: ldp      x24, x23, [sp, #0x40]
0xfffffe00095f353c: add      sp, sp, #0x80
0xfffffe00095f3540: retab    