import ctypes, time, hashlib
import numpy as np
lib = ctypes.CDLL("/var/tmp/encwall-decomp/libane_tile512.so", use_errno=True)
P = ctypes.c_void_p
init = lib.__ane_init; init.restype=P; init.argtypes=[ctypes.c_char_p, ctypes.c_int]
free = lib.__ane_free; free.restype=ctypes.c_int; free.argtypes=[P]
src_size = lib.__ane_src_size; src_size.restype=ctypes.c_uint64; src_size.argtypes=[P,ctypes.c_uint32]
dst_size = lib.__ane_dst_size; dst_size.restype=ctypes.c_uint64; dst_size.argtypes=[P,ctypes.c_uint32]
send = lib.__ane_send; send.restype=None; send.argtypes=[P,P,ctypes.c_uint32]
read = lib.__ane_read; read.restype=None; read.argtypes=[P,P,ctypes.c_uint32]
ex = lib.ane_exec; ex.restype=ctypes.c_int; ex.argtypes=[P]
h = init(b"/var/tmp/encoder-fp16-v3.anec", 0)
sin=[src_size(h,i) for i in range(2)]; sout=[dst_size(h,i) for i in range(2)]
feat=np.load("/var/tmp/feat-f16.npy").reshape(3000,128).tobytes()
mask=np.load("/var/tmp/mask-f16.npy").reshape(3000).tobytes()
inb=[ctypes.create_string_buffer(s) for s in sin]
outb=[ctypes.create_string_buffer(s) for s in sout]
ctypes.memmove(inb[0], mask, len(mask))
ctypes.memmove(inb[1], feat, len(feat))
gold=np.load("/var/tmp/gold-f16.npy").astype(np.float16)
times=[]; hashes=set()
for it in range(20):
    t0=time.perf_counter()
    send(h,inb[0],0); send(h,inb[1],1)
    rc=ex(h)
    read(h,outb[0],0); read(h,outb[1],1)
    times.append((time.perf_counter()-t0)*1e3)
    hashes.add(hashlib.sha256(outb[0].raw[:480000]).hexdigest()[:16])
    if rc: break
o=np.frombuffer(outb[0].raw,dtype=np.float16)[:480000]
print("rc=",rc,"iters=20")
ts=sorted(times); print("submit wall ms: min=%.1f p50=%.1f p90=%.1f max=%.1f"%(ts[0],ts[10],ts[18],ts[-1]))
print("byte-identical across reps:", len(hashes)==1, list(hashes))
print("hidden bytes == gold bytes:", o.tobytes()==gold.tobytes())
m=np.frombuffer(outb[1].raw,dtype=np.float16)
print("outmask first8:",m[:8].tolist(),"nz:",int(np.count_nonzero(m[:750])), "of 750")
try: free(h)
except Exception: pass
