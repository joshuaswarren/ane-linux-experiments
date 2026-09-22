#!/usr/bin/env python3
"""Check high-pressure atomicOr output (atomic_lane_hi.comp)."""
import struct, sys
d = open(sys.argv[1] if len(sys.argv) > 1 else "atomic-hi.bin", "rb").read()
words = len(d) // 4
bad = []
for w in range(words):
    i0, i1 = 2 * w, 2 * w + 1
    e = (((0x0400 + ((i1 >> 2) & 0x3FFF)) << 16) | (0x0400 + ((i0 >> 2) & 0x3FFF)))
    if struct.unpack_from("<I", d, 4 * w)[0] != e:
        bad.append(w)
print("hi-pressure words:", words, "bad:", len(bad), bad[:5])
