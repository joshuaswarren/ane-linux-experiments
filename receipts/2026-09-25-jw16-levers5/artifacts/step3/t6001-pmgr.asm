; AppleT6000PMGR (jw16 22G74 stub cache, sha256 35695639 decompressed)
; setPerfState dispatch seen: domains 1-5 (jump table), 13 explicit; T8103's domain 8 NOT accepted here
; writeReg32 special-case: map==2 && reg==0xc00 && die==0 -> branch 0xfffffe0009b56368; general path RMW orr w3,w0,#0x20000000 (BIT29)

===== setPerfState va=0xfffffe0009b52f1c file=0x2b4ef1c
fffffe0009b52f1c  pacibsp 
fffffe0009b52f20  sub sp, sp, #0x70
fffffe0009b52f24  stp x28, x27, [sp, #0x10]
fffffe0009b52f28  stp x26, x25, [sp, #0x20]
fffffe0009b52f2c  stp x24, x23, [sp, #0x30]
fffffe0009b52f30  stp x22, x21, [sp, #0x40]
fffffe0009b52f34  stp x20, x19, [sp, #0x50]
fffffe0009b52f38  stp x29, x30, [sp, #0x60]
fffffe0009b52f3c  add x29, sp, #0x60
fffffe0009b52f40  mov x19, x4
fffffe0009b52f44  mov x22, x3
fffffe0009b52f48  mov x23, x2
fffffe0009b52f4c  mov x20, x1
fffffe0009b52f50  mov x21, x0
fffffe0009b52f54  ldr x16, [x0]
fffffe0009b52f58  mov x17, x0
fffffe0009b52f5c  movk x17, #0xcda1, lsl #48
fffffe0009b52f60  autda x16, x17
fffffe0009b52f64  mov x17, #0xab8
fffffe0009b52f68  add x16, x16, x17
fffffe0009b52f6c  ldr x8, [x16]
fffffe0009b52f70  mov x9, x16
fffffe0009b52f74  mov x17, x9
fffffe0009b52f78  movk x17, #0x27ca, lsl #48
fffffe0009b52f7c  blraa x8, x17
fffffe0009b52f80  mov x25, x0
fffffe0009b52f84  sub w16, w20, #1
fffffe0009b52f88  cmp w16, #4
fffffe0009b52f8c  b.hi #0xfffffe0009b52fb8
fffffe0009b52f90  cmp x16, #4
fffffe0009b52f94  csel x16, x16, xzr, ls
fffffe0009b52f98  adrp x17, #0xfffffe0009b53000
fffffe0009b52f9c  add x17, x17, #0x678
fffffe0009b52fa0  ldrsw x16, [x17, x16, lsl #2]
fffffe0009b52fa4  adr x17, #0xfffffe0009b52fa4
fffffe0009b52fa8  add x16, x17, x16
fffffe0009b52fac  br x16
fffffe0009b52fb0  bti j
fffffe0009b52fb4  bl #0xfffffe0009b70510
fffffe0009b52fb8  cmp w20, #0xd
fffffe0009b52fbc  b.ne #0xfffffe0009b53668
fffffe0009b52fc0  bti j
fffffe0009b52fc4  add x8, x21, #0x36, lsl #12
fffffe0009b52fc8  add x28, x8, #0x968
fffffe0009b52fcc  mov x0, x21
fffffe0009b52fd0  mov x1, x20
fffffe0009b52fd4  mov w2, #0
fffffe0009b52fd8  bl #0xfffffe0009b5368c
fffffe0009b52fdc  ldr x16, [x21]
fffffe0009b52fe0  mov x17, x21
fffffe0009b52fe4  movk x17, #0xcda1, lsl #48
fffffe0009b52fe8  autda x16, x17
fffffe0009b52fec  mov x17, #0xd80
fffffe0009b52ff0  add x16, x16, x17
fffffe0009b52ff4  ldr x8, [x16]
fffffe0009b52ff8  mov x9, x16
fffffe0009b52ffc  mov x0, x21
fffffe0009b53000  mov x1, x20
fffffe0009b53004  mov x17, x9
fffffe0009b53008  movk x17, #0xaae3, lsl #48
fffffe0009b5300c  blraa x8, x17
fffffe0009b53010  mov x26, x0
fffffe0009b53014  ldrb w8, [x28, #0x33]
fffffe0009b53018  cbz w8, #0xfffffe0009b532a8
fffffe0009b5301c  ldr x27, [x28, #0x4f8]
fffffe0009b53020  mov w0, #0
fffffe0009b53024  bl #0xfffffe000856fd5c
fffffe0009b53028  mov x24, x0
fffffe0009b5302c  mov x0, x27
fffffe0009b53030  bl #0xfffffe000856a980
fffffe0009b53034  add x8, x21, w26, uxtw
fffffe0009b53038  mov w9, #0x6968
fffffe0009b5303c  movk w9, #3, lsl #16
fffffe0009b53040  strb w23, [x8, x9]
fffffe0009b53044  ldrb w2, [x28]
fffffe0009b53048  mov w27, #1
fffffe0009b5304c  mov x0, x21
fffffe0009b53050  mov w1, #2
fffffe0009b53054  mov w3, #1
fffffe0009b53058  mov w4, #0
fffffe0009b5305c  bl #0xfffffe000985e998
fffffe0009b53060  ldr w8, [x28, #0x4f4]
fffffe0009b53064  cmp w0, w8
fffffe0009b53068  b.hs #0xfffffe0009b530b8
fffffe0009b5306c  ldrb w2, [x28, #1]
fffffe0009b53070  mov w27, #1
fffffe0009b53074  mov x0, x21
fffffe0009b53078  mov w1, #5
fffffe0009b5307c  mov w3, #1
fffffe0009b53080  mov w4, #0
fffffe0009b53084  bl #0xfffffe000985e998
fffffe0009b53088  ldr w8, [x28, #0x4f4]
fffffe0009b5308c  cmp w0, w8
fffffe0009b53090  b.hs #0xfffffe0009b530b8
fffffe0009b53094  ldrb w2, [x28, #2]
fffffe0009b53098  mov x0, x21
fffffe0009b5309c  mov w1, #0xd
fffffe0009b530a0  mov w3, #1
fffffe0009b530a4  mov w4, #0
fffffe0009b530a8  bl #0xfffffe000985e998
fffffe0009b530ac  ldr w8, [x28, #0x4f4]
fffffe0009b530b0  cmp w0, w8
fffffe0009b530b4  cset w27, hs
fffffe0009b530b8  ldrb w8, [x28, #0x4f0]
fffffe0009b530bc  cmp w8, w27
fffffe0009b530c0  b.eq #0xfffffe0009b532c0
fffffe0009b530c4  ldr x16, [x21]
fffffe0009b530c8  mov x17, x21
fffffe0009b530cc  movk x17, #0xcda1, lsl #48
fffffe0009b530d0  autda x16, x17
fffffe0009b530d4  mov x17, #0xd98
fffffe0009b530d8  add x16, x16, x17
fffffe0009b530dc  ldr x8, [x16]
fffffe0009b530e0  mov x9, x16
fffffe0009b530e4  mov x0, x21
fffffe0009b530e8  mov w1, #0
fffffe0009b530ec  mov w2, #0xe20000
fffffe0009b530f0  mov w3, #0
fffffe0009b530f4  mov x17, x9
fffffe0009b530f8  movk x17, #0x61a4, lsl #48
fffffe0009b530fc  blraa x8, x17
fffffe0009b53100  orr x3, x0, #0x20000000
fffffe0009b53104  ldr x16, [x21]
fffffe0009b53108  mov x17, x21
fffffe0009b5310c  movk x17, #0xcda1, lsl #48
fffffe0009b53110  autda x16, x17
fffffe0009b53114  mov x17, x16
fffffe0009b53118  xpacd x17
fffffe0009b5311c  cmp x16, x17
fffffe0009b53120  b.eq #0xfffffe0009b53128
fffffe0009b53124  brk #0xc472
fffffe0009b53128  add x8, x16, #0xda8
fffffe0009b5312c  ldr x9, [x16, #0xda8]
fffffe0009b53130  mov x0, x21
fffffe0009b53134  mov w1, #0
fffffe0009b53138  mov w2, #0xe20000
fffffe0009b5313c  mov w4, #0
fffffe0009b53140  mov x17, x8
fffffe0009b53144  movk x17, #0x1843, lsl #48
fffffe0009b53148  blraa x9, x17
fffffe0009b5314c  ldr x16, [x21]
fffffe0009b53150  mov x17, x21
fffffe0009b53154  movk x17, #0xcda1, lsl #48
fffffe0009b53158  autda x16, x17
fffffe0009b5315c  mov x17, x16
fffffe0009b53160  xpacd x17
fffffe0009b53164  cmp x16, x17
fffffe0009b53168  b.eq #0xfffffe0009b53170
fffffe0009b5316c  brk #0xc472
fffffe0009b53170  add x8, x16, #0xd98
fffffe0009b53174  ldr x9, [x16, #0xd98]
fffffe0009b53178  mov x0, x21
fffffe0009b5317c  mov w1, #1
fffffe0009b53180  mov w2, #0xe20000
fffffe0009b53184  mov w3, #0
fffffe0009b53188  mov x17, x8
fffffe0009b5318c  movk x17, #0x61a4, lsl #48
fffffe0009b53190  blraa x9, x17
fffffe0009b53194  orr x3, x0, #0x20000000
fffffe0009b53198  ldr x16, [x21]
fffffe0009b5319c  mov x17, x21
fffffe0009b531a0  movk x17, #0xcda1, lsl #48
fffffe0009b531a4  autda x16, x17
fffffe0009b531a8  mov x17, x16
fffffe0009b531ac  xpacd x17
fffffe0009b531b0  cmp x16, x17
fffffe0009b531b4  b.eq #0xfffffe0009b531bc
fffffe0009b531b8  brk #0xc472
fffffe0009b531bc  add x8, x16, #0xda8
fffffe0009b531c0  ldr x9, [x16, #0xda8]
fffffe0009b531c4  mov x0, x21
fffffe0009b531c8  mov w1, #1
fffffe0009b531cc  mov w2, #0xe20000
fffffe0009b531d0  mov w4, #0
fffffe0009b531d4  mov x17, x8
fffffe0009b531d8  movk x17, #0x1843, lsl #48
fffffe0009b531dc  blraa x9, x17
fffffe0009b531e0  ldr x16, [x21]
fffffe0009b531e4  mov x17, x21
fffffe0009b531e8  movk x17, #0xcda1, lsl #48
fffffe0009b531ec  autda x16, x17
fffffe0009b531f0  mov x17, x16
fffffe0009b531f4  xpacd x17
fffffe0009b531f8  cmp x16, x17
fffffe0009b531fc  b.eq #0xfffffe0009b53204
fffffe0009b53200  brk #0xc472
fffffe0009b53204  add x8, x16, #0xd98
fffffe0009b53208  ldr x9, [x16, #0xd98]
fffffe0009b5320c  mov x0, x21
fffffe0009b53210  mov w1, #2
fffffe0009b53214  mov w2, #0xe20000
fffffe0009b53218  mov w3, #0
fffffe0009b5321c  mov x17, x8
fffffe0009b53220  movk x17, #0x61a4, lsl #48
fffffe0009b53224  blraa x9, x17
fffffe0009b53228  orr x3, x0, #0x20000000
fffffe0009b5322c  ldr x16, [x21]
fffffe0009b53230  mov x17, x21
fffffe0009b53234  movk x17, #0xcda1, lsl #48
fffffe0009b53238  autda x16, x17
fffffe0009b5323c  mov x17, x16
fffffe0009b53240  xpacd x17
fffffe0009b53244  cmp x16, x17
fffffe0009b53248  b.eq #0xfffffe0009b53250
fffffe0009b5324c  brk #0xc472
fffffe0009b53250  add x8, x16, #0xda8
fffffe0009b53254  ldr x9, [x16, #0xda8]
fffffe0009b53258  mov x0, x21
fffffe0009b5325c  mov w1, #2
fffffe0009b53260  mov w2, #0xe20000
fffffe0009b53264  mov w4, #0
fffffe0009b53268  mov x17, x8
fffffe0009b5326c  movk x17, #0x1843, lsl #48
fffffe0009b53270  blraa x9, x17
fffffe0009b53274  mov x0, x21
fffffe0009b53278  mov w1, #2
fffffe0009b5327c  mov w2, #0
fffffe0009b53280  bl #0xfffffe0009b5368c
fffffe0009b53284  mov x0, x21
fffffe0009b53288  mov w1, #5
fffffe0009b5328c  mov w2, #0
fffffe0009b53290  bl #0xfffffe0009b5368c
fffffe0009b53294  mov x0, x21
fffffe0009b53298  mov w1, #0xd
fffffe0009b5329c  mov w2, #0
fffffe0009b532a0  bl #0xfffffe0009b5368c
fffffe0009b532a4  b #0xfffffe0009b532c0
fffffe0009b532a8  mov w27, #0
fffffe0009b532ac  mov w24, #0
fffffe0009b532b0  add x8, x21, w26, uxtw
fffffe0009b532b4  mov w9, #0x6968
fffffe0009b532b8  movk w9, #3, lsl #16
fffffe0009b532bc  strb w23, [x8, x9]
fffffe0009b532c0  ldr w8, [x28, #0x1c]
fffffe0009b532c4  cmp w8, #2
fffffe0009b532c8  b.ne #0xfffffe0009b53344
fffffe0009b532cc  ldr x16, [x21]
fffffe0009b532d0  mov x17, x21
fffffe0009b532d4  movk x17, #0xcda1, lsl #48
fffffe0009b532d8  autda x16, x17
fffffe0009b532dc  mov x17, #0xd40
fffffe0009b532e0  add x16, x16, x17
fffffe0009b532e4  ldr x8, [x16]
fffffe0009b532e8  mov x9, x16
fffffe0009b532ec  mov x0, x21
fffffe0009b532f0  mov x1, x26
fffffe0009b532f4  mov x17, x9
fffffe0009b532f8  movk x17, #0xddff, lsl #48
fffffe0009b532fc  blraa x8, x17
fffffe0009b53300  mov x1, x0
fffffe0009b53304  ldr x16, [x21]
fffffe0009b53308  mov x17, x21
fffffe0009b5330c  movk x17, #0xcda1, lsl #48
fffffe0009b53310  autda x16, x17
fffffe0009b53314  mov x17, x16
fffffe0009b53318  xpacd x17
fffffe0009b5331c  cmp x16, x17
fffffe0009b53320  b.eq #0xfffffe0009b53328
fffffe0009b53324  brk #0xc472
fffffe0009b53328  add x8, x16, #0xa38
fffffe0009b5332c  ldr x9, [x16, #0xa38]
fffffe0009b53330  mov x0, x21
fffffe0009b53334  mov w2, #0
fffffe0009b53338  mov x17, x8
fffffe0009b5333c  movk x17, #0x5f1f, lsl #48
fffffe0009b53340  blraa x9, x17
fffffe0009b53344  ldr x16, [x21]
fffffe0009b53348  mov x17, x21
fffffe0009b5334c  movk x17, #0xcda1, lsl #48
fffffe0009b53350  autda x16, x17
fffffe0009b53354  mov x17, #0xd98
fffffe0009b53358  add x16, x16, x17
fffffe0009b5335c  ldr x8, [x16]
fffffe0009b53360  mov x9, x16
fffffe0009b53364  mov x0, x21
fffffe0009b53368  mov x1, x26
fffffe0009b5336c  mov w2, #0x20
fffffe0009b53370  movk w2, #0xe2, lsl #16
fffffe0009b53374  mov x3, x19
fffffe0009b53378  mov x17, x9
fffffe0009b5337c  movk x17, #0x61a4, lsl #48
fffffe0009b53380  blraa x8, x17
fffffe0009b53384  and x8, x0, #0xfffffffffffffff0
fffffe0009b53388  mov w9, #0x2000000
fffffe0009b5338c  bfxil w9, w25, #0, #4
fffffe0009b53390  orr x3, x8, x9
fffffe0009b53394  ldr x16, [x21]
fffffe0009b53398  mov x17, x21
fffffe0009b5339c  movk x17, #0xcda1, lsl #48
fffffe0009b533a0  autda x16, x17
fffffe0009b533a4  mov x17, x16
fffffe0009b533a8  xpacd x17
fffffe0009b533ac  cmp x16, x17
fffffe0009b533b0  b.eq #0xfffffe0009b533b8
fffffe0009b533b4  brk #0xc472
fffffe0009b533b8  add x8, x16, #0xda8
fffffe0009b533bc  ldr x9, [x16, #0xda8]
fffffe0009b533c0  mov x0, x21
fffffe0009b533c4  mov x1, x26
fffffe0009b533c8  mov w2, #0x20
fffffe0009b533cc  movk w2, #0xe2, lsl #16
fffffe0009b533d0  mov x4, x19
fffffe0009b533d4  mov x17, x8
fffffe0009b533d8  movk x17, #0x1843, lsl #48
fffffe0009b533dc  blraa x9, x17
fffffe0009b533e0  ldrb w8, [x28, #0x33]
fffffe0009b533e4  cbz w8, #0xfffffe0009b535d0
fffffe0009b533e8  ldrb w8, [x28, #0x4f0]
fffffe0009b533ec  cmp w8, w27
fffffe0009b533f0  b.eq #0xfffffe0009b535c0
fffffe0009b533f4  ldr x16, [x21]
fffffe0009b533f8  mov x17, x21
fffffe0009b533fc  movk x17, #0xcda1, lsl #48
fffffe0009b53400  autda x16, x17
fffffe0009b53404  mov x17, #0xd98
fffffe0009b53408  add x16, x16, x17
fffffe0009b5340c  ldr x8, [x16]
fffffe0009b53410  mov x9, x16
fffffe0009b53414  mov x0, x21
fffffe0009b53418  mov w1, #0
fffffe0009b5341c  mov w2, #0xe20000
fffffe0009b53420  mov w3, #0
fffffe0009b53424  mov x17, x9
fffffe0009b53428  movk x17, #0x61a4, lsl #48
fffffe0009b5342c  blraa x8, x17
fffffe0009b53430  and x8, x0, #0xffffffffdfffffff
fffffe0009b53434  cmp w27, #0
fffffe0009b53438  mov w9, #0x20000000
fffffe0009b5343c  csel x25, x9, xzr, ne
fffffe0009b53440  orr x3, x8, x25
fffffe0009b53444  ldr x16, [x21]
fffffe0009b53448  mov x17, x21
fffffe0009b5344c  movk x17, #0xcda1, lsl #48
fffffe0009b53450  autda x16, x17
fffffe0009b53454  mov x17, x16
fffffe0009b53458  xpacd x17
fffffe0009b5345c  cmp x16, x17
fffffe0009b53460  b.eq #0xfffffe0009b53468
fffffe0009b53464  brk #0xc472
fffffe0009b53468  add x8, x16, #0xda8
fffffe0009b5346c  ldr x9, [x16, #0xda8]
fffffe0009b53470  mov x0, x21
fffffe0009b53474  mov w1, #0
fffffe0009b53478  mov w2, #0xe20000
fffffe0009b5347c  mov w4, #0
fffffe0009b53480  mov x17, x8
fffffe0009b53484  movk x17, #0x1843, lsl #48
fffffe0009b53488  blraa x9, x17
fffffe0009b5348c  ldr x16, [x21]
fffffe0009b53490  mov x17, x21
fffffe0009b53494  movk x17, #0xcda1, lsl #48
fffffe0009b53498  autda x16, x17
fffffe0009b5349c  mov x17, x16
fffffe0009b534a0  xpacd x17
fffffe0009b534a4  cmp x16, x17
fffffe0009b534a8  b.eq #0xfffffe0009b534b0
fffffe0009b534ac  brk #0xc472
fffffe0009b534b0  add x8, x16, #0xd98
fffffe0009b534b4  ldr x9, [x16, #0xd98]
fffffe0009b534b8  mov x0, x21
fffffe0009b534bc  mov w1, #1
fffffe0009b534c0  mov w2, #0xe20000
fffffe0009b534c4  mov w3, #0
fffffe0009b534c8  mov x17, x8
fffffe0009b534cc  movk x17, #0x61a4, lsl #48
fffffe0009b534d0  blraa x9, x17
fffffe0009b534d4  and x8, x0, #0xffffffffdfffffff
fffffe0009b534d8  orr x3, x8, x25
fffffe0009b534dc  ldr x16, [x21]
fffffe0009b534e0  mov x17, x21
fffffe0009b534e4  movk x17, #0xcda1, lsl #48
fffffe0009b534e8  autda x16, x17
fffffe0009b534ec  mov x17, x16
fffffe0009b534f0  xpacd x17
fffffe0009b534f4  cmp x16, x17
fffffe0009b534f8  b.eq #0xfffffe0009b53500
fffffe0009b534fc  brk #0xc472
fffffe0009b53500  add x8, x16, #0xda8
fffffe0009b53504  ldr x9, [x16, #0xda8]
fffffe0009b53508  mov x0, x21
fffffe0009b5350c  mov w1, #1
fffffe0009b53510  mov w2, #0xe20000
fffffe0009b53514  mov w4, #0
fffffe0009b53518  mov x17, x8
fffffe0009b5351c  movk x17, #0x1843, lsl #48
fffffe0009b53520  blraa x9, x17
fffffe0009b53524  ldr x16, [x21]
fffffe0009b53528  mov x17, x21
fffffe0009b5352c  movk x17, #0xcda1, lsl #48
fffffe0009b53530  autda x16, x17
fffffe0009b53534  mov x17, x16
fffffe0009b53538  xpacd x17
fffffe0009b5353c  cmp x16, x17
fffffe0009b53540  b.eq #0xfffffe0009b53548
fffffe0009b53544  brk #0xc472
fffffe0009b53548  add x8, x16, #0xd98
fffffe0009b5354c  ldr x9, [x16, #0xd98]
fffffe0009b53550  mov x0, x21
fffffe0009b53554  mov w1, #2
fffffe0009b53558  mov w2, #0xe20000
fffffe0009b5355c  mov w3, #0
fffffe0009b53560  mov x17, x8
fffffe0009b53564  movk x17, #0x61a4, lsl #48
fffffe0009b53568  blraa x9, x17
fffffe0009b5356c  and x8, x0, #0xffffffffdfffffff
fffffe0009b53570  orr x3, x8, x25
fffffe0009b53574  ldr x16, [x21]
fffffe0009b53578  mov x17, x21
fffffe0009b5357c  movk x17, #0xcda1, lsl #48
fffffe0009b53580  autda x16, x17
fffffe0009b53584  mov x17, x16
fffffe0009b53588  xpacd x17
fffffe0009b5358c  cmp x16, x17
fffffe0009b53590  b.eq #0xfffffe0009b53598
fffffe0009b53594  brk #0xc472
fffffe0009b53598  add x8, x16, #0xda8
fffffe0009b5359c  ldr x9, [x16, #0xda8]
fffffe0009b535a0  mov x0, x21
fffffe0009b535a4  mov w1, #2
fffffe0009b535a8  mov w2, #0xe20000
fffffe0009b535ac  mov w4, #0
fffffe0009b535b0  mov x17, x8
fffffe0009b535b4  movk x17, #0x1843, lsl #48
fffffe0009b535b8  blraa x9, x17
fffffe0009b535bc  strb w27, [x28, #0x4f0]
fffffe0009b535c0  ldr x0, [x28, #0x4f8]
fffffe0009b535c4  bl #0xfffffe000856a9a0
fffffe0009b535c8  mov x0, x24
fffffe0009b535cc  bl #0xfffffe000856fd5c
fffffe0009b535d0  and w8, w20, #0xfffffff7
fffffe0009b535d4  cmp w8, #5
fffffe0009b535d8  b.ne #0xfffffe0009b53634
fffffe0009b535dc  ldrb w8, [x28, #0x18]
fffffe0009b535e0  cmp w8, #0xff
fffffe0009b535e4  b.eq #0xfffffe0009b53634
fffffe0009b535e8  mov w9, #5
fffffe0009b535ec  cmp w8, w23
fffffe0009b535f0  cset w8, ls
fffffe0009b535f4  stp w8, w9, [sp, #8]
fffffe0009b535f8  ldr x0, [x28, #8]
fffffe0009b535fc  ldr x16, [x0]
fffffe0009b53600  mov x17, x0
fffffe0009b53604  movk x17, #0xcda1, lsl #48
fffffe0009b53608  autda x16, x17
fffffe0009b5360c  mov x17, #0x140
fffffe0009b53610  add x16, x16, x17
fffffe0009b53614  ldr x8, [x16]
fffffe0009b53618  mov x9, x16
fffffe0009b5361c  add x1, sp, #0xc
fffffe0009b53620  add x2, sp, #8
fffffe0009b53624  mov x3, #0
fffffe0009b53628  mov x17, x9
fffffe0009b5362c  movk x17, #0x7547, lsl #48
fffffe0009b53630  blraa x8, x17
fffffe0009b53634  cbz w22, #0xfffffe0009b53648
fffffe0009b53638  mov x0, x21
fffffe0009b5363c  mov x1, x20
fffffe0009b53640  mov x2, x19
fffffe0009b53644  bl #0xfffffe0009b5368c
fffffe0009b53648  ldp x29, x30, [sp, #0x60]
fffffe0009b5364c  ldp x20, x19, [sp, #0x50]
fffffe0009b53650  ldp x22, x21, [sp, #0x40]
fffffe0009b53654  ldp x24, x23, [sp, #0x30]
fffffe0009b53658  ldp x26, x25, [sp, #0x20]
fffffe0009b5365c  ldp x28, x27, [sp, #0x10]
fffffe0009b53660  add sp, sp, #0x70
fffffe0009b53664  retab 
fffffe0009b53668  bti j
fffffe0009b5366c  bl #0xfffffe0009b704cc
fffffe0009b53670  bti j
fffffe0009b53674  bl #0xfffffe0009b70554
fffffe0009b53678  udf #0xc
fffffe0009b5367c  udf #0x1c
fffffe0009b53680  udf #0x6cc
fffffe0009b53684  udf #0x6c4
fffffe0009b53688  udf #0x1c
fffffe0009b5368c  pacibsp 
fffffe0009b53690  stp x22, x21, [sp, #-0x30]!
fffffe0009b53694  stp x20, x19, [sp, #0x10]
fffffe0009b53698  stp x29, x30, [sp, #0x20]
fffffe0009b5369c  add x29, sp, #0x20
fffffe0009b536a0  cmp w1, #0xd
fffffe0009b536a4  b.hi #0xfffffe0009b537a0
fffffe0009b536a8  mov x21, x1
fffffe0009b536ac  mov w8, #1
fffffe0009b536b0  lsl w8, w8, w1
fffffe0009b536b4  mov w9, #0x2024
fffffe0009b536b8  tst w8, w9
fffffe0009b536bc  b.eq #0xfffffe0009b537a0
fffffe0009b536c0  mov x20, x2
fffffe0009b536c4  mov x19, x0
fffffe0009b536c8  mov w22, #0
fffffe0009b536cc  ldr x16, [x19]
fffffe0009b536d0  mov x17, x19
fffffe0009b536d4  movk x17, #0xcda1, lsl #48
fffffe0009b536d8  autda x16, x17
fffffe0009b536dc  mov x17, #0xd80
fffffe0009b536e0  add x16, x16, x17
fffffe0009b536e4  ldr x8, [x16]
fffffe0009b536e8  mov x9, x16
fffffe0009b536ec  mov x0, x19
fffffe0009b536f0  mov x1, x21
fffffe0009b536f4  mov x17, x9
fffffe0009b536f8  movk x17, #0xaae3, lsl #48
fffffe0009b536fc  blraa x8, x17
fffffe0009b53700  mov x1, x0
fffffe0009b53704  ldr x16, [x19]
fffffe0009b53708  mov x17, x19
fffffe0009b5370c  movk x17, #0xcda1, lsl #48
fffffe0009b53710  autda x16, x17
fffffe0009b53714  mov x17, x16
fffffe0009b53718  xpacd x17
fffffe0009b5371c  cmp x16, x17
fffffe0009b53720  b.eq #0xfffffe0009b53728
fffffe0009b53724  brk #0xc472
fffffe0009b53728  add x8, x16, #0xd98
fffffe0009b5372c  ldr x9, [x16, #0xd98]
fffffe0009b53730  mov x0, x19
fffffe0009b53734  mov w2, #0x20
fffffe0009b53738  movk w2, #0xe2, lsl #16
fffffe0009b5373c  mov x3, x20
fffffe0009b53740  mov x17, x8
fffffe0009b53744  movk x17, #0x61a4, lsl #48
fffffe0009b53748  blraa x9, x17
fffffe0009b5374c  tbnz w0, #0x1f, #0xfffffe0009b536cc
fffffe0009b53750  add w22, w22, #1
fffffe0009b53754  cmp w22, #2
fffffe0009b53758  b.ne #0xfffffe0009b536cc
fffffe0009b5375c  mov w8, #0x696b
fffffe0009b53760  movk w8, #3, lsl #16
fffffe0009b53764  ldrb w8, [x19, x8]
fffffe0009b53768  cbz w8, #0xfffffe0009b53790
fffffe0009b5376c  mov x0, x19
fffffe0009b53770  ldp x29, x30, [sp, #0x20]
fffffe0009b53774  ldp x20, x19, [sp, #0x10]
fffffe0009b53778  ldp x22, x21, [sp], #0x30
fffffe0009b5377c  autibsp 
fffffe0009b53780  eor x16, x30, x30, lsl #1
fffffe0009b53784  tbz x16, #0x3e, #0xfffffe0009b5378c
fffffe0009b53788  brk #0xc471
fffffe0009b5378c  b #0xfffffe0009b51e54
fffffe0009b53790  ldp x29, x30, [sp, #0x20]
fffffe0009b53794  ldp x20, x19, [sp, #0x10]
fffffe0009b53798  ldp x22, x21, [sp], #0x30
fffffe0009b5379c  retab 
fffffe0009b537a0  bl #0xfffffe0009b70598
fffffe0009b537a4  pacibsp 
fffffe0009b537a8  stp x20, x19, [sp, #-0x20]!
fffffe0009b537ac  stp x29, x30, [sp, #0x10]
fffffe0009b537b0  add x29, sp, #0x10
fffffe0009b537b4  mov x3, x2
fffffe0009b537b8  mov x19, x0
fffffe0009b537bc  sub w16, w1, #1
fffffe0009b537c0  cmp w16, #4
fffffe0009b537c4  b.hi #0xfffffe0009b53830
fffffe0009b537c8  cmp x16, #4
fffffe0009b537cc  csel x16, x16, xzr, ls
fffffe0009b537d0  adrp x17, #0xfffffe0009b53000
fffffe0009b537d4  add x17, x17, #0x8e8
fffffe0009b537d8  ldrsw x16, [x17, x16, lsl #2]
fffffe0009b537dc  adr x17, #0xfffffe0009b537dc
fffffe0009b537e0  add x16, x17, x16
fffffe0009b537e4  br x16
fffffe0009b537e8  bti j
fffffe0009b537ec  ldr x16, [x19]
fffffe0009b537f0  mov x17, x19
fffffe0009b537f4  movk x17, #0xcda1, lsl #48
fffffe0009b537f8  autda x16, x17
fffffe0009b537fc  mov x17, #0xd98
fffffe0009b53800  add x16, x16, x17
fffffe0009b53804  ldr x8, [x16]
fffffe0009b53808  mov x9, x16
fffffe0009b5380c  mov x0, x19
fffffe0009b53810  mov w1, #0
fffffe0009b53814  mov w2, #0x20
fffffe0009b53818  movk w2, #0xe2, lsl #16
fffffe0009b5381c  mov x17, x9
fffffe0009b53820  movk x17, #0x61a4, lsl #48
fffffe0009b53824  blraa x8, x17
fffffe0009b53828  ubfx x0, x0, #0x1f, #1
fffffe0009b5382c  b #0xfffffe0009b538d4
fffffe0009b53830  cmp w1, #0xd
fffffe0009b53834  b.ne #0xfffffe0009b538e0
fffffe0009b53838  ldr x16, [x19]
fffffe0009b5383c  mov x17, x19
fffffe0009b53840  movk x17, #0xcda1, lsl #48
fffffe0009b53844  autda x16, x17
fffffe0009b53848  mov x17, #0xd98
fffffe0009b5384c  add x16, x16, x17
fffffe0009b53850  ldr x8, [x16]
fffffe0009b53854  mov x9, x16
fffffe0009b53858  mov x0, x19
fffffe0009b5385c  mov w1, #2
fffffe0009b53860  b #0xfffffe0009b538bc
fffffe0009b53864  bti j
fffffe0009b53868  mov x0, x19
fffffe0009b5386c  mov w1, #0x800
fffffe0009b53870  bl #0xfffffe0009860194
fffffe0009b53874  bti j
fffffe0009b53878  mov x0, x19
fffffe0009b5387c  mov w1, #0x50000
fffffe0009b53880  mov w2, #0
fffffe0009b53884  bl #0xfffffe0009860040
fffffe0009b53888  lsr w0, w0, #0x1f
fffffe0009b5388c  b #0xfffffe0009b538d4
fffffe0009b53890  bti j
fffffe0009b53894  ldr x16, [x19]
fffffe0009b53898  mov x17, x19
fffffe0009b5389c  movk x17, #0xcda1, lsl #48
fffffe0009b538a0  autda x16, x17
fffffe0009b538a4  mov x17, #0xd98
fffffe0009b538a8  add x16, x16, x17
fffffe0009b538ac  ldr x8, [x16]
fffffe0009b538b0  mov x9, x16
fffffe0009b538b4  mov x0, x19
fffffe0009b538b8  mov w1, #1
fffffe0009b538bc  mov w2, #0x20
fffffe0009b538c0  movk w2, #0xe2, lsl #16
fffffe0009b538c4  mov x17, x9
fffffe0009b538c8  movk x17, #0x61a4, lsl #48
fffffe0009b538cc  blraa x8, x17
fffffe0009b538d0  ubfx x0, x0, #0x1f, #1
fffffe0009b538d4  ldp x29, x30, [sp, #0x10]
fffffe0009b538d8  ldp x20, x19, [sp], #0x20
fffffe0009b538dc  retab 
fffffe0009b538e0  bti j
fffffe0009b538e4  bl #0xfffffe0009b705dc
fffffe0009b538e8  udf #0x98
fffffe0009b538ec  udf #0xc
fffffe0009b538f0  udf #0x88
fffffe0009b538f4  udf #0x104
fffffe0009b538f8  udf #0xb4
fffffe0009b538fc  bti c
fffffe0009b53900  cmp w1, #0xd
fffffe0009b53904  b.hi #0xfffffe0009b53924
fffffe0009b53908  mov w8, #1
fffffe0009b5390c  lsl w8, w8, w1
fffffe0009b53910  mov w9, #0x202e
fffffe0009b53914  tst w8, w9
fffffe0009b53918  b.eq #0xfffffe0009b53924
fffffe0009b5391c  add w0, w2, #1
fffffe0009b53920  ret 
fffffe0009b53924  pacibsp 
fffffe0009b53928  stp x29, x30, [sp, #-0x10]!
fffffe0009b5392c  mov x29, sp
fffffe0009b53930  bl #0xfffffe0009b70620
fffffe0009b53934  pacibsp 
fffffe0009b53938  stp x22, x21, [sp, #-0x30]!
fffffe0009b5393c  stp x20, x19, [sp, #0x10]
fffffe0009b53940  stp x29, x30, [sp, #0x20]
fffffe0009b53944  add x29, sp, #0x20
fffffe0009b53948  mov w8, #0x69a8
fffffe0009b5394c  movk w8, #3, lsl #16
fffffe0009b53950  ldr w8, [x0, x8]
fffffe0009b53954  add w8, w8, w8, lsl #1
fffffe0009b53958  cmp w8, w1
fffffe0009b5395c  b.ls #0xfffffe0009b53a24
fffffe0009b53960  mov x21, x2
fffffe0009b53964  mov x19, x1
fffffe0009b53968  mov x20, x0
fffffe0009b5396c  ldr x16, [x0]
fffffe0009b53970  mov x17, x0
fffffe0009b53974  movk x17, #0xcda1, lsl #48
fffffe0009b53978  autda x16, x17
fffffe0009b5397c  mov x17, #0xd98
fffffe0009b53980  add x16, x16, x17
fffffe0009b53984  ldr x8, [x16]
fffffe0009b53988  mov x9, x16
fffffe0009b5398c  mov w2, #0x660
fffffe0009b53990  movk w2, #0xe2, lsl #16
fffffe0009b53994  mov w3, #0
fffffe0009b53998  mov x17, x9
fffffe0009b5399c  movk x17, #0x61a4, lsl #48
fffffe0009b539a0  blraa x8, x17
fffffe0009b539a4  mov x8, #-0x16
fffffe0009b539a8  and x8, x0, x8
fffffe0009b539ac  cmp w21, #0
fffffe0009b539b0  mov w9, #0x15
fffffe0009b539b4  csel x9, x9, xzr, ne
fffffe0009b539b8  orr x3, x8, x9
fffffe0009b539bc  ldr x16, [x20]
fffffe0009b539c0  mov x17, x20
fffffe0009b539c4  movk x17, #0xcda1, lsl #48
fffffe0009b539c8  autda x16, x17
fffffe0009b539cc  mov x17, x16
fffffe0009b539d0  xpacd x17
fffffe0009b539d4  cmp x16, x17
fffffe0009b539d8  b.eq #0xfffffe0009b539e0
fffffe0009b539dc  brk #0xc472
fffffe0009b539e0  add x5, x16, #0xda8
fffffe0009b539e4  ldr x16, [x16, #0xda8]
fffffe0009b539e8  mov x0, x20
fffffe0009b539ec  mov x1, x19
fffffe0009b539f0  mov w2, #0x660
fffffe0009b539f4  movk w2, #0xe2, lsl #16
fffffe0009b539f8  mov w4, #0
fffffe0009b539fc  ldp x29, x30, [sp, #0x20]
fffffe0009b53a00  ldp x20, x19, [sp, #0x10]
fffffe0009b53a04  ldp x22, x21, [sp], #0x30
fffffe0009b53a08  autibsp 
fffffe0009b53a0c  eor x17, x30, x30, lsl #1
fffffe0009b53a10  tbz x17, #0x3e, #0xfffffe0009b53a18
fffffe0009b53a14  brk #0xc471
fffffe0009b53a18  mov x17, x5
fffffe0009b53a1c  movk x17, #0x1843, lsl #48
fffffe0009b53a20  braa x16, x17
fffffe0009b53a24  bl #0xfffffe0009b70664
fffffe0009b53a28  pacibsp 
fffffe0009b53a2c  stp x29, x30, [sp, #-0x10]!
fffffe0009b53a30  mov x29, sp
fffffe0009b53a34  cmp w1, #0x15
fffffe0009b53a38  b.hi #0xfffffe0009b53d6c
fffffe0009b53a3c  mov w16, w1
fffffe0009b53a40  cmp x16, #0x15
fffffe0009b53a44  csel x16, x16, xzr, ls
fffffe0009b53a48  adrp x17, #0xfffffe0009b53000
fffffe0009b53a4c  add x17, x17, #0xda4
fffffe0009b53a50  ldrsw x16, [x17, x16, lsl #2]
fffffe0009b53a54  adr x17, #0xfffffe0009b53a54
fffffe0009b53a58  add x16, x17, x16
fffffe0009b53a5c  br x16
fffffe0009b53a60  bti j
fffffe0009b53a64  cmp w2, #0x10
fffffe0009b53a68  b.hs #0xfffffe0009b53d74
fffffe0009b53a6c  mov w8, #0x400
fffffe0009b53a70  movk w8, #0xe2, lsl #16
fffffe0009b53a74  orr w9, w8, #0x80
fffffe0009b53a78  cmp w3, #0
fffffe0009b53a7c  csel w8, w9, w8, ne
fffffe0009b53a80  add w2, w8, w2, lsl #3
fffffe0009b53a84  b #0xfffffe0009b53d20
fffffe0009b53a88  bti j
fffffe0009b53a8c  cmp w2, #0x10
fffffe0009b53a90  b.hs #0xfffffe0009b53d78
fffffe0009b53a94  mov w8, #0x400
fffffe0009b53a98  movk w8, #0xe2, lsl #16
fffffe0009b53a9c  orr w9, w8, #0x80
fffffe0009b53aa0  cmp w3, #0
fffffe0009b53aa4  csel w8, w9, w8, ne
fffffe0009b53aa8  add w2, w8, w2, lsl #3
fffffe0009b53aac  b #0xfffffe0009b53b78
fffffe0009b53ab0  bti j
fffffe0009b53ab4  cmp w2, #0x10
fffffe0009b53ab8  b.hs #0xfffffe0009b53d7c
fffffe0009b53abc  mov w8, #0x400
fffffe0009b53ac0  movk w8, #0xe2, lsl #16
fffffe0009b53ac4  orr w9, w8, #0x80
fffffe0009b53ac8  cmp w3, #0
fffffe0009b53acc  csel w8, w9, w8, ne
fffffe0009b53ad0  add w2, w8, w2, lsl #3
fffffe0009b53ad4  b #0xfffffe0009b53bcc
fffffe0009b53ad8  bti j
fffffe0009b53adc  cmp w2, #0x10
fffffe0009b53ae0  b.hs #0xfffffe0009b53d80
fffffe0009b53ae4  mov w8, #0x400
fffffe0009b53ae8  movk w8, #0xe2, lsl #16
fffffe0009b53aec  orr w9, w8, #0x80
fffffe0009b53af0  cmp w3, #0
fffffe0009b53af4  csel w8, w9, w8, ne
fffffe0009b53af8  add w2, w8, w2, lsl #3
fffffe0009b53afc  b #0xfffffe0009b53c20
fffffe0009b53b00  bti j
fffffe0009b53b04  cmp w2, #0x10
fffffe0009b53b08  b.hs #0xfffffe0009b53d84
fffffe0009b53b0c  mov w8, #0x400
fffffe0009b53b10  movk w8, #0xe2, lsl #16
fffffe0009b53b14  orr w9, w8, #0x80
fffffe0009b53b18  cmp w3, #0
fffffe0009b53b1c  csel w8, w9, w8, ne
fffffe0009b53b20  add w2, w8, w2, lsl #3
fffffe0009b53b24  b #0xfffffe0009b53c74
fffffe0009b53b28  bti j
fffffe0009b53b2c  cmp w2, #0x10
fffffe0009b53b30  b.hs #0xfffffe0009b53d88
fffffe0009b53b34  mov w8, #0x400
fffffe0009b53b38  movk w8, #0xe2, lsl #16
fffffe0009b53b3c  orr w9, w8, #0x80
fffffe0009b53b40  cmp w3, #0
fffffe0009b53b44  csel w8, w9, w8, ne
fffffe0009b53b48  add w2, w8, w2, lsl #3
fffffe0009b53b4c  b #0xfffffe0009b53cc8
fffffe0009b53b50  bti j
fffffe0009b53b54  cmp w2, #0x1b
fffffe0009b53b58  b.hs #0xfffffe0009b53d8c
fffffe0009b53b5c  mov w8, #0x180
fffffe0009b53b60  mov w9, #0x188
fffffe0009b53b64  cmp w3, #0
fffffe0009b53b68  csel w8, w9, w8, ne
fffffe0009b53b6c  add w8, w8, w2, lsl #3
fffffe0009b53b70  add w8, w8, #0xe20, lsl #12
fffffe0009b53b74  add w2, w8, #0x400
fffffe0009b53b78  ldr x16, [x0]
fffffe0009b53b7c  mov x17, x0
fffffe0009b53b80  movk x17, #0xcda1, lsl #48
fffffe0009b53b84  autda x16, x17
fffffe0009b53b88  mov x17, #0xd98
fffffe0009b53b8c  add x16, x16, x17
fffffe0009b53b90  ldr x8, [x16]
fffffe0009b53b94  mov x4, x16
fffffe0009b53b98  mov x16, x8
fffffe0009b53b9c  mov w1, #1
fffffe0009b53ba0  b #0xfffffe0009b53d48
fffffe0009b53ba4  bti j
fffffe0009b53ba8  cmp w2, #0x1b
fffffe0009b53bac  b.hs #0xfffffe0009b53d90
fffffe0009b53bb0  mov w8, #0x180
fffffe0009b53bb4  mov w9, #0x188
fffffe0009b53bb8  cmp w3, #0
fffffe0009b53bbc  csel w8, w9, w8, ne
fffffe0009b53bc0  add w8, w8, w2, lsl #3
fffffe0009b53bc4  add w8, w8, #0xe20, lsl #12
fffffe0009b53bc8  add w2, w8, #0x400
fffffe0009b53bcc  ldr x16, [x0]
fffffe0009b53bd0  mov x17, x0
fffffe0009b53bd4  movk x17, #0xcda1, lsl #48
fffffe0009b53bd8  autda x16, x17
fffffe0009b53bdc  mov x17, #0xd98
fffffe0009b53be0  add x16, x16, x17
fffffe0009b53be4  ldr x8, [x16]
fffffe0009b53be8  mov x4, x16
fffffe0009b53bec  mov x16, x8
fffffe0009b53bf0  mov w1, #2
fffffe0009b53bf4  b #0xfffffe0009b53d48
fffffe0009b53bf8  bti j
fffffe0009b53bfc  cmp w2, #0x1b
fffffe0009b53c00  b.hs #0xfffffe0009b53d94
fffffe0009b53c04  mov w8, #0x180
fffffe0009b53c08  mov w9, #0x188
fffffe0009b53c0c  cmp w3, #0
fffffe0009b53c10  csel w8, w9, w8, ne
fffffe0009b53c14  add w8, w8, w2, lsl #3
fffffe0009b53c18  add w8, w8, #0xe20, lsl #12
fffffe0009b53c1c  add w2, w8, #0x400
fffffe0009b53c20  ldr x16, [x0]
fffffe0009b53c24  mov x17, x0
fffffe0009b53c28  movk x17, #0xcda1, lsl #48
fffffe0009b53c2c  autda x16, x17
fffffe0009b53c30  mov x17, #0xd98
fffffe0009b53c34  add x16, x16, x17
fffffe0009b53c38  ldr x8, [x16]
fffffe0009b53c3c  mov x4, x16
fffffe0009b53c40  mov x16, x8
fffffe0009b53c44  mov w1, #0
fffffe0009b53c48  b #0xfffffe0009b53cf0
fffffe0009b53c4c  bti j
fffffe0009b53c50  cmp w2, #0x1b
fffffe0009b53c54  b.hs #0xfffffe0009b53d98
fffffe0009b53c58  mov w8, #0x180
fffffe0009b53c5c  mov w9, #0x188
fffffe0009b53c60  cmp w3, #0
fffffe0009b53c64  csel w8, w9, w8, ne
fffffe0009b53c68  add w8, w8, w2, lsl #3
fffffe0009b53c6c  add w8, w8, #0xe20, lsl #12
fffffe0009b53c70  add w2, w8, #0x400
fffffe0009b53c74  ldr x16, [x0]
fffffe0009b53c78  mov x17, x0
fffffe0009b53c7c  movk x17, #0xcda1, lsl #48
fffffe0009b53c80  autda x16, x17
fffffe0009b53c84  mov x17, #0xd98
fffffe0009b53c88  add x16, x16, x17
fffffe0009b53c8c  ldr x8, [x16]
fffffe0009b53c90  mov x4, x16
fffffe0009b53c94  mov x16, x8
fffffe0009b53c98  mov w1, #1
fffffe0009b53c9c  b #0xfffffe0009b53cf0
fffffe0009b53ca0  bti j
fffffe0009b53ca4  cmp w2, #0x1b
fffffe0009b53ca8  b.hs #0xfffffe0009b53d9c
fffffe0009b53cac  mov w8, #0x180
fffffe0009b53cb0  mov w9, #0x188
fffffe0009b53cb4  cmp w3, #0
fffffe0009b53cb8  csel w8, w9, w8, ne
fffffe0009b53cbc  add w8, w8, w2, lsl #3
fffffe0009b53cc0  add w8, w8, #0xe20, lsl #12
fffffe0009b53cc4  add w2, w8, #0x400
fffffe0009b53cc8  ldr x16, [x0]
fffffe0009b53ccc  mov x17, x0
fffffe0009b53cd0  movk x17, #0xcda1, lsl #48
fffffe0009b53cd4  autda x16, x17
fffffe0009b53cd8  mov x17, #0xd98
fffffe0009b53cdc  add x16, x16, x17
fffffe0009b53ce0  ldr x8, [x16]
fffffe0009b53ce4  mov x4, x16
fffffe0009b53ce8  mov x16, x8
fffffe0009b53cec  mov w1, #2
fffffe0009b53cf0  mov w3, #1
fffffe0009b53cf4  b #0xfffffe0009b53d4c
fffffe0009b53cf8  bti j
fffffe0009b53cfc  cmp w2, #0x1b
fffffe0009b53d00  b.hs #0xfffffe0009b53da0
fffffe0009b53d04  mov w8, #0x180
fffffe0009b53d08  mov w9, #0x188
fffffe0009b53d0c  cmp w3, #0
fffffe0009b53d10  csel w8, w9, w8, ne
fffffe0009b53d14  add w8, w8, w2, lsl #3
fffffe0009b53d18  add w8, w8, #0xe20, lsl #12
fffffe0009b53d1c  add w2, w8, #0x400
fffffe0009b53d20  ldr x16, [x0]
fffffe0009b53d24  mov x17, x0
fffffe0009b53d28  movk x17, #0xcda1, lsl #48

===== writeReg32 va=0xfffffe0009b54ee8 file=0x2b50ee8
fffffe0009b54ee8  pacibsp 
fffffe0009b54eec  sub sp, sp, #0xa0
fffffe0009b54ef0  stp x28, x27, [sp, #0x40]
fffffe0009b54ef4  stp x26, x25, [sp, #0x50]
fffffe0009b54ef8  stp x24, x23, [sp, #0x60]
fffffe0009b54efc  stp x22, x21, [sp, #0x70]
fffffe0009b54f00  stp x20, x19, [sp, #0x80]
fffffe0009b54f04  stp x29, x30, [sp, #0x90]
fffffe0009b54f08  add x29, sp, #0x90
fffffe0009b54f0c  mov x19, x4
fffffe0009b54f10  str w3, [sp, #0x34]
fffffe0009b54f14  mov x20, x2
fffffe0009b54f18  mov x23, x1
fffffe0009b54f1c  mov x21, x0
fffffe0009b54f20  cmp w1, #2
fffffe0009b54f24  b.ne #0xfffffe0009b54f34
fffffe0009b54f28  cmp w20, #0xc00
fffffe0009b54f2c  b.ne #0xfffffe0009b54f34
fffffe0009b54f30  cbnz w19, #0xfffffe0009b56368
fffffe0009b54f34  mov x28, #0
fffffe0009b54f38  mov w25, #0
fffffe0009b54f3c  mov w9, #0
fffffe0009b54f40  add x8, x21, #0x36, lsl #12
fffffe0009b54f44  add x8, x8, #0x9a8
fffffe0009b54f48  str x8, [sp, #0x10]
fffffe0009b54f4c  ldr w8, [sp, #0x34]
fffffe0009b54f50  and w24, w8, #0xf
fffffe0009b54f54  adrp x8, #0xfffffe0007e41000
fffffe0009b54f58  ldr x8, [x8, #0xc80]
fffffe0009b54f5c  ldr x26, [x8, #0xd30]
fffffe0009b54f60  adrp x27, #0xfffffe00074fa000
fffffe0009b54f64  add x27, x27, #0x834
fffffe0009b54f68  str x26, [sp, #0x38]
fffffe0009b54f6c  str w20, [sp, #0x2c]
fffffe0009b54f70  str w24, [sp, #0x1c]
fffffe0009b54f74  ldur w8, [x27, #-8]
fffffe0009b54f78  cmp w8, w20
fffffe0009b54f7c  b.ne #0xfffffe0009b55208
fffffe0009b54f80  ldur w8, [x27, #-0xc]
fffffe0009b54f84  cmp w8, w23
fffffe0009b54f88  b.ne #0xfffffe0009b55208
fffffe0009b54f8c  ldr x16, [x21]
fffffe0009b54f90  mov x17, x21
fffffe0009b54f94  movk x17, #0xcda1, lsl #48
fffffe0009b54f98  autda x16, x17
fffffe0009b54f9c  mov x17, #0xd18
fffffe0009b54fa0  add x16, x16, x17
fffffe0009b54fa4  ldr x8, [x16]
fffffe0009b54fa8  mov x9, x16
fffffe0009b54fac  mov x0, x21
fffffe0009b54fb0  mov x1, x23
fffffe0009b54fb4  mov x2, x20
fffffe0009b54fb8  mov x3, x19
fffffe0009b54fbc  mov x17, x9
fffffe0009b54fc0  movk x17, #0x73ce, lsl #48
fffffe0009b54fc4  blraa x8, x17
fffffe0009b54fc8  and w25, w0, #0xf
fffffe0009b54fcc  cbnz w24, #0xfffffe0009b55204
fffffe0009b54fd0  cbz w25, #0xfffffe0009b55204
fffffe0009b54fd4  str w25, [sp, #0x30]
fffffe0009b54fd8  mov w8, #0x15d
fffffe0009b54fdc  lsr x8, x8, x28
fffffe0009b54fe0  str x8, [sp, #0x20]
fffffe0009b54fe4  tbnz w8, #0, #0xfffffe0009b55058
fffffe0009b54fe8  ldr w24, [x27]
fffffe0009b54fec  ldr x16, [x21]
fffffe0009b54ff0  mov x17, x21
fffffe0009b54ff4  movk x17, #0xcda1, lsl #48
fffffe0009b54ff8  autda x16, x17
fffffe0009b54ffc  mov x17, #0xd18
fffffe0009b55000  add x16, x16, x17
fffffe0009b55004  ldr x8, [x16]
fffffe0009b55008  mov x9, x16
fffffe0009b5500c  mov x0, x21
fffffe0009b55010  mov x1, x23
fffffe0009b55014  mov x2, x24
fffffe0009b55018  mov x3, x19
fffffe0009b5501c  mov x17, x9
fffffe0009b55020  movk x17, #0x73ce, lsl #48
fffffe0009b55024  blraa x8, x17
fffffe0009b55028  orr w3, w0, #0x20000000
fffffe0009b5502c  adrp x8, #0xfffffe0007e41000
fffffe0009b55030  ldr x8, [x8, #0xc80]
fffffe0009b55034  add x8, x8, #0xd30
fffffe0009b55038  mov x0, x21
fffffe0009b5503c  mov x1, x23
fffffe0009b55040  mov x2, x24
fffffe0009b55044  mov x4, x19
fffffe0009b55048  ldr x9, [sp, #0x38]
fffffe0009b5504c  mov x17, x8
fffffe0009b55050  movk x17, #0xfd0b, lsl #48
fffffe0009b55054  blraa x9, x17
fffffe0009b55058  ldur w24, [x27, #-4]
fffffe0009b5505c  ldr x16, [x21]
fffffe0009b55060  mov x17, x21
fffffe0009b55064  movk x17, #0xcda1, lsl #48
fffffe0009b55068  autda x16, x17
fffffe0009b5506c  mov x17, #0xd18
fffffe0009b55070  add x16, x16, x17
fffffe0009b55074  ldr x8, [x16]
fffffe0009b55078  mov x9, x16
fffffe0009b5507c  mov x0, x21
fffffe0009b55080  mov x1, x23
fffffe0009b55084  mov x2, x24
fffffe0009b55088  mov x3, x19
fffffe0009b5508c  mov x17, x9
fffffe0009b55090  movk x17, #0x73ce, lsl #48
fffffe0009b55094  blraa x8, x17
fffffe0009b55098  mov x25, x0
fffffe0009b5509c  orr w3, w0, #0x20000000
fffffe0009b550a0  adrp x8, #0xfffffe0007e41000
fffffe0009b550a4  ldr x8, [x8, #0xc80]
fffffe0009b550a8  add x20, x8, #0xd30
fffffe0009b550ac  mov x0, x21
fffffe0009b550b0  mov x1, x23
fffffe0009b550b4  mov x2, x24
fffffe0009b550b8  mov x4, x19
fffffe0009b550bc  ldr x26, [sp, #0x38]
fffffe0009b550c0  mov x17, x20
fffffe0009b550c4  movk x17, #0xfd0b, lsl #48
fffffe0009b550c8  blraa x26, x17
fffffe0009b550cc  mov x0, x21
fffffe0009b550d0  mov x1, x23
fffffe0009b550d4  mov x22, x19
fffffe0009b550d8  ldr w19, [sp, #0x2c]
fffffe0009b550dc  mov x2, x19
fffffe0009b550e0  ldr w3, [sp, #0x34]
fffffe0009b550e4  mov x4, x22
fffffe0009b550e8  mov x17, x20
fffffe0009b550ec  movk x17, #0xfd0b, lsl #48
fffffe0009b550f0  blraa x26, x17
fffffe0009b550f4  ldr x16, [x21]
fffffe0009b550f8  mov x17, x21
fffffe0009b550fc  movk x17, #0xcda1, lsl #48
fffffe0009b55100  autda x16, x17
fffffe0009b55104  mov x17, x16
fffffe0009b55108  xpacd x17
fffffe0009b5510c  cmp x16, x17
fffffe0009b55110  b.eq #0xfffffe0009b55118
fffffe0009b55114  brk #0xc472
fffffe0009b55118  add x8, x16, #0xd28
fffffe0009b5511c  ldr x9, [x16, #0xd28]
fffffe0009b55120  mov x0, x21
fffffe0009b55124  mov x1, x23
fffffe0009b55128  mov x2, x19
fffffe0009b5512c  mov w3, #0x800
fffffe0009b55130  mov w4, #0
fffffe0009b55134  mov w5, #0xee00
fffffe0009b55138  movk w5, #2, lsl #16
fffffe0009b5513c  mov x6, x22
fffffe0009b55140  mov x17, x8
fffffe0009b55144  movk x17, #0x7f, lsl #48
fffffe0009b55148  blraa x9, x17
fffffe0009b5514c  ldr x16, [x21]
fffffe0009b55150  mov x17, x21
fffffe0009b55154  movk x17, #0xcda1, lsl #48
fffffe0009b55158  autda x16, x17
fffffe0009b5515c  mov x17, x16
fffffe0009b55160  xpacd x17
fffffe0009b55164  cmp x16, x17
fffffe0009b55168  b.eq #0xfffffe0009b55170
fffffe0009b5516c  brk #0xc472
fffffe0009b55170  add x8, x16, #0xd28
fffffe0009b55174  ldr x9, [x16, #0xd28]
fffffe0009b55178  mov x0, x21
fffffe0009b5517c  mov x1, x23
fffffe0009b55180  mov x2, x19
fffffe0009b55184  mov x19, x22
fffffe0009b55188  mov w3, #0xf0
fffffe0009b5518c  mov w4, #0
fffffe0009b55190  mov w5, #0xee00
fffffe0009b55194  movk w5, #2, lsl #16
fffffe0009b55198  mov x6, x22
fffffe0009b5519c  mov x17, x8
fffffe0009b551a0  movk x17, #0x7f, lsl #48
fffffe0009b551a4  blraa x9, x17
fffffe0009b551a8  and w25, w25, #0xdfffffff
fffffe0009b551ac  mov x0, x21
fffffe0009b551b0  mov x1, x23
fffffe0009b551b4  mov x2, x24
fffffe0009b551b8  mov x3, x25
fffffe0009b551bc  mov x4, x22
fffffe0009b551c0  mov x17, x20
fffffe0009b551c4  movk x17, #0xfd0b, lsl #48
fffffe0009b551c8  blraa x26, x17
fffffe0009b551cc  ldr x8, [sp, #0x20]
fffffe0009b551d0  tbnz w8, #0, #0xfffffe0009b551f4
fffffe0009b551d4  ldr w2, [x27]
fffffe0009b551d8  mov x0, x21
fffffe0009b551dc  mov x1, x23
fffffe0009b551e0  mov x3, x25
fffffe0009b551e4  mov x4, x19
fffffe0009b551e8  mov x17, x20
fffffe0009b551ec  movk x17, #0xfd0b, lsl #48
fffffe0009b551f0  blraa x26, x17
fffffe0009b551f4  mov w9, #0
fffffe0009b551f8  ldp w20, w25, [sp, #0x2c]
fffffe0009b551fc  ldr w24, [sp, #0x1c]
fffffe0009b55200  b #0xfffffe0009b55208
fffffe0009b55204  mov x9, x24
fffffe0009b55208  add x28, x28, #1
fffffe0009b5520c  add x27, x27, #0x10
fffffe0009b55210  cmp x28, #0xa
fffffe0009b55214  b.ne #0xfffffe0009b54f74
fffffe0009b55218  mov w8, #0x8014
fffffe0009b5521c  movk w8, #1, lsl #16
fffffe0009b55220  cmp w23, #0
fffffe0009b55224  ccmp w20, w8, #0, eq
fffffe0009b55228  cset w27, eq
fffffe0009b5522c  b.ne #0xfffffe0009b55404
fffffe0009b55230  mov x22, x27
fffffe0009b55234  ldr x16, [x21]
fffffe0009b55238  mov x17, x21
fffffe0009b5523c  movk x17, #0xcda1, lsl #48
fffffe0009b55240  autda x16, x17
fffffe0009b55244  mov x17, #0xd18
fffffe0009b55248  add x16, x16, x17
fffffe0009b5524c  ldr x8, [x16]
fffffe0009b55250  mov x9, x16
fffffe0009b55254  mov x0, x21
fffffe0009b55258  mov w1, #0
fffffe0009b5525c  mov w2, #0x8014
fffffe0009b55260  movk w2, #1, lsl #16
fffffe0009b55264  mov x3, x19
fffffe0009b55268  mov x17, x9
fffffe0009b5526c  movk x17, #0x73ce, lsl #48
fffffe0009b55270  blraa x8, x17
fffffe0009b55274  and w25, w0, #0xf
fffffe0009b55278  ldr x27, [sp, #0x10]
fffffe0009b5527c  ldr w8, [x27]
fffffe0009b55280  cmp w8, #2
fffffe0009b55284  adrp x28, #0xfffffe0007e41000
fffffe0009b55288  ldr x28, [x28, #0xc80]
fffffe0009b5528c  b.lo #0xfffffe0009b5585c
fffffe0009b55290  cmp w24, #0xf
fffffe0009b55294  b.ne #0xfffffe0009b5537c
fffffe0009b55298  cmp w25, #0xf
fffffe0009b5529c  b.eq #0xfffffe0009b5537c
fffffe0009b552a0  str w23, [sp, #4]
fffffe0009b552a4  add x23, x28, #0xd30
fffffe0009b552a8  mov x0, x21
fffffe0009b552ac  mov w1, #0
fffffe0009b552b0  mov w2, #0x8014
fffffe0009b552b4  movk w2, #1, lsl #16
fffffe0009b552b8  ldr w3, [sp, #0x34]
fffffe0009b552bc  mov x4, x19
fffffe0009b552c0  mov x17, x23
fffffe0009b552c4  movk x17, #0xfd0b, lsl #48
fffffe0009b552c8  blraa x26, x17
fffffe0009b552cc  eor w24, w19, #1
fffffe0009b552d0  mov x0, x21
fffffe0009b552d4  mov w1, #0
fffffe0009b552d8  mov w2, #0x8014
fffffe0009b552dc  movk w2, #1, lsl #16
fffffe0009b552e0  mov w3, #0xf
fffffe0009b552e4  mov x4, x24
fffffe0009b552e8  mov x17, x23
fffffe0009b552ec  movk x17, #0xfd0b, lsl #48
fffffe0009b552f0  blraa x26, x17
fffffe0009b552f4  add x23, x28, #0xd38
fffffe0009b552f8  mov x20, x25
fffffe0009b552fc  ldr x25, [x28, #0xd38]
fffffe0009b55300  mov x0, x21
fffffe0009b55304  mov w1, #0
fffffe0009b55308  mov w2, #0x8014
fffffe0009b5530c  movk w2, #1, lsl #16
fffffe0009b55310  mov w3, #0x10
fffffe0009b55314  mov w4, #0
fffffe0009b55318  mov w5, #0xee00
fffffe0009b5531c  movk w5, #2, lsl #16
fffffe0009b55320  mov x6, x19
fffffe0009b55324  mov x17, x23
fffffe0009b55328  movk x17, #0x7f, lsl #48
fffffe0009b5532c  blraa x25, x17
fffffe0009b55330  mov x0, x21
fffffe0009b55334  mov w1, #0
fffffe0009b55338  mov w2, #0x8014
fffffe0009b5533c  movk w2, #1, lsl #16
fffffe0009b55340  mov w3, #0x10
fffffe0009b55344  mov w4, #0
fffffe0009b55348  mov w5, #0xee00
fffffe0009b5534c  movk w5, #2, lsl #16
fffffe0009b55350  mov x6, x24
fffffe0009b55354  ldr w24, [sp, #0x1c]
fffffe0009b55358  mov x17, x23
fffffe0009b5535c  movk x17, #0x7f, lsl #48
fffffe0009b55360  blraa x25, x17
fffffe0009b55364  mov x25, x20
fffffe0009b55368  ldr w23, [sp, #4]
fffffe0009b5536c  ldr w20, [sp, #0x2c]
fffffe0009b55370  ldr w8, [x27]
fffffe0009b55374  cmp w8, #2
fffffe0009b55378  b.lo #0xfffffe0009b55858
fffffe0009b5537c  cbnz w24, #0xfffffe0009b5585c
fffffe0009b55380  cbz w25, #0xfffffe0009b5585c
fffffe0009b55384  ldr w8, [x27, #0x18]
fffffe0009b55388  cbnz w8, #0xfffffe0009b56368
fffffe0009b5538c  ldr x8, [sp, #0x10]
fffffe0009b55390  ldr w8, [x8, #0x1c]
fffffe0009b55394  cbnz w8, #0xfffffe0009b56368
fffffe0009b55398  add x8, x28, #0xd30
fffffe0009b5539c  eor w24, w19, #1
fffffe0009b553a0  mov x0, x21
fffffe0009b553a4  mov w1, #0
fffffe0009b553a8  mov w2, #0x8014
fffffe0009b553ac  movk w2, #1, lsl #16
fffffe0009b553b0  mov w3, #0
fffffe0009b553b4  mov x4, x24
fffffe0009b553b8  mov x17, x8
fffffe0009b553bc  movk x17, #0xfd0b, lsl #48
fffffe0009b553c0  blraa x26, x17
fffffe0009b553c4  add x8, x28, #0xd38
fffffe0009b553c8  ldr x9, [x28, #0xd38]
fffffe0009b553cc  mov x0, x21
fffffe0009b553d0  mov w1, #0
fffffe0009b553d4  mov w2, #0x8014
fffffe0009b553d8  movk w2, #1, lsl #16
fffffe0009b553dc  mov w3, #0x10
fffffe0009b553e0  mov w4, #0
fffffe0009b553e4  mov w5, #0xee00
fffffe0009b553e8  movk w5, #2, lsl #16
fffffe0009b553ec  mov x6, x24
fffffe0009b553f0  mov x17, x8
fffffe0009b553f4  movk x17, #0x7f, lsl #48
fffffe0009b553f8  blraa x9, x17
fffffe0009b553fc  mov w24, #0
fffffe0009b55400  b #0xfffffe0009b5585c
fffffe0009b55404  cmp w23, #0
fffffe0009b55408  mov w8, #0x1e8
fffffe0009b5540c  ccmp w20, w8, #0, eq
fffffe0009b55410  cset w22, eq
fffffe0009b55414  adrp x28, #0xfffffe0007e41000
fffffe0009b55418  ldr x28, [x28, #0xc80]
fffffe0009b5541c  b.ne #0xfffffe0009b55574
fffffe0009b55420  ldr w8, [sp, #0x34]
fffffe0009b55424  and w8, w8, #0xfffffbff
fffffe0009b55428  str w8, [sp, #0x34]
fffffe0009b5542c  ldr x25, [x28, #0xd28]
fffffe0009b55430  add x8, x28, #0xd28
fffffe0009b55434  mov x0, x21
fffffe0009b55438  mov w1, #0
fffffe0009b5543c  mov w2, #0x1e8
fffffe0009b55440  mov x3, x19
fffffe0009b55444  mov x17, x8
fffffe0009b55448  movk x17, #0x73ce, lsl #48
fffffe0009b5544c  blraa x25, x17
fffffe0009b55450  and w8, w0, #0xf
fffffe0009b55454  str w8, [sp, #0x30]
fffffe0009b55458  ldr x8, [sp, #0x10]
fffffe0009b5545c  ldr w8, [x8]
fffffe0009b55460  cmp w24, #0xf
fffffe0009b55464  b.ne #0xfffffe0009b55484
fffffe0009b55468  cmp w8, #2
fffffe0009b5546c  b.lo #0xfffffe0009b55484
fffffe0009b55470  add x9, x21, w19, uxtw #2
fffffe0009b55474  mov w10, #0x69c0
fffffe0009b55478  movk w10, #3, lsl #16
fffffe0009b5547c  mov w11, #0xf
fffffe0009b55480  str w11, [x9, x10]
fffffe0009b55484  cmp w8, #2
fffffe0009b55488  b.lo #0xfffffe0009b55760
fffffe0009b5548c  cmp w24, #0xf
fffffe0009b55490  b.ne #0xfffffe0009b55760
fffffe0009b55494  ldr w9, [sp, #0x30]
fffffe0009b55498  cmp w9, #0xf
fffffe0009b5549c  b.eq #0xfffffe0009b55760
fffffe0009b554a0  eor w24, w19, #1
fffffe0009b554a4  add x8, x28, #0xd28
fffffe0009b554a8  mov x0, x21
fffffe0009b554ac  mov w1, #0
fffffe0009b554b0  mov w2, #0x1e8
fffffe0009b554b4  mov x3, x24
fffffe0009b554b8  mov x17, x8
fffffe0009b554bc  movk x17, #0x73ce, lsl #48
fffffe0009b554c0  blraa x25, x17
fffffe0009b554c4  mov x25, x0
fffffe0009b554c8  orr w3, w0, #0xf
fffffe0009b554cc  add x22, x28, #0xd30
fffffe0009b554d0  mov x0, x21
fffffe0009b554d4  mov w1, #0
fffffe0009b554d8  mov w2, #0x1e8
fffffe0009b554dc  mov x4, x24
fffffe0009b554e0  mov x17, x22
fffffe0009b554e4  movk x17, #0xfd0b, lsl #48
fffffe0009b554e8  blraa x26, x17
fffffe0009b554ec  ldr x16, [x21]
fffffe0009b554f0  mov x17, x21
fffffe0009b554f4  movk x17, #0xcda1, lsl #48
fffffe0009b554f8  autda x16, x17
fffffe0009b554fc  mov x17, x16
fffffe0009b55500  xpacd x17
fffffe0009b55504  cmp x16, x17
fffffe0009b55508  b.eq #0xfffffe0009b55510
fffffe0009b5550c  brk #0xc472
fffffe0009b55510  add x8, x16, #0xd28
fffffe0009b55514  ldr x9, [x16, #0xd28]
fffffe0009b55518  mov x0, x21
fffffe0009b5551c  mov w1, #0
fffffe0009b55520  mov w2, #0x1e8
fffffe0009b55524  mov w3, #0xf0
fffffe0009b55528  mov w4, #0
fffffe0009b5552c  mov w5, #0xee00
fffffe0009b55530  movk w5, #2, lsl #16
fffffe0009b55534  mov x6, x24
fffffe0009b55538  mov x17, x8
fffffe0009b5553c  movk x17, #0x7f, lsl #48
fffffe0009b55540  blraa x9, x17
fffffe0009b55544  mov w8, #0xf
fffffe0009b55548  movk w8, #0x1004, lsl #16
fffffe0009b5554c  orr w3, w25, w8
fffffe0009b55550  mov x0, x21
fffffe0009b55554  mov w1, #0
fffffe0009b55558  mov w2, #0x1e8
fffffe0009b5555c  mov x4, x24
fffffe0009b55560  mov x17, x22
fffffe0009b55564  movk x17, #0xfd0b, lsl #48
fffffe0009b55568  blraa x26, x17
fffffe0009b5556c  mov w24, #0xf
fffffe0009b55570  b #0xfffffe0009b55790
fffffe0009b55574  str w22, [sp, #0x20]
fffffe0009b55578  cmp w23, #0
fffffe0009b5557c  mov w8, #0x120
fffffe0009b55580  ccmp w20, w8, #0, eq
fffffe0009b55584  cset w22, eq
fffffe0009b55588  b.ne #0xfffffe0009b556ac
fffffe0009b5558c  ldr x16, [x21]
fffffe0009b55590  mov x17, x21
fffffe0009b55594  movk x17, #0xcda1, lsl #48
fffffe0009b55598  autda x16, x17
fffffe0009b5559c  mov x17, #0xd18
fffffe0009b555a0  add x16, x16, x17
fffffe0009b555a4  ldr x8, [x16]
fffffe0009b555a8  mov x9, x16
fffffe0009b555ac  mov x0, x21
fffffe0009b555b0  mov w1, #0
fffffe0009b555b4  mov w2, #0x120
fffffe0009b555b8  mov x3, x19
fffffe0009b555bc  mov x17, x9
fffffe0009b555c0  movk x17, #0x73ce, lsl #48
fffffe0009b555c4  blraa x8, x17
fffffe0009b555c8  and w25, w0, #0xf
fffffe0009b555cc  ldr w8, [sp, #0x34]
fffffe0009b555d0  and w9, w8, #0xf
fffffe0009b555d4  cmp w9, #0xf
fffffe0009b555d8  b.eq #0xfffffe0009b5574c
fffffe0009b555dc  cmp w25, w9
fffffe0009b555e0  b.eq #0xfffffe0009b5574c
fffffe0009b555e4  mov x24, x0
fffffe0009b555e8  ldr x16, [x21]
fffffe0009b555ec  mov x17, x21
fffffe0009b555f0  movk x17, #0xcda1, lsl #48
fffffe0009b555f4  autda x16, x17
fffffe0009b555f8  mov x17, #0xd18
fffffe0009b555fc  add x16, x16, x17
fffffe0009b55600  ldr x8, [x16]
fffffe0009b55604  mov x27, x9
fffffe0009b55608  mov x9, x16
fffffe0009b5560c  mov x0, x21
fffffe0009b55610  mov w1, #2
fffffe0009b55614  mov w2, #0x180
fffffe0009b55618  mov x3, x19
fffffe0009b5561c  mov x17, x9
fffffe0009b55620  movk x17, #0x73ce, lsl #48
fffffe0009b55624  blraa x8, x17
fffffe0009b55628  orr w3, w24, #0xf
fffffe0009b5562c  add x8, x28, #0xd30
fffffe0009b55630  mov x0, x21
fffffe0009b55634  mov w1, #2
fffffe0009b55638  mov w2, #0x180
fffffe0009b5563c  mov x4, x19
fffffe0009b55640  mov x17, x8
fffffe0009b55644  movk x17, #0xfd0b, lsl #48
fffffe0009b55648  blraa x26, x17
fffffe0009b5564c  ldr x16, [x21]
fffffe0009b55650  mov x17, x21
fffffe0009b55654  movk x17, #0xcda1, lsl #48
fffffe0009b55658  autda x16, x17
fffffe0009b5565c  mov x17, x16
fffffe0009b55660  xpacd x17
fffffe0009b55664  cmp x16, x17
fffffe0009b55668  b.eq #0xfffffe0009b55670
fffffe0009b5566c  brk #0xc472
fffffe0009b55670  add x8, x16, #0xd28
fffffe0009b55674  ldr x9, [x16, #0xd28]
fffffe0009b55678  mov x0, x21
fffffe0009b5567c  mov w1, #2
fffffe0009b55680  mov w2, #0x180
fffffe0009b55684  mov w3, #0xf0
fffffe0009b55688  mov w4, #0xf0
fffffe0009b5568c  mov x6, x19
fffffe0009b55690  mov w5, #0xee00
fffffe0009b55694  movk w5, #2, lsl #16
fffffe0009b55698  mov x17, x8
fffffe0009b5569c  movk x17, #0x7f, lsl #48
fffffe0009b556a0  blraa x9, x17
fffffe0009b556a4  mov x9, x27
fffffe0009b556a8  b #0xfffffe0009b5574c
fffffe0009b556ac  cbnz w23, #0xfffffe0009b55798
fffffe0009b556b0  cmp w20, #0x268
fffffe0009b556b4  b.ne #0xfffffe0009b55798
fffffe0009b556b8  ldr x16, [x21]
fffffe0009b556bc  mov x17, x21
fffffe0009b556c0  movk x17, #0xcda1, lsl #48
fffffe0009b556c4  autda x16, x17
fffffe0009b556c8  mov x17, #0xd18
fffffe0009b556cc  add x16, x16, x17
fffffe0009b556d0  ldr x8, [x16]
fffffe0009b556d4  mov x9, x16
fffffe0009b556d8  mov x0, x21
fffffe0009b556dc  mov w1, #0
fffffe0009b556e0  mov w2, #0x268
fffffe0009b556e4  mov x3, x19
fffffe0009b556e8  mov x17, x9
fffffe0009b556ec  movk x17, #0x73ce, lsl #48
fffffe0009b556f0  blraa x8, x17
fffffe0009b556f4  and w25, w0, #0xf
fffffe0009b556f8  ldr w8, [sp, #0x34]
fffffe0009b556fc  ands w9, w8, #0xf
fffffe0009b55700  b.ne #0xfffffe0009b5574c
fffffe0009b55704  cbz w25, #0xfffffe0009b5574c
fffffe0009b55708  ldr x16, [x21]
fffffe0009b5570c  mov x17, x21
fffffe0009b55710  movk x17, #0xcda1, lsl #48
fffffe0009b55714  autda x16, x17
fffffe0009b55718  mov x17, #0xa08
fffffe0009b5571c  add x16, x16, x17
fffffe0009b55720  ldr x8, [x16]
fffffe0009b55724  mov x9, x16
fffffe0009b55728  mov x0, x21
fffffe0009b5572c  mov w1, #4
fffffe0009b55730  mov w2, #0
fffffe0009b55734  mov w3, #1
fffffe0009b55738  mov x4, x19
fffffe0009b5573c  mov x17, x9
fffffe0009b55740  movk x17, #0xe748, lsl #48
fffffe0009b55744  blraa x8, x17
fffffe0009b55748  mov w9, #0
fffffe0009b5574c  str w9, [sp, #0x2c]
fffffe0009b55750  str wzr, [sp, #0x1c]
fffffe0009b55754  eor w8, w22, #1
fffffe0009b55758  stp wzr, w8, [sp, #8]
fffffe0009b5575c  b #0xfffffe0009b55870
fffffe0009b55760  cbnz w24, #0xfffffe0009b55790
fffffe0009b55764  ldr w9, [sp, #0x30]
fffffe0009b55768  cbz w9, #0xfffffe0009b55790
fffffe0009b5576c  cmp w8, #2
fffffe0009b55770  b.lo #0xfffffe0009b56398
fffffe0009b55774  add x8, x21, #0x36, lsl #12
fffffe0009b55778  add x8, x8, #0x9c0
fffffe0009b5577c  str wzr, [x8, w19, uxtw #2]
fffffe0009b55780  eor w9, w19, #1
fffffe0009b55784  ldr w8, [x8, w9, uxtw #2]
fffffe0009b55788  cbnz w8, #0xfffffe0009b56368
fffffe0009b5578c  b #0xfffffe0009b5639c
fffffe0009b55790  ldr w25, [sp, #0x30]
fffffe0009b55794  b #0xfffffe0009b55860
fffffe0009b55798  mov w8, #0
fffffe0009b5579c  cmp w23, #3
fffffe0009b557a0  cset w10, eq
fffffe0009b557a4  b.ne #0xfffffe0009b56388
fffffe0009b557a8  cmp w20, #0x268
fffffe0009b557ac  b.ne #0xfffffe0009b56388
fffffe0009b557b0  ldr x16, [x21]
fffffe0009b557b4  mov x17, x21
fffffe0009b557b8  movk x17, #0xcda1, lsl #48
fffffe0009b557bc  autda x16, x17
fffffe0009b557c0  mov x17, #0xd18
fffffe0009b557c4  add x16, x16, x17
fffffe0009b557c8  ldr x8, [x16]
fffffe0009b557cc  mov x9, x16
fffffe0009b557d0  mov x0, x21
fffffe0009b557d4  mov w1, #3
fffffe0009b557d8  mov w2, #0x268
fffffe0009b557dc  mov x3, x19
fffffe0009b557e0  mov x17, x9
fffffe0009b557e4  movk x17, #0x73ce, lsl #48
fffffe0009b557e8  blraa x8, x17
fffffe0009b557ec  mov w9, #0
fffffe0009b557f0  and w25, w0, #0xf
fffffe0009b557f4  ldr w8, [sp, #0x34]
fffffe0009b557f8  ands w8, w8, #0xf
fffffe0009b557fc  b.ne #0xfffffe0009b56614
fffffe0009b55800  cbz w25, #0xfffffe0009b56614
fffffe0009b55804  ldr x16, [x21]
fffffe0009b55808  mov x17, x21
fffffe0009b5580c  movk x17, #0xcda1, lsl #48
fffffe0009b55810  autda x16, x17
fffffe0009b55814  mov x17, #0xa08
fffffe0009b55818  add x16, x16, x17
fffffe0009b5581c  ldr x8, [x16]
fffffe0009b55820  mov x9, x16
fffffe0009b55824  mov w10, #1
fffffe0009b55828  str w10, [sp, #0x1c]
fffffe0009b5582c  mov x0, x21
fffffe0009b55830  mov w1, #5
fffffe0009b55834  mov w2, #0
fffffe0009b55838  mov w3, #1
fffffe0009b5583c  mov x4, x19
fffffe0009b55840  mov x17, x9
fffffe0009b55844  movk x17, #0xe748, lsl #48
fffffe0009b55848  blraa x8, x17
fffffe0009b5584c  str wzr, [sp, #0xc]
fffffe0009b55850  str wzr, [sp, #0x2c]
fffffe0009b55854  b #0xfffffe0009b56624
fffffe0009b55858  mov w24, #0xf
fffffe0009b5585c  mov x27, x22
fffffe0009b55860  str xzr, [sp, #8]
fffffe0009b55864  eor w8, w27, #1
fffffe0009b55868  stp wzr, w8, [sp, #0x1c]
fffffe0009b5586c  str w24, [sp, #0x2c]
fffffe0009b55870  cbnz w23, #0xfffffe0009b55c9c
fffffe0009b55874  str w25, [sp, #0x30]
fffffe0009b55878  str w23, [sp, #4]
fffffe0009b5587c  mov w26, #0
fffffe0009b55880  mov x9, x28
fffffe0009b55884  mov w28, #0
fffffe0009b55888  ldr w8, [sp, #0x34]
fffffe0009b5588c  and w27, w8, #0xf
fffffe0009b55890  and w22, w8, #0xf0
fffffe0009b55894  mov w10, #-0x2e8
fffffe0009b55898  mov w23, #-0x238
fffffe0009b5589c  add x25, x9, #0xd30
fffffe0009b558a0  cmp w28, #2
fffffe0009b558a4  csel w8, w23, w10, lo
fffffe0009b558a8  cbz w22, #0xfffffe0009b559a4
fffffe0009b558ac  cbnz w27, #0xfffffe0009b559a4
fffffe0009b558b0  add w8, w20, w8
fffffe0009b558b4  cmp w8, w26
fffffe0009b558b8  b.ne #0xfffffe0009b559a4
fffffe0009b558bc  add w24, w26, #0xd0
fffffe0009b558c0  mov x0, x21
fffffe0009b558c4  mov w1, #1
fffffe0009b558c8  mov x2, x24
fffffe0009b558cc  bl #0xfffffe0009861f54
fffffe0009b558d0  cbz w0, #0xfffffe0009b5665c
fffffe0009b558d4  mov x1, x0
fffffe0009b558d8  mov x0, x21
fffffe0009b558dc  mov x2, x19
fffffe0009b558e0  bl #0xfffffe0009861fb0
fffffe0009b558e4  cbnz w0, #0xfffffe0009b56660
fffffe0009b558e8  ldr x16, [x21]
fffffe0009b558ec  mov x17, x21
fffffe0009b558f0  movk x17, #0xcda1, lsl #48
fffffe0009b558f4  autda x16, x17
fffffe0009b558f8  mov x17, #0xd18
fffffe0009b558fc  add x16, x16, x17
fffffe0009b55900  ldr x8, [x16]
fffffe0009b55904  mov x9, x16
fffffe0009b55908  mov x0, x21
fffffe0009b5590c  mov w1, #1
fffffe0009b55910  mov x2, x24
fffffe0009b55914  mov x3, x19
fffffe0009b55918  mov x17, x9
fffffe0009b5591c  movk x17, #0x73ce, lsl #48
fffffe0009b55920  blraa x8, x17
fffffe0009b55924  and w3, w0, #0xfffffff0
fffffe0009b55928  mov x0, x21
fffffe0009b5592c  mov w1, #1
fffffe0009b55930  mov x2, x24
fffffe0009b55934  mov x4, x19
fffffe0009b55938  ldr x8, [sp, #0x38]
fffffe0009b5593c  mov x17, x25
fffffe0009b55940  movk x17, #0xfd0b, lsl #48
fffffe0009b55944  blraa x8, x17
fffffe0009b55948  ldr x16, [x21]
fffffe0009b5594c  mov x17, x21
fffffe0009b55950  movk x17, #0xcda1, lsl #48
fffffe0009b55954  autda x16, x17
fffffe0009b55958  mov x17, x16
fffffe0009b5595c  xpacd x17
fffffe0009b55960  cmp x16, x17
fffffe0009b55964  b.eq #0xfffffe0009b5596c
fffffe0009b55968  brk #0xc472
fffffe0009b5596c  add x8, x16, #0xd28
fffffe0009b55970  ldr x9, [x16, #0xd28]
fffffe0009b55974  mov x0, x21
fffffe0009b55978  mov w1, #1
fffffe0009b5597c  mov x2, x24
fffffe0009b55980  mov w3, #0xf0
fffffe0009b55984  mov w4, #0
fffffe0009b55988  mov w5, #0xee00
fffffe0009b5598c  movk w5, #2, lsl #16
fffffe0009b55990  mov x6, x19
fffffe0009b55994  mov x17, x8
fffffe0009b55998  movk x17, #0x7f, lsl #48
fffffe0009b5599c  blraa x9, x17
fffffe0009b559a0  mov w10, #-0x2e8
fffffe0009b559a4  add w28, w28, #1
fffffe0009b559a8  add w26, w26, #8
fffffe0009b559ac  cmp w26, #0x20
fffffe0009b559b0  b.ne #0xfffffe0009b558a0
fffffe0009b559b4  cmp w20, #0x248
fffffe0009b559b8  ldr x26, [sp, #0x38]
fffffe0009b559bc  ldr w23, [sp, #4]
fffffe0009b559c0  adrp x28, #0xfffffe0007e41000
fffffe0009b559c4  ldr x28, [x28, #0xc80]
fffffe0009b559c8  ldr w25, [sp, #0x30]
fffffe0009b559cc  b.eq #0xfffffe0009b55bb8
fffffe0009b559d0  cmp w20, #0x250
fffffe0009b559d4  b.eq #0xfffffe0009b55ba8
fffffe0009b559d8  cmp w20, #0x318
fffffe0009b559dc  b.ne #0xfffffe0009b55c9c
fffffe0009b559e0  cbnz w27, #0xfffffe0009b55c9c
fffffe0009b559e4  cbz w22, #0xfffffe0009b55c9c
fffffe0009b559e8  mov x0, x21
fffffe0009b559ec  mov w1, #0
fffffe0009b559f0  mov w2, #0x248
fffffe0009b559f4  bl #0xfffffe0009861f54
fffffe0009b559f8  mov x22, x0
fffffe0009b559fc  mov x0, x21
fffffe0009b55a00  mov w1, #0
fffffe0009b55a04  mov w2, #0x250
fffffe0009b55a08  bl #0xfffffe0009861f54
fffffe0009b55a0c  cbz w22, #0xfffffe0009b5666c
fffffe0009b55a10  mov x24, x0
fffffe0009b55a14  cbz w0, #0xfffffe0009b5666c
fffffe0009b55a18  mov x0, x21
fffffe0009b55a1c  mov x1, x22
fffffe0009b55a20  mov x2, x19
fffffe0009b55a24  bl #0xfffffe0009861fb0
fffffe0009b55a28  mov x22, x0
fffffe0009b55a2c  mov x0, x21
fffffe0009b55a30  mov x1, x24
fffffe0009b55a34  mov x2, x19
fffffe0009b55a38  bl #0xfffffe0009861fb0
fffffe0009b55a3c  orr w8, w22, w0
fffffe0009b55a40  cbnz w8, #0xfffffe0009b56670
fffffe0009b55a44  ldr x16, [x21]
fffffe0009b55a48  mov x17, x21
fffffe0009b55a4c  movk x17, #0xcda1, lsl #48
fffffe0009b55a50  autda x16, x17
fffffe0009b55a54  mov x17, #0xd18
fffffe0009b55a58  add x16, x16, x17
fffffe0009b55a5c  ldr x8, [x16]
fffffe0009b55a60  mov x9, x16
fffffe0009b55a64  mov x0, x21
fffffe0009b55a68  mov w1, #0
fffffe0009b55a6c  mov w2, #0x248
fffffe0009b55a70  mov x3, x19
fffffe0009b55a74  mov x17, x9
fffffe0009b55a78  movk x17, #0x73ce, lsl #48
fffffe0009b55a7c  blraa x8, x17
fffffe0009b55a80  and w3, w0, #0xfffffff0
fffffe0009b55a84  add x22, x28, #0xd30
fffffe0009b55a88  mov x0, x21
fffffe0009b55a8c  mov w1, #0
fffffe0009b55a90  mov w2, #0x248
fffffe0009b55a94  mov x4, x19
fffffe0009b55a98  mov x17, x22
fffffe0009b55a9c  movk x17, #0xfd0b, lsl #48
fffffe0009b55aa0  blraa x26, x17
fffffe0009b55aa4  ldr x16, [x21]
fffffe0009b55aa8  mov x17, x21
fffffe0009b55aac  movk x17, #0xcda1, lsl #48
fffffe0009b55ab0  autda x16, x17
fffffe0009b55ab4  mov x17, x16
fffffe0009b55ab8  xpacd x17
fffffe0009b55abc  cmp x16, x17
fffffe0009b55ac0  b.eq #0xfffffe0009b55ac8
fffffe0009b55ac4  brk #0xc472
fffffe0009b55ac8  add x8, x16, #0xd28
fffffe0009b55acc  ldr x9, [x16, #0xd28]
fffffe0009b55ad0  mov x0, x21
fffffe0009b55ad4  mov w1, #0
fffffe0009b55ad8  mov w2, #0x248
fffffe0009b55adc  mov w3, #0xf0
fffffe0009b55ae0  mov w4, #0
fffffe0009b55ae4  mov w5, #0xee00
fffffe0009b55ae8  movk w5, #2, lsl #16
fffffe0009b55aec  mov x6, x19
fffffe0009b55af0  mov x17, x8
fffffe0009b55af4  movk x17, #0x7f, lsl #48
fffffe0009b55af8  blraa x9, x17
fffffe0009b55afc  ldr x16, [x21]
fffffe0009b55b00  mov x17, x21
fffffe0009b55b04  movk x17, #0xcda1, lsl #48
fffffe0009b55b08  autda x16, x17
fffffe0009b55b0c  mov x17, x16
fffffe0009b55b10  xpacd x17
fffffe0009b55b14  cmp x16, x17
fffffe0009b55b18  b.eq #0xfffffe0009b55b20
fffffe0009b55b1c  brk #0xc472
fffffe0009b55b20  add x8, x16, #0xd18
fffffe0009b55b24  ldr x9, [x16, #0xd18]
fffffe0009b55b28  mov x0, x21
fffffe0009b55b2c  mov w1, #0
fffffe0009b55b30  mov w2, #0x250
fffffe0009b55b34  mov x3, x19
fffffe0009b55b38  mov x17, x8
fffffe0009b55b3c  movk x17, #0x73ce, lsl #48
fffffe0009b55b40  blraa x9, x17
fffffe0009b55b44  and w3, w0, #0xfffffff0
fffffe0009b55b48  mov x0, x21
fffffe0009b55b4c  mov w1, #0
fffffe0009b55b50  mov w2, #0x250
fffffe0009b55b54  mov x4, x19
fffffe0009b55b58  mov x17, x22
fffffe0009b55b5c  movk x17, #0xfd0b, lsl #48
fffffe0009b55b60  blraa x26, x17
fffffe0009b55b64  ldr x16, [x21]
fffffe0009b55b68  mov x17, x21
fffffe0009b55b6c  movk x17, #0xcda1, lsl #48
fffffe0009b55b70  autda x16, x17
fffffe0009b55b74  mov x17, x16
fffffe0009b55b78  xpacd x17
fffffe0009b55b7c  cmp x16, x17
fffffe0009b55b80  b.eq #0xfffffe0009b55b88
fffffe0009b55b84  brk #0xc472
fffffe0009b55b88  add x8, x16, #0xd28
fffffe0009b55b8c  ldr x9, [x16, #0xd28]
fffffe0009b55b90  mov x0, x21
fffffe0009b55b94  mov w1, #0
fffffe0009b55b98  mov w2, #0x250
fffffe0009b55b9c  mov w3, #0xf0
fffffe0009b55ba0  mov w4, #0
fffffe0009b55ba4  b #0xfffffe0009b55c84
fffffe0009b55ba8  cmp w27, #0xf
fffffe0009b55bac  b.ne #0xfffffe0009b55c9c
fffffe0009b55bb0  cmp w22, #0xf0
fffffe0009b55bb4  b.eq #0xfffffe0009b55c9c
fffffe0009b55bb8  mov x0, x21
fffffe0009b55bbc  mov w1, #0
fffffe0009b55bc0  mov w2, #0x318
fffffe0009b55bc4  bl #0xfffffe0009861f54
fffffe0009b55bc8  cbz w0, #0xfffffe0009b56664
fffffe0009b55bcc  mov x1, x0
fffffe0009b55bd0  mov x0, x21
fffffe0009b55bd4  mov x2, x19
fffffe0009b55bd8  bl #0xfffffe0009861fb0
fffffe0009b55bdc  cmp w0, #0xf
fffffe0009b55be0  b.ne #0xfffffe0009b56668
fffffe0009b55be4  ldr x16, [x21]
fffffe0009b55be8  mov x17, x21
fffffe0009b55bec  movk x17, #0xcda1, lsl #48
fffffe0009b55bf0  autda x16, x17
fffffe0009b55bf4  mov x17, #0xd18
fffffe0009b55bf8  add x16, x16, x17
fffffe0009b55bfc  ldr x8, [x16]
fffffe0009b55c00  mov x9, x16
fffffe0009b55c04  mov x0, x21
fffffe0009b55c08  mov w1, #0
fffffe0009b55c0c  mov w2, #0x318
fffffe0009b55c10  mov x3, x19
fffffe0009b55c14  mov x17, x9
fffffe0009b55c18  movk x17, #0x73ce, lsl #48
fffffe0009b55c1c  blraa x8, x17
fffffe0009b55c20  orr w3, w0, #0xf
fffffe0009b55c24  add x8, x28, #0xd30
fffffe0009b55c28  mov x0, x21
fffffe0009b55c2c  mov w1, #0
fffffe0009b55c30  mov w2, #0x318
fffffe0009b55c34  mov x4, x19
fffffe0009b55c38  mov x17, x8
fffffe0009b55c3c  movk x17, #0xfd0b, lsl #48
fffffe0009b55c40  blraa x26, x17
fffffe0009b55c44  ldr x16, [x21]
fffffe0009b55c48  mov x17, x21
fffffe0009b55c4c  movk x17, #0xcda1, lsl #48
fffffe0009b55c50  autda x16, x17
fffffe0009b55c54  mov x17, x16
fffffe0009b55c58  xpacd x17
fffffe0009b55c5c  cmp x16, x17
fffffe0009b55c60  b.eq #0xfffffe0009b55c68
fffffe0009b55c64  brk #0xc472
fffffe0009b55c68  add x8, x16, #0xd28
fffffe0009b55c6c  ldr x9, [x16, #0xd28]
fffffe0009b55c70  mov x0, x21
fffffe0009b55c74  mov w1, #0
fffffe0009b55c78  mov w2, #0x318
fffffe0009b55c7c  mov w3, #0xf0
fffffe0009b55c80  mov w4, #0xf0
fffffe0009b55c84  mov w5, #0xee00
fffffe0009b55c88  movk w5, #2, lsl #16
fffffe0009b55c8c  mov x6, x19
fffffe0009b55c90  mov x17, x8
fffffe0009b55c94  movk x17, #0x7f, lsl #48
fffffe0009b55c98  blraa x9, x17
fffffe0009b55c9c  add x8, x28, #0xd30
fffffe0009b55ca0  mov x0, x21
fffffe0009b55ca4  mov x1, x23
fffffe0009b55ca8  mov x2, x20
fffffe0009b55cac  ldr w3, [sp, #0x34]
fffffe0009b55cb0  mov x4, x19
fffffe0009b55cb4  mov x17, x8
fffffe0009b55cb8  movk x17, #0xfd0b, lsl #48
fffffe0009b55cbc  blraa x26, x17
fffffe0009b55cc0  cbnz w23, #0xfffffe0009b55cd0
fffffe0009b55cc4  mov w8, #0xc029
fffffe0009b55cc8  cmp w20, w8
fffffe0009b55ccc  b.lo #0xfffffe0009b55ce8
fffffe0009b55cd0  sub w8, w20, #0x100
fffffe0009b55cd4  cmp w23, #2
fffffe0009b55cd8  b.ne #0xfffffe0009b55d00
fffffe0009b55cdc  mov w9, #0x7f21
fffffe0009b55ce0  cmp w8, w9
fffffe0009b55ce4  b.hs #0xfffffe0009b55d00
fffffe0009b55ce8  ldr w8, [sp, #0x34]
fffffe0009b55cec  mvn w8, w8
fffffe0009b55cf0  tst w8, #0xf
fffffe0009b55cf4  ldr x22, [sp, #0x10]
fffffe0009b55cf8  b.ne #0xfffffe0009b55d30
fffffe0009b55cfc  b #0xfffffe0009b55d7c
fffffe0009b55d00  mov w9, #0xbf00
fffffe0009b55d04  cmp w8, w9
fffffe0009b55d08  cset w8, hi
fffffe0009b55d0c  ldr w9, [sp, #8]
fffffe0009b55d10  eor w9, w9, #1
fffffe0009b55d14  orr w8, w8, w9
fffffe0009b55d18  ldr x22, [sp, #0x10]
fffffe0009b55d1c  tbnz w8, #0, #0xfffffe0009b55d7c
fffffe0009b55d20  ldr w8, [sp, #0x34]
fffffe0009b55d24  and w8, w8, #0xf
fffffe0009b55d28  cmp w8, #0xf
fffffe0009b55d2c  b.eq #0xfffffe0009b55d7c
fffffe0009b55d30  ldr x16, [x21]
fffffe0009b55d34  mov x17, x21
fffffe0009b55d38  movk x17, #0xcda1, lsl #48
fffffe0009b55d3c  autda x16, x17
fffffe0009b55d40  mov x17, #0xd28
fffffe0009b55d44  add x16, x16, x17
fffffe0009b55d48  ldr x8, [x16]
fffffe0009b55d4c  mov x9, x16
fffffe0009b55d50  mov x0, x21
fffffe0009b55d54  mov x1, x23
fffffe0009b55d58  mov x2, x20
fffffe0009b55d5c  mov w3, #0x800
fffffe0009b55d60  mov w4, #0
fffffe0009b55d64  mov w5, #0xee00
fffffe0009b55d68  movk w5, #2, lsl #16
fffffe0009b55d6c  mov x6, x19
fffffe0009b55d70  mov x17, x9
fffffe0009b55d74  movk x17, #0x7f, lsl #48
fffffe0009b55d78  blraa x8, x17
fffffe0009b55d7c  ldp w24, w8, [sp, #0x1c]
fffffe0009b55d80  cbz w8, #0xfffffe0009b55dd4
fffffe0009b55d84  ldr w8, [x22]
fffffe0009b55d88  cmp w8, #2
fffffe0009b55d8c  b.lo #0xfffffe0009b55dd4
fffffe0009b55d90  ldr w8, [sp, #0x2c]
fffffe0009b55d94  cmp w8, #0xf
fffffe0009b55d98  b.ne #0xfffffe0009b55dd4
fffffe0009b55d9c  cmp w25, #0xf
fffffe0009b55da0  b.eq #0xfffffe0009b55dd4
fffffe0009b55da4  ldr x22, [x28, #0xd28]
fffffe0009b55da8  add x8, x28, #0xd28
fffffe0009b55dac  mov x0, x21
fffffe0009b55db0  mov w1, #0
fffffe0009b55db4  mov w2, #0x1e8
fffffe0009b55db8  mov x3, x19
fffffe0009b55dbc  mov x17, x8
fffffe0009b55dc0  movk x17, #0x73ce, lsl #48
fffffe0009b55dc4  blraa x22, x17
fffffe0009b55dc8  mvn w8, w0
fffffe0009b55dcc  tst w8, #0xf0
fffffe0009b55dd0  b.ne #0xfffffe0009b55da8
fffffe0009b55dd4  cmp w23, #2
fffffe0009b55dd8  ldr w8, [sp, #0x2c]
fffffe0009b55ddc  b.ne #0xfffffe0009b55e04
fffffe0009b55de0  cmp w20, #0x3c0
fffffe0009b55de4  b.ne #0xfffffe0009b55e04
fffffe0009b55de8  cmp w8, #0xf
fffffe0009b55dec  b.ne #0xfffffe0009b55e04
fffffe0009b55df0  cmp w25, #0xf
fffffe0009b55df4  b.eq #0xfffffe0009b55e04
fffffe0009b55df8  mov x0, x21
fffffe0009b55dfc  bl #0xfffffe0009864804
fffffe0009b55e00  ldr w8, [sp, #0x2c]
fffffe0009b55e04  ldr w9, [sp, #0xc]
fffffe0009b55e08  cbz w9, #0xfffffe0009b55e90
fffffe0009b55e0c  cmp w8, #0xf
fffffe0009b55e10  b.ne #0xfffffe0009b55e90
fffffe0009b55e14  cmp w25, #0xf
fffffe0009b55e18  b.eq #0xfffffe0009b55e90
fffffe0009b55e1c  ldr x22, [x28, #0xd28]
fffffe0009b55e20  add x8, x28, #0xd28
fffffe0009b55e24  mov x0, x21
fffffe0009b55e28  mov w1, #0
fffffe0009b55e2c  mov w2, #0x268
fffffe0009b55e30  mov x3, x19
fffffe0009b55e34  mov x17, x8
fffffe0009b55e38  movk x17, #0x73ce, lsl #48
fffffe0009b55e3c  blraa x22, x17
fffffe0009b55e40  mvn w8, w0
fffffe0009b55e44  tst w8, #0xf0
fffffe0009b55e48  b.ne #0xfffffe0009b55e20
fffffe0009b55e4c  ldr x16, [x21]
fffffe0009b55e50  mov x17, x21
fffffe0009b55e54  movk x17, #0xcda1, lsl #48
fffffe0009b55e58  autda x16, x17
fffffe0009b55e5c  mov x17, #0xa08
fffffe0009b55e60  add x16, x16, x17
fffffe0009b55e64  ldr x8, [x16]
fffffe0009b55e68  mov x9, x16
fffffe0009b55e6c  mov x0, x21
fffffe0009b55e70  mov w1, #4
fffffe0009b55e74  mov w2, #1
fffffe0009b55e78  mov w3, #1
fffffe0009b55e7c  mov x4, x19
fffffe0009b55e80  mov x17, x9
fffffe0009b55e84  movk x17, #0xe748, lsl #48
fffffe0009b55e88  blraa x8, x17
fffffe0009b55e8c  ldr w8, [sp, #0x2c]
fffffe0009b55e90  cbz w24, #0xfffffe0009b55f14
fffffe0009b55e94  cmp w8, #0xf
fffffe0009b55e98  b.ne #0xfffffe0009b55f14
fffffe0009b55e9c  cmp w25, #0xf
fffffe0009b55ea0  b.eq #0xfffffe0009b55f14
fffffe0009b55ea4  ldr x22, [x28, #0xd28]
fffffe0009b55ea8  add x8, x28, #0xd28
fffffe0009b55eac  mov x0, x21
fffffe0009b55eb0  mov w1, #3
fffffe0009b55eb4  mov w2, #0x268
fffffe0009b55eb8  mov x3, x19
fffffe0009b55ebc  mov x17, x8
fffffe0009b55ec0  movk x17, #0x73ce, lsl #48
fffffe0009b55ec4  blraa x22, x17
fffffe0009b55ec8  mvn w8, w0
fffffe0009b55ecc  tst w8, #0xf0
fffffe0009b55ed0  b.ne #0xfffffe0009b55ea8
fffffe0009b55ed4  ldr x16, [x21]
fffffe0009b55ed8  mov x17, x21
fffffe0009b55edc  movk x17, #0xcda1, lsl #48
fffffe0009b55ee0  autda x16, x17
fffffe0009b55ee4  mov x17, #0xa08
fffffe0009b55ee8  add x16, x16, x17
fffffe0009b55eec  ldr x8, [x16]
fffffe0009b55ef0  mov x9, x16
fffffe0009b55ef4  mov x0, x21
fffffe0009b55ef8  mov w1, #5
fffffe0009b55efc  mov w2, #1
fffffe0009b55f00  mov w3, #1
fffffe0009b55f04  mov x4, x19
fffffe0009b55f08  mov x17, x9
fffffe0009b55f0c  movk x17, #0xe748, lsl #48
fffffe0009b55f10  blraa x8, x17
fffffe0009b55f14  cmp w23, #1
fffffe0009b55f18  b.ne #0xfffffe0009b56368
fffffe0009b55f1c  mov w24, #0
fffffe0009b55f20  ldr w8, [sp, #0x34]
fffffe0009b55f24  and w25, w8, #0xf
fffffe0009b55f28  mov w27, #0x88
fffffe0009b55f2c  mov w23, #0x2e8
fffffe0009b55f30  add x28, x28, #0xd30
fffffe0009b55f34  cmp w24, #2
fffffe0009b55f38  mov w8, #0x238
fffffe0009b55f3c  csel w22, w8, w23, lo
fffffe0009b55f40  cmp w25, #0xf
fffffe0009b55f44  b.ne #0xfffffe0009b56358
fffffe0009b55f48  cmp w20, w27
fffffe0009b55f4c  b.ne #0xfffffe0009b56358
fffffe0009b55f50  ldr x16, [x21]
fffffe0009b55f54  mov x17, x21
fffffe0009b55f58  movk x17, #0xcda1, lsl #48
fffffe0009b55f5c  autda x16, x17
fffffe0009b55f60  mov x17, #0xd18
fffffe0009b55f64  add x16, x16, x17
fffffe0009b55f68  ldr x8, [x16]
fffffe0009b55f6c  mov x9, x16
fffffe0009b55f70  mov x0, x21
fffffe0009b55f74  mov w1, #1
fffffe0009b55f78  mov x2, x20
fffffe0009b55f7c  mov x3, x19
fffffe0009b55f80  mov x17, x9
fffffe0009b55f84  movk x17, #0x73ce, lsl #48
fffffe0009b55f88  blraa x8, x17
fffffe0009b55f8c  mvn w8, w0
fffffe0009b55f90  tst w8, #0xf0
fffffe0009b55f94  b.eq #0xfffffe0009b56358
fffffe0009b55f98  add w23, w27, #0x48
fffffe0009b55f9c  add w8, w22, w27
fffffe0009b55fa0  sub w22, w8, #0x88
fffffe0009b55fa4  orr w3, w0, #0x80000000
fffffe0009b55fa8  mov x0, x21
fffffe0009b55fac  mov w1, #1
fffffe0009b55fb0  mov x2, x20
fffffe0009b55fb4  mov x4, x19
fffffe0009b55fb8  mov x17, x28
fffffe0009b55fbc  movk x17, #0xfd0b, lsl #48
fffffe0009b55fc0  blraa x26, x17
fffffe0009b55fc4  mov x0, x21
fffffe0009b55fc8  mov x1, x22
fffffe0009b55fcc  mov x2, x19
fffffe0009b55fd0  bl #0xfffffe000985d34c
fffffe0009b55fd4  orr w3, w0, #0x8000000f
fffffe0009b55fd8  mov x0, x21
fffffe0009b55fdc  mov w1, #0
fffffe0009b55fe0  mov x2, x22
fffffe0009b55fe4  mov x4, x19
fffffe0009b55fe8  mov x17, x28
fffffe0009b55fec  movk x17, #0xfd0b, lsl #48
fffffe0009b55ff0  blraa x26, x17
fffffe0009b55ff4  ldr x16, [x21]
fffffe0009b55ff8  mov x17, x21
fffffe0009b55ffc  movk x17, #0xcda1, lsl #48
fffffe0009b56000  autda x16, x17
fffffe0009b56004  mov x17, x16
fffffe0009b56008  xpacd x17
fffffe0009b5600c  cmp x16, x17
fffffe0009b56010  b.eq #0xfffffe0009b56018
fffffe0009b56014  brk #0xc472
fffffe0009b56018  add x8, x16, #0xd28
fffffe0009b5601c  ldr x9, [x16, #0xd28]
fffffe0009b56020  mov x0, x21
fffffe0009b56024  mov w1, #0
fffffe0009b56028  mov x2, x22
fffffe0009b5602c  mov w3, #0xf0
fffffe0009b56030  mov w4, #0xf0
fffffe0009b56034  mov w5, #0xee00
fffffe0009b56038  movk w5, #2, lsl #16
fffffe0009b5603c  mov x6, x19
fffffe0009b56040  mov x17, x8
fffffe0009b56044  movk x17, #0x7f, lsl #48
fffffe0009b56048  blraa x9, x17
fffffe0009b5604c  ldr x16, [x21]
fffffe0009b56050  mov x17, x21
fffffe0009b56054  movk x17, #0xcda1, lsl #48
fffffe0009b56058  autda x16, x17
fffffe0009b5605c  mov x17, x16
fffffe0009b56060  xpacd x17
fffffe0009b56064  cmp x16, x17
fffffe0009b56068  b.eq #0xfffffe0009b56070
fffffe0009b5606c  brk #0xc472
fffffe0009b56070  add x8, x16, #0xd18
fffffe0009b56074  ldr x9, [x16, #0xd18]
fffffe0009b56078  mov x0, x21
fffffe0009b5607c  mov w1, #1
fffffe0009b56080  mov x2, x23
fffffe0009b56084  mov x3, x19
fffffe0009b56088  mov x17, x8
fffffe0009b5608c  movk x17, #0x73ce, lsl #48
fffffe0009b56090  blraa x9, x17
fffffe0009b56094  orr w3, w0, #0x8000000f
fffffe0009b56098  mov x0, x21
fffffe0009b5609c  mov w1, #1
fffffe0009b560a0  mov x2, x23
fffffe0009b560a4  mov x4, x19
fffffe0009b560a8  mov x17, x28
fffffe0009b560ac  movk x17, #0xfd0b, lsl #48
fffffe0009b560b0  blraa x26, x17
fffffe0009b560b4  ldr x16, [x21]
fffffe0009b560b8  mov x17, x21
fffffe0009b560bc  movk x17, #0xcda1, lsl #48
fffffe0009b560c0  autda x16, x17
fffffe0009b560c4  mov x17, x16
fffffe0009b560c8  xpacd x17
fffffe0009b560cc  cmp x16, x17
fffffe0009b560d0  b.eq #0xfffffe0009b560d8
fffffe0009b560d4  brk #0xc472
fffffe0009b560d8  add x8, x16, #0xd28
fffffe0009b560dc  ldr x9, [x16, #0xd28]
fffffe0009b560e0  mov x0, x21
fffffe0009b560e4  mov w1, #1
fffffe0009b560e8  mov x2, x23
fffffe0009b560ec  mov w3, #0xf0
fffffe0009b560f0  mov w4, #0xf0
fffffe0009b560f4  mov w5, #0xee00
fffffe0009b560f8  movk w5, #2, lsl #16
fffffe0009b560fc  mov x6, x19
fffffe0009b56100  mov x17, x8
fffffe0009b56104  movk x17, #0x7f, lsl #48
fffffe0009b56108  blraa x9, x17
fffffe0009b5610c  ldr x16, [x21]
fffffe0009b56110  mov x17, x21
fffffe0009b56114  movk x17, #0xcda1, lsl #48
fffffe0009b56118  autda x16, x17
fffffe0009b5611c  mov x17, x16
fffffe0009b56120  xpacd x17
fffffe0009b56124  cmp x16, x17
fffffe0009b56128  b.eq #0xfffffe0009b56130
fffffe0009b5612c  brk #0xc472
fffffe0009b56130  add x8, x16, #0xd18
fffffe0009b56134  ldr x9, [x16, #0xd18]
fffffe0009b56138  mov x0, x21
fffffe0009b5613c  mov w1, #1
fffffe0009b56140  mov x2, x20
fffffe0009b56144  mov x3, x19
fffffe0009b56148  mov x17, x8
fffffe0009b5614c  movk x17, #0x73ce, lsl #48
fffffe0009b56150  blraa x9, x17
fffffe0009b56154  and w3, w0, #0x7fffffff
fffffe0009b56158  mov x0, x21
fffffe0009b5615c  mov w1, #1
fffffe0009b56160  mov x2, x20
fffffe0009b56164  mov x4, x19
fffffe0009b56168  mov x17, x28
fffffe0009b5616c  movk x17, #0xfd0b, lsl #48
fffffe0009b56170  blraa x26, x17
fffffe0009b56174  mov x0, x21
fffffe0009b56178  mov x1, x22
fffffe0009b5617c  mov x2, x19
fffffe0009b56180  bl #0xfffffe000985d34c
fffffe0009b56184  and w3, w0, #0x7fffffff
fffffe0009b56188  mov x0, x21
fffffe0009b5618c  mov w1, #0
fffffe0009b56190  mov x2, x22
fffffe0009b56194  mov x4, x19
fffffe0009b56198  mov x17, x28
fffffe0009b5619c  movk x17, #0xfd0b, lsl #48
fffffe0009b561a0  blraa x26, x17
fffffe0009b561a4  ldr x16, [x21]
fffffe0009b561a8  mov x17, x21
fffffe0009b561ac  movk x17, #0xcda1, lsl #48
fffffe0009b561b0  autda x16, x17
fffffe0009b561b4  mov x17, x16
fffffe0009b561b8  xpacd x17
fffffe0009b561bc  cmp x16, x17
fffffe0009b561c0  b.eq #0xfffffe0009b561c8
fffffe0009b561c4  brk #0xc472
fffffe0009b561c8  add x8, x16, #0xd18
fffffe0009b561cc  ldr x9, [x16, #0xd18]
fffffe0009b561d0  mov x0, x21
fffffe0009b561d4  mov w1, #1
fffffe0009b561d8  mov x2, x23
fffffe0009b561dc  mov x3, x19
fffffe0009b561e0  mov x17, x8
fffffe0009b561e4  movk x17, #0x73ce, lsl #48
fffffe0009b561e8  blraa x9, x17
fffffe0009b561ec  and w3, w0, #0x7fffffff
fffffe0009b561f0  mov x0, x21
fffffe0009b561f4  mov w1, #1
fffffe0009b561f8  mov x2, x23
fffffe0009b561fc  mov x4, x19
fffffe0009b56200  mov x17, x28
fffffe0009b56204  movk x17, #0xfd0b, lsl #48
fffffe0009b56208  blraa x26, x17
fffffe0009b5620c  ldr x16, [x21]
fffffe0009b56210  mov x17, x21
fffffe0009b56214  movk x17, #0xcda1, lsl #48
fffffe0009b56218  autda x16, x17
fffffe0009b5621c  mov x17, x16
fffffe0009b56220  xpacd x17
fffffe0009b56224  cmp x16, x17
fffffe0009b56228  b.eq #0xfffffe0009b56230
fffffe0009b5622c  brk #0xc472
fffffe0009b56230  add x8, x16, #0xd18
fffffe0009b56234  ldr x9, [x16, #0xd18]
fffffe0009b56238  mov x0, x21
fffffe0009b5623c  mov w1, #1
fffffe0009b56240  mov x2, x23
fffffe0009b56244  mov x3, x19
fffffe0009b56248  mov x17, x8
fffffe0009b5624c  movk x17, #0x73ce, lsl #48
fffffe0009b56250  blraa x9, x17
fffffe0009b56254  and w3, w0, #0xfffffff0
fffffe0009b56258  mov x0, x21
fffffe0009b5625c  mov w1, #1
fffffe0009b56260  mov x2, x23
fffffe0009b56264  mov x4, x19
fffffe0009b56268  mov x17, x28
fffffe0009b5626c  movk x17, #0xfd0b, lsl #48
fffffe0009b56270  blraa x26, x17
fffffe0009b56274  ldr x16, [x21]
fffffe0009b56278  mov x17, x21
fffffe0009b5627c  movk x17, #0xcda1, lsl #48
fffffe0009b56280  autda x16, x17
fffffe0009b56284  mov x17, x16
fffffe0009b56288  xpacd x17
fffffe0009b5628c  cmp x16, x17
fffffe0009b56290  b.eq #0xfffffe0009b56298
fffffe0009b56294  brk #0xc472
fffffe0009b56298  add x8, x16, #0xd28
fffffe0009b5629c  ldr x9, [x16, #0xd28]
fffffe0009b562a0  mov x0, x21
fffffe0009b562a4  mov w1, #1
fffffe0009b562a8  mov x2, x23
fffffe0009b562ac  mov w23, #0x2e8
fffffe0009b562b0  mov w3, #0xf0
fffffe0009b562b4  mov w4, #0
fffffe0009b562b8  mov w5, #0xee00
fffffe0009b562bc  movk w5, #2, lsl #16
fffffe0009b562c0  mov x6, x19
fffffe0009b562c4  mov x17, x8
fffffe0009b562c8  movk x17, #0x7f, lsl #48
fffffe0009b562cc  blraa x9, x17
fffffe0009b562d0  mov x0, x21
fffffe0009b562d4  mov x1, x22
fffffe0009b562d8  mov x2, x19
fffffe0009b562dc  bl #0xfffffe000985d34c
fffffe0009b562e0  and w3, w0, #0xfffffff0
fffffe0009b562e4  mov x0, x21
fffffe0009b562e8  mov w1, #0
fffffe0009b562ec  mov x2, x22
fffffe0009b562f0  mov x4, x19
fffffe0009b562f4  mov x17, x28
fffffe0009b562f8  movk x17, #0xfd0b, lsl #48
fffffe0009b562fc  blraa x26, x17
fffffe0009b56300  ldr x16, [x21]
fffffe0009b56304  mov x17, x21
fffffe0009b56308  movk x17, #0xcda1, lsl #48
fffffe0009b5630c  autda x16, x17
fffffe0009b56310  mov x17, x16
fffffe0009b56314  xpacd x17
fffffe0009b56318  cmp x16, x17
fffffe0009b5631c  b.eq #0xfffffe0009b56324
fffffe0009b56320  brk #0xc472
fffffe0009b56324  add x8, x16, #0xd28
fffffe0009b56328  ldr x9, [x16, #0xd28]
fffffe0009b5632c  mov x0, x21
fffffe0009b56330  mov w1, #0
fffffe0009b56334  mov x2, x22
fffffe0009b56338  mov w3, #0xf0
fffffe0009b5633c  mov w4, #0
fffffe0009b56340  mov w5, #0xee00
fffffe0009b56344  movk w5, #2, lsl #16
fffffe0009b56348  mov x6, x19
fffffe0009b5634c  mov x17, x8
fffffe0009b56350  movk x17, #0x7f, lsl #48
fffffe0009b56354  blraa x9, x17
fffffe0009b56358  add w24, w24, #1
fffffe0009b5635c  add w27, w27, #8
fffffe0009b56360  cmp w24, #4
fffffe0009b56364  b.ne #0xfffffe0009b55f34
fffffe0009b56368  ldp x29, x30, [sp, #0x90]
fffffe0009b5636c  ldp x20, x19, [sp, #0x80]
fffffe0009b56370  ldp x22, x21, [sp, #0x70]
fffffe0009b56374  ldp x24, x23, [sp, #0x60]
fffffe0009b56378  ldp x26, x25, [sp, #0x50]
fffffe0009b5637c  ldp x28, x27, [sp, #0x40]
fffffe0009b56380  add sp, sp, #0xa0
fffffe0009b56384  retab 
fffffe0009b56388  stp w10, w8, [sp, #8]
fffffe0009b5638c  str w9, [sp, #0x2c]
fffffe0009b56390  str w8, [sp, #0x1c]
fffffe0009b56394  b #0xfffffe0009b55870
fffffe0009b56398  cbz w8, #0xfffffe0009b56630
fffffe0009b5639c  str w22, [sp, #0x20]
fffffe0009b563a0  mov x20, x23
fffffe0009b563a4  mov w24, #0
fffffe0009b563a8  ldr x27, [sp, #0x10]
fffffe0009b563ac  add x22, x28, #0xd28
fffffe0009b563b0  mov x0, x21
fffffe0009b563b4  mov w1, #0
fffffe0009b563b8  mov w2, #0x1e8
fffffe0009b563bc  mov x3, x24
fffffe0009b563c0  mov x17, x22
fffffe0009b563c4  movk x17, #0x73ce, lsl #48
fffffe0009b563c8  blraa x25, x17
fffffe0009b563cc  and w8, w0, #0xfff0ffff
fffffe0009b563d0  orr w3, w8, #0x40000
fffffe0009b563d4  add x23, x28, #0xd30
fffffe0009b563d8  mov x0, x21
fffffe0009b563dc  mov w1, #0
fffffe0009b563e0  mov w2, #0x1e8
fffffe0009b563e4  mov x4, x24
fffffe0009b563e8  mov x17, x23
fffffe0009b563ec  movk x17, #0xfd0b, lsl #48
fffffe0009b563f0  blraa x26, x17
fffffe0009b563f4  mov x0, x21
fffffe0009b563f8  mov w1, #0
fffffe0009b563fc  mov w2, #0x1e8
fffffe0009b56400  mov x3, x24
fffffe0009b56404  mov x17, x22
fffffe0009b56408  movk x17, #0x73ce, lsl #48
fffffe0009b5640c  blraa x25, x17
fffffe0009b56410  orr w3, w0, #0x10000000
fffffe0009b56414  mov x0, x21
fffffe0009b56418  mov w1, #0
fffffe0009b5641c  mov w2, #0x1e8
fffffe0009b56420  mov x4, x24
fffffe0009b56424  mov x17, x23
fffffe0009b56428  movk x17, #0xfd0b, lsl #48
fffffe0009b5642c  blraa x26, x17
fffffe0009b56430  add w24, w24, #1
fffffe0009b56434  ldr w8, [x27]
fffffe0009b56438  cmp w24, w8
fffffe0009b5643c  b.lo #0xfffffe0009b563ac
fffffe0009b56440  cbz w8, #0xfffffe0009b56648
fffffe0009b56444  mov w24, #0
fffffe0009b56448  ldr x22, [x28, #0xd38]
fffffe0009b5644c  mov x23, x20
fffffe0009b56450  ldr w20, [sp, #0x2c]
fffffe0009b56454  ldr x27, [sp, #0x10]
fffffe0009b56458  ldrb w8, [x27, #0x20]
fffffe0009b5645c  cbnz w8, #0xfffffe0009b564a4
fffffe0009b56460  add x8, x28, #0xd38
fffffe0009b56464  mov x0, x21
fffffe0009b56468  mov w1, #0
fffffe0009b5646c  mov w2, #0x1e8
fffffe0009b56470  mov w3, #0xf000000
fffffe0009b56474  mov w4, #0x4000000
fffffe0009b56478  mov w5, #0xee00
fffffe0009b5647c  movk w5, #2, lsl #16
fffffe0009b56480  mov x6, x24
fffffe0009b56484  mov x17, x8
fffffe0009b56488  movk x17, #0x7f, lsl #48
fffffe0009b5648c  blraa x22, x17
fffffe0009b56490  add w24, w24, #1
fffffe0009b56494  ldr w8, [x27]
fffffe0009b56498  cmp w24, w8
fffffe0009b5649c  b.lo #0xfffffe0009b56458
fffffe0009b564a0  cbz w8, #0xfffffe0009b5660c
fffffe0009b564a4  mov w24, #0
fffffe0009b564a8  add x8, x28, #0xd28
fffffe0009b564ac  mov x0, x21
fffffe0009b564b0  mov w1, #0
fffffe0009b564b4  mov w2, #0x1e8
fffffe0009b564b8  mov x3, x24
fffffe0009b564bc  mov x17, x8
fffffe0009b564c0  movk x17, #0x73ce, lsl #48
fffffe0009b564c4  blraa x25, x17

===== writeReg32_c00_branch va=0xfffffe0009b56368 file=0x2b52368
fffffe0009b56368  ldp x29, x30, [sp, #0x90]
fffffe0009b5636c  ldp x20, x19, [sp, #0x80]
fffffe0009b56370  ldp x22, x21, [sp, #0x70]
fffffe0009b56374  ldp x24, x23, [sp, #0x60]
fffffe0009b56378  ldp x26, x25, [sp, #0x50]
fffffe0009b5637c  ldp x28, x27, [sp, #0x40]
fffffe0009b56380  add sp, sp, #0xa0
fffffe0009b56384  retab 
fffffe0009b56388  stp w10, w8, [sp, #8]
fffffe0009b5638c  str w9, [sp, #0x2c]
fffffe0009b56390  str w8, [sp, #0x1c]
fffffe0009b56394  b #0xfffffe0009b55870
fffffe0009b56398  cbz w8, #0xfffffe0009b56630
fffffe0009b5639c  str w22, [sp, #0x20]
fffffe0009b563a0  mov x20, x23
fffffe0009b563a4  mov w24, #0
fffffe0009b563a8  ldr x27, [sp, #0x10]
fffffe0009b563ac  add x22, x28, #0xd28
fffffe0009b563b0  mov x0, x21
fffffe0009b563b4  mov w1, #0
fffffe0009b563b8  mov w2, #0x1e8
fffffe0009b563bc  mov x3, x24
fffffe0009b563c0  mov x17, x22
fffffe0009b563c4  movk x17, #0x73ce, lsl #48
fffffe0009b563c8  blraa x25, x17
fffffe0009b563cc  and w8, w0, #0xfff0ffff
fffffe0009b563d0  orr w3, w8, #0x40000
fffffe0009b563d4  add x23, x28, #0xd30
fffffe0009b563d8  mov x0, x21
fffffe0009b563dc  mov w1, #0
fffffe0009b563e0  mov w2, #0x1e8
fffffe0009b563e4  mov x4, x24
fffffe0009b563e8  mov x17, x23
fffffe0009b563ec  movk x17, #0xfd0b, lsl #48
fffffe0009b563f0  blraa x26, x17
fffffe0009b563f4  mov x0, x21
fffffe0009b563f8  mov w1, #0
fffffe0009b563fc  mov w2, #0x1e8
fffffe0009b56400  mov x3, x24
fffffe0009b56404  mov x17, x22
fffffe0009b56408  movk x17, #0x73ce, lsl #48
fffffe0009b5640c  blraa x25, x17
fffffe0009b56410  orr w3, w0, #0x10000000
fffffe0009b56414  mov x0, x21
fffffe0009b56418  mov w1, #0
fffffe0009b5641c  mov w2, #0x1e8
fffffe0009b56420  mov x4, x24
fffffe0009b56424  mov x17, x23
fffffe0009b56428  movk x17, #0xfd0b, lsl #48
fffffe0009b5642c  blraa x26, x17
fffffe0009b56430  add w24, w24, #1
fffffe0009b56434  ldr w8, [x27]
fffffe0009b56438  cmp w24, w8
fffffe0009b5643c  b.lo #0xfffffe0009b563ac
fffffe0009b56440  cbz w8, #0xfffffe0009b56648
fffffe0009b56444  mov w24, #0
fffffe0009b56448  ldr x22, [x28, #0xd38]
fffffe0009b5644c  mov x23, x20
fffffe0009b56450  ldr w20, [sp, #0x2c]
fffffe0009b56454  ldr x27, [sp, #0x10]
fffffe0009b56458  ldrb w8, [x27, #0x20]
fffffe0009b5645c  cbnz w8, #0xfffffe0009b564a4
fffffe0009b56460  add x8, x28, #0xd38
fffffe0009b56464  mov x0, x21
fffffe0009b56468  mov w1, #0
fffffe0009b5646c  mov w2, #0x1e8
fffffe0009b56470  mov w3, #0xf000000
fffffe0009b56474  mov w4, #0x4000000
fffffe0009b56478  mov w5, #0xee00
fffffe0009b5647c  movk w5, #2, lsl #16
fffffe0009b56480  mov x6, x24
fffffe0009b56484  mov x17, x8
fffffe0009b56488  movk x17, #0x7f, lsl #48
fffffe0009b5648c  blraa x22, x17
fffffe0009b56490  add w24, w24, #1
fffffe0009b56494  ldr w8, [x27]
fffffe0009b56498  cmp w24, w8
fffffe0009b5649c  b.lo #0xfffffe0009b56458
fffffe0009b564a0  cbz w8, #0xfffffe0009b5660c
fffffe0009b564a4  mov w24, #0
fffffe0009b564a8  add x8, x28, #0xd28
fffffe0009b564ac  mov x0, x21
fffffe0009b564b0  mov w1, #0
fffffe0009b564b4  mov w2, #0x1e8
fffffe0009b564b8  mov x3, x24
fffffe0009b564bc  mov x17, x8
fffffe0009b564c0  movk x17, #0x73ce, lsl #48
fffffe0009b564c4  blraa x25, x17
fffffe0009b564c8  orr w3, w0, #0xf0000
fffffe0009b564cc  add x8, x28, #0xd30
fffffe0009b564d0  mov x0, x21
fffffe0009b564d4  mov w1, #0
fffffe0009b564d8  mov w2, #0x1e8
fffffe0009b564dc  mov x4, x24
fffffe0009b564e0  mov x17, x8
fffffe0009b564e4  movk x17, #0xfd0b, lsl #48
fffffe0009b564e8  blraa x26, x17
fffffe0009b564ec  add x8, x28, #0xd38
fffffe0009b564f0  mov x0, x21
fffffe0009b564f4  mov w1, #0
fffffe0009b564f8  mov w2, #0x1e8
fffffe0009b564fc  mov w3, #0xf000000
fffffe0009b56500  mov w4, #0xf000000
fffffe0009b56504  mov w5, #0xee00
fffffe0009b56508  movk w5, #2, lsl #16
fffffe0009b5650c  mov x6, x24
fffffe0009b56510  mov x17, x8
fffffe0009b56514  movk x17, #0x7f, lsl #48
fffffe0009b56518  blraa x22, x17
fffffe0009b5651c  add w24, w24, #1
fffffe0009b56520  ldr w8, [x27]
fffffe0009b56524  cmp w24, w8
fffffe0009b56528  b.lo #0xfffffe0009b564a8
fffffe0009b5652c  cbz w8, #0xfffffe0009b5660c
fffffe0009b56530  mov w24, #0
fffffe0009b56534  ldr x27, [sp, #0x10]
fffffe0009b56538  add x8, x28, #0xd28
fffffe0009b5653c  mov x0, x21
fffffe0009b56540  mov w1, #0
fffffe0009b56544  mov w2, #0x1e8
fffffe0009b56548  mov x3, x24
fffffe0009b5654c  mov x17, x8
fffffe0009b56550  movk x17, #0x73ce, lsl #48
fffffe0009b56554  blraa x25, x17
fffffe0009b56558  and w3, w0, #0xefffffff
fffffe0009b5655c  add x8, x28, #0xd30
fffffe0009b56560  mov x0, x21
fffffe0009b56564  mov w1, #0
fffffe0009b56568  mov w2, #0x1e8
fffffe0009b5656c  mov x4, x24
fffffe0009b56570  mov x17, x8
fffffe0009b56574  movk x17, #0xfd0b, lsl #48
fffffe0009b56578  blraa x26, x17
fffffe0009b5657c  add w24, w24, #1
fffffe0009b56580  ldr w8, [x27]
fffffe0009b56584  cmp w24, w8
fffffe0009b56588  b.lo #0xfffffe0009b56538
fffffe0009b5658c  cmp w8, #1
fffffe0009b56590  b.ls #0xfffffe0009b5660c
fffffe0009b56594  eor w24, w19, #1
fffffe0009b56598  add x8, x28, #0xd28
fffffe0009b5659c  mov x0, x21
fffffe0009b565a0  mov w1, #0
fffffe0009b565a4  mov w2, #0x1e8
fffffe0009b565a8  mov x3, x24
fffffe0009b565ac  mov x17, x8
fffffe0009b565b0  movk x17, #0x73ce, lsl #48
fffffe0009b565b4  blraa x25, x17
fffffe0009b565b8  and w3, w0, #0xfffffff0
fffffe0009b565bc  add x8, x28, #0xd30
fffffe0009b565c0  mov x0, x21
fffffe0009b565c4  mov w1, #0
fffffe0009b565c8  mov w2, #0x1e8
fffffe0009b565cc  mov x4, x24
fffffe0009b565d0  mov x17, x8
fffffe0009b565d4  movk x17, #0xfd0b, lsl #48
fffffe0009b565d8  blraa x26, x17
fffffe0009b565dc  add x8, x28, #0xd38
fffffe0009b565e0  mov x0, x21
fffffe0009b565e4  mov w1, #0
fffffe0009b565e8  mov w2, #0x1e8
fffffe0009b565ec  mov w3, #0xf0
fffffe0009b565f0  mov w4, #0
fffffe0009b565f4  mov w5, #0xee00
fffffe0009b565f8  movk w5, #2, lsl #16
fffffe0009b565fc  mov x6, x24
fffffe0009b56600  mov x17, x8
fffffe0009b56604  movk x17, #0x7f, lsl #48
fffffe0009b56608  blraa x22, x17
fffffe0009b5660c  mov w9, #0
fffffe0009b56610  b #0xfffffe0009b56654
fffffe0009b56614  str w9, [sp, #0xc]
fffffe0009b56618  mov w9, #1
fffffe0009b5661c  str w9, [sp, #0x1c]
fffffe0009b56620  str w8, [sp, #0x2c]
fffffe0009b56624  mov w8, #1
fffffe0009b56628  str w8, [sp, #8]
fffffe0009b5662c  b #0xfffffe0009b55870
fffffe0009b56630  str xzr, [sp, #8]
fffffe0009b56634  str wzr, [sp, #0x2c]
fffffe0009b56638  mov w8, #1
fffffe0009b5663c  stp wzr, w8, [sp, #0x1c]
fffffe0009b56640  ldr w25, [sp, #0x30]
fffffe0009b56644  b #0xfffffe0009b55870
fffffe0009b56648  mov w9, #0
fffffe0009b5664c  mov x23, x20
fffffe0009b56650  ldr w20, [sp, #0x2c]
fffffe0009b56654  ldr w25, [sp, #0x30]
fffffe0009b56658  b #0xfffffe0009b55578
fffffe0009b5665c  bl #0xfffffe0009b713f0
fffffe0009b56660  bl #0xfffffe0009b71434
fffffe0009b56664  bl #0xfffffe0009b712e0
fffffe0009b56668  bl #0xfffffe0009b71324
fffffe0009b5666c  bl #0xfffffe0009b713ac
fffffe0009b56670  bl #0xfffffe0009b71368
fffffe0009b56674  pacibsp 
fffffe0009b56678  stp x22, x21, [sp, #-0x30]!
fffffe0009b5667c  stp x20, x19, [sp, #0x10]
fffffe0009b56680  stp x29, x30, [sp, #0x20]
fffffe0009b56684  add x29, sp, #0x20
fffffe0009b56688  cmp w1, #4
fffffe0009b5668c  b.hs #0xfffffe0009b56718
fffffe0009b56690  mov x21, x3
fffffe0009b56694  mov x20, x2
fffffe0009b56698  mov x19, x0
fffffe0009b5669c  mov w8, #0x8210
fffffe0009b566a0  movk w8, #3, lsl #16
fffffe0009b566a4  add w22, w8, w1, lsl #2
fffffe0009b566a8  mov x1, x22
fffffe0009b566ac  mov w2, #0
fffffe0009b566b0  bl #0xfffffe0009860040
fffffe0009b566b4  and w8, w0, #0x7fffffc0
fffffe0009b566b8  and w8, w8, #0xfcffffff
fffffe0009b566bc  and w9, w21, #0x3f
fffffe0009b566c0  bfi w9, w20, #0x18, #2
fffffe0009b566c4  orr w8, w9, w8
fffffe0009b566c8  orr w2, w8, #0x80000000
fffffe0009b566cc  mov x0, x19
fffffe0009b566d0  mov x1, x22
fffffe0009b566d4  mov w3, #0
fffffe0009b566d8  bl #0xfffffe00098600ac
fffffe0009b566dc  mov x0, x19
fffffe0009b566e0  mov x1, x22
fffffe0009b566e4  mov w2, #0x40000000
fffffe0009b566e8  mov w3, #0
fffffe0009b566ec  mov w4, #0xee00
fffffe0009b566f0  movk w4, #2, lsl #16
fffffe0009b566f4  mov w5, #0
fffffe0009b566f8  ldp x29, x30, [sp, #0x20]
fffffe0009b566fc  ldp x20, x19, [sp, #0x10]
fffffe0009b56700  ldp x22, x21, [sp], #0x30
fffffe0009b56704  autibsp 
fffffe0009b56708  eor x16, x30, x30, lsl #1
fffffe0009b5670c  tbz x16, #0x3e, #0xfffffe0009b56714
fffffe0009b56710  brk #0xc471
fffffe0009b56714  b #0xfffffe000986011c
fffffe0009b56718  bl #0xfffffe0009b71478
fffffe0009b5671c  bti c
fffffe0009b56720  mov w0, #0
fffffe0009b56724  ret 
fffffe0009b56728  pacibsp 
fffffe0009b5672c  stp x20, x19, [sp, #-0x20]!
fffffe0009b56730  stp x29, x30, [sp, #0x10]
fffffe0009b56734  add x29, sp, #0x10
fffffe0009b56738  mov x19, x0
fffffe0009b5673c  add x8, x0, #0x36, lsl #12
fffffe0009b56740  add x20, x8, #0xe6c
fffffe0009b56744  ldrb w8, [x20]
fffffe0009b56748  cbz w8, #0xfffffe0009b56788
fffffe0009b5674c  ldr w2, [x20, #4]
fffffe0009b56750  ldr x16, [x19]
fffffe0009b56754  mov x17, x19
fffffe0009b56758  movk x17, #0xcda1, lsl #48
fffffe0009b5675c  autda x16, x17
fffffe0009b56760  mov x17, #0x9a8
fffffe0009b56764  add x16, x16, x17
fffffe0009b56768  ldr x8, [x16]
fffffe0009b5676c  mov x9, x16
fffffe0009b56770  mov x0, x19
fffffe0009b56774  mov w1, #0
fffffe0009b56778  mov w3, #0
fffffe0009b5677c  mov x17, x9
fffffe0009b56780  movk x17, #0xfd24, lsl #48
fffffe0009b56784  blraa x8, x17
fffffe0009b56788  ldrb w8, [x20, #1]
fffffe0009b5678c  cbz w8, #0xfffffe0009b567e8
fffffe0009b56790  ldr w2, [x20, #8]
fffffe0009b56794  ldr x16, [x19]
fffffe0009b56798  mov x17, x19
fffffe0009b5679c  movk x17, #0xcda1, lsl #48
fffffe0009b567a0  autda x16, x17
fffffe0009b567a4  mov x17, #0x9a8
fffffe0009b567a8  add x16, x16, x17
fffffe0009b567ac  ldr x8, [x16]
fffffe0009b567b0  mov x4, x16
fffffe0009b567b4  mov x16, x8
fffffe0009b567b8  mov x0, x19
fffffe0009b567bc  mov w1, #1
fffffe0009b567c0  mov w3, #0
fffffe0009b567c4  ldp x29, x30, [sp, #0x10]
fffffe0009b567c8  ldp x20, x19, [sp], #0x20
fffffe0009b567cc  autibsp 
fffffe0009b567d0  eor x17, x30, x30, lsl #1
fffffe0009b567d4  tbz x17, #0x3e, #0xfffffe0009b567dc
fffffe0009b567d8  brk #0xc471
fffffe0009b567dc  mov x17, x4
fffffe0009b567e0  movk x17, #0xfd24, lsl #48
fffffe0009b567e4  braa x16, x17
fffffe0009b567e8  ldp x29, x30, [sp, #0x10]
fffffe0009b567ec  ldp x20, x19, [sp], #0x20
fffffe0009b567f0  retab 
fffffe0009b567f4  bti c
fffffe0009b567f8  mov w0, #0x4000
fffffe0009b567fc  ret 
fffffe0009b56800  bti c
fffffe0009b56804  mov w0, #7
fffffe0009b56808  ret 
fffffe0009b5680c  bti c
fffffe0009b56810  ret 
fffffe0009b56814  pacibsp 
