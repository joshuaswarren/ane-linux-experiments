#!/usr/bin/env python3
"""Read the T6001 ane0 SET0 power-state register. Read-only, zero writes.

Method and address are the ones already established on this host in
receipts/2026-09-13-jw16-set0-read.json and
receipts/2026-09-13-jw16-set0-after-resume.json: readl of physical
0x28e08c000 (m1n1 ps_map[ane0]) through a PROT_READ mmap of /dev/mem.

ACTUAL 0x0 is the gated state that explains doorbell-ok / TM -110; ACTUAL 0xf
is powered. The worker's open of /dev/accel/accel0 resumes the domain through
genpd, so this only ever observes the value. It never writes SET, and in
particular never writes 0xf, which is the prohibited action on this box.
"""
import json
import mmap
import os
import struct
import sys

PHYS = 0x28E08C000
PAGE = 16384


def read_set0():
    base = PHYS & ~(PAGE - 1)
    offset = PHYS - base
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    try:
        region = mmap.mmap(fd, offset + 4, mmap.MAP_SHARED,
                           mmap.PROT_READ, offset=base)
    finally:
        os.close(fd)
    try:
        raw = struct.unpack_from('<I', region, offset)[0]
    finally:
        region.close()
    return raw


def main():
    raw = read_set0()
    print(json.dumps({
        'phys': f'{PHYS:#x}',
        'raw': f'{raw:#010x}',
        'ACTUAL': f'{raw & 0xF:#x}',
        'TARGET': f'{(raw >> 4) & 0xF:#x}',
        'WAS_CLKGATED': bool(raw & (1 << 9)),
        'WAS_PWRGATED': bool(raw & (1 << 8)),
        'powered': (raw & 0xF) == 0xF,
        'writes': 0,
        'prot': 'PROT_READ',
    }))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
