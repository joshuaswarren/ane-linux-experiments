#!/usr/bin/env python3
"""Check fma-out.bin: results[2i] must be +0.0 (NoContraction honored),
results[2i+1] shows whether unconstrained a*b+c was contracted."""
import struct, sys
d = open(sys.argv[1] if len(sys.argv) > 1 else "fma-out.bin", "rb").read()
n = len(d) // 8
p_bad = {}
q_bits = {}
for i in range(n):
    p, q = struct.unpack_from("<2f", d, 8 * i)
    if p != 0.0:
        b = struct.unpack("<I", struct.pack("<f", p))[0]
        p_bad[b] = p_bad.get(b, 0) + 1
    b = struct.unpack("<I", struct.pack("<f", q))[0]
    q_bits[b] = q_bits.get(b, 0) + 1
print("precise-nonzero:", sum(p_bad.values()),
      {hex(k): v for k, v in p_bad.items()})
print("unconstrained:", {hex(k): v for k, v in q_bits.items()})
print("VERDICT:", "NoContraction VIOLATED (precise fused)" if p_bad
      else "NoContraction honored")
