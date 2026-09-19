; ANEFWRpcMsg_create_real [0xfffffe00095a6d6c-0xfffffe00095a6db8) 0x4c bytes
0xfffffe00095a6d6c: bti      c
0xfffffe00095a6d70: pacibsp  
0xfffffe00095a6d74: stp      x29, x30, [sp, #-0x10]!
0xfffffe00095a6d78: mov      x29, sp
0xfffffe00095a6d7c: adrp     x1, #0xfffffe00074be000
0xfffffe00095a6d80: add      x1, x1, #0xb02
0xfffffe00095a6d84: adrp     x2, #0xfffffe000cb6d000
0xfffffe00095a6d88: add      x2, x2, #0x9b8
0xfffffe00095a6d8c: mov      w3, #0x58
0xfffffe00095a6d90: bl       #0xfffffe000964ba28
0xfffffe00095a6d94: adrp     x16, #0xfffffe0008144000
0xfffffe00095a6d98: add      x16, x16, #0xbe0
0xfffffe00095a6d9c: add      x16, x16, #0x10
0xfffffe00095a6da0: mov      x17, x0
0xfffffe00095a6da4: movk     x17, #0xcda1, lsl #48
0xfffffe00095a6da8: pacda    x16, x17
0xfffffe00095a6dac: str      x16, [x0]
0xfffffe00095a6db0: ldp      x29, x30, [sp], #0x10
0xfffffe00095a6db4: retab    