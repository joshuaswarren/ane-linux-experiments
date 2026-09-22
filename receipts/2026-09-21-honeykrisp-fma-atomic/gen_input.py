#!/usr/bin/env python3
"""Generate fma-in.bin: duplicated float triples for fma_contract.comp v2."""
import struct, sys
n = int(sys.argv[1]) if len(sys.argv) > 1 else 65536
trip = struct.pack("<3f", 1.0 + 2.0**-23, 1.0 - 2.0**-23, -1.0)
with open(sys.argv[2] if len(sys.argv) > 2 else "fma-in.bin", "wb") as f:
    for _ in range(n):
        f.write(trip * 2)
