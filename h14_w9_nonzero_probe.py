#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""H14/W9 nonzero-write probe — closes the W8 confound.

W8 wrote SCRATCH (GPIO0, +0x1840048) with its own readback 0x0: the write
transaction was accepted (no SError), but "accepted, latched" cannot be
distinguished from "accepted, discarded" by an identity write.  This probe
runs AFTER the W8 grant sequence on the same boot and writes real nonzero
values, verifying each readback, then restores the W8-end state (0x0).

Run on jw14m2-linux as root, after h14_write_grant_test.py:
  sudo python3 h14_w9_nonzero_probe.py
"""
import json, mmap, os, struct, sys

ANE_BASE = 0x284000000
ENGINE_KILL = (0x285C04000, 0x285C28000)
SCRATCH = ANE_BASE + 0x1840048   # GPIO0, W8-proven writable surface

PROBE_VALUES = (0xA5A5A5A5, 0x5A5A5A5A, 0x0)   # last one restores W8-end state


def klog(ev, **kw):
    line = "H14W9 " + json.dumps({"ev": ev, **kw})
    with open("/dev/kmsg", "w") as k:
        k.write(line + "\n")
    print(line, flush=True)


def check(addr):
    lo, hi = ENGINE_KILL
    assert not (lo <= addr < hi), f"refusing address in kill window: {addr:#x}"


class DevMem:
    def __init__(self):
        self.fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        self.maps = {}

    def window(self, base, size):
        page = 0x1000
        b = base & ~(page - 1)
        e = (base + size + page - 1) & ~(page - 1)
        m = mmap.mmap(self.fd, e - b, mmap.MAP_SHARED,
                      mmap.PROT_READ | mmap.PROT_WRITE, offset=b)
        return m, base - b

    def rd32(self, m, delta, addr):
        check(addr)
        return struct.unpack_from("<I", m, delta + (addr - ANE_BASE))[0]

    def wr32(self, m, delta, addr, val):
        check(addr)
        struct.pack_into("<I", m, delta + (addr - ANE_BASE), val)


def main():
    d = DevMem()
    m, delta = d.window(ANE_BASE, 0x1900000)
    ok = True
    for val in PROBE_VALUES:
        klog("probe.pre", addr=f"{SCRATCH:#x}", val=f"{val:#010x}")
        d.wr32(m, delta, SCRATCH, val)
        rb = d.rd32(m, delta, SCRATCH)
        match = rb == val
        klog("probe.readback", addr=f"{SCRATCH:#x}", val=f"{val:#010x}",
             rb=f"{rb:#010x}", match=match)
        if not match and val:
            ok = False
    print("VERDICT: NONZERO_LATCH_OK" if ok else "VERDICT: LATCH_FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
