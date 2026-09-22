#!/usr/bin/env python3
"""Whole-encoder exec attempt with errno capture. Fresh process per attempt."""
import ctypes, time
import numpy as np
lib = ctypes.CDLL("/var/tmp/encwall-decomp/libane_tile512.so", use_errno=True)
P = ctypes.c_void_p
init = lib.__ane_init; init.restype = P; init.argtypes = [ctypes.c_char_p, ctypes.c_int]
free = lib.__ane_free; free.restype = ctypes.c_int; free.argtypes = [P]
src_size = lib.__ane_src_size; src_size.restype = ctypes.c_uint64; src_size.argtypes = [P, ctypes.c_uint32]
dst_size = lib.__ane_dst_size; dst_size.restype = ctypes.c_uint64; dst_size.argtypes = [P, ctypes.c_uint32]
send = lib.__ane_send; send.restype = None; send.argtypes = [P, P, ctypes.c_uint32]
read = lib.__ane_read; read.restype = None; read.argtypes = [P, P, ctypes.c_uint32]
ex = lib.ane_exec; ex.restype = ctypes.c_int; ex.argtypes = [P]

h = init(b"/var/tmp/encoder-fp16.anec", 0)
if not h: raise SystemExit("ane_init refused")
sin = [src_size(h,i) for i in range(2)]
sout = [dst_size(h,i) for i in range(2)]
print("surfaces in:", sin, "out:", sout, flush=True)
feat = np.load("/var/tmp/feat-f16.npy").reshape(3000,128)
mask = np.load("/var/tmp/mask-f16.npy").reshape(3000)
inb = [ctypes.create_string_buffer(s) for s in sin]
outb = [ctypes.create_string_buffer(s) for s in sout]
fb = feat.tobytes(); mb = mask.tobytes()
ctypes.memmove(inb[0], fb, len(fb))
st1 = sin[1]//3000
for r in range(3000):
    ctypes.memmove(ctypes.byref(inb[1], r*st1), mb[r*2:(r+1)*2], 2)
t0 = time.perf_counter()
send(h, inb[0], 0); send(h, inb[1], 1)
t1 = time.perf_counter()
rc = ex(h)
err = ctypes.get_errno()
t2 = time.perf_counter()
read(h, outb[0], 0); read(h, outb[1], 1)
print(f"exec rc={rc} errno={err} send={1e3*(t1-t0):.1f}ms exec={1e3*(t2-t1):.1f}ms", flush=True)
o0 = np.frombuffer(outb[0].raw, dtype=np.float16)
print("out0 nonzero frac:", float(np.count_nonzero(o0))/len(o0))
print("out0 first16:", o0[:16].tolist())
gold = np.load("/var/tmp/gold-f16.npy").astype(np.float32).ravel()
v = o0[:len(gold)].astype(np.float32)
d = np.abs(v-gold)
print(f"vs gold: max_abs={d.max():.4f} mean_abs={d.mean():.4f} frac_close={float(np.mean(d<=0.02+0.02*np.abs(gold))):.4f}")
try:
    free(h)
    print("free ok")
except Exception as e:
    print("free error (ignored):", e)
