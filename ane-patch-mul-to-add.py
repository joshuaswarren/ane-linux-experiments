#!/usr/bin/env python3
"""Patch an ANEC MUL graph's task registers into ADD without recompiling."""
import struct
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
data = bytearray(source.read_bytes())
task_offset = 0x1000
pe_offset = task_offset + 0x22c
mac_offset = task_offset + 0x244
pe_value = struct.unpack_from('<I', data, pe_offset)[0]
mac_value = struct.unpack_from('<I', data, mac_offset)[0]
print(f'before_pe=0x{pe_value:08x} before_mac=0x{mac_value:08x}')
if pe_value != 0x00080004 or mac_value not in (0x00000000, 0x00000030):
    raise SystemExit('unexpected MUL register values')
struct.pack_into('<I', data, pe_offset, 0x00080000)
struct.pack_into('<I', data, mac_offset, 0x00000000)
target.write_bytes(data)
print('MUL_TO_ADD_PATCHED')
