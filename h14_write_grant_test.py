#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""H14/W8 write-grant live test — m1n1 apply_static_tunables() on t6021.

Hypothesis (W7): the ANE control aperture 0x284000000 rejects host writes
(async external abort 0xbe000000) until m1n1's static-tunable sequence is
applied, led by base+0x0 <- 0x10.

Sequence: ps-raise (phase-1 proven eight-word RMW) -> tunables -> SCRATCH
(+0x1840048) read/write probe.

EVERY address is logged to /dev/kmsg (netconsole-carried) BEFORE the access
and the log fd is closed before the MMIO, so a freeze pins the exact word.

Run on jw14m2-linux:  sudo python3 h14_write_grant_test.py
"""
import json, mmap, os, struct, sys, time

ANE_BASE = 0x284000000
PMGR_BASE = 0x28E080000
PMGR_SPAN = 0x8000
ENGINE_KILL = (0x285C04000, 0x285C28000)
SCRATCH = ANE_BASE + 0x1840048   # GPIO0, "for acks w/ rtkit" (m1n1 hw/ane.py)

# m1n1 fw/ane.py apply_static_tunables(), verbatim order.
TUNABLES = [
    (0x0,   0x10),        # the hypothesized write-grant unlock
    (0x38,  0x50020),
    (0x3c,  0xa0030),
    (0x400, 0x40010001),
    (0x600, 0x1ffffff),
    (0x738, 0x200020),    # PMGR1 alias inside ANE block
    (0x798, 0x100030),    # PMGR2
    (0x7f8, 0x100000a),   # PMGR3
    (0x900, 0x101),
    (0x410, 0x1100),
    (0x420, 0x1100),
    (0x430, 0x1100),
]

PS_CHAIN = [
    ("ane_sys_mpm", 0x4000), ("ane_td", 0x4008), ("ane_base", 0x4010),
    ("ane_set1", 0x4018), ("ane_set2", 0x4020), ("ane_set3", 0x4028),
    ("ane_set4", 0x4030), ("ane_cpu", 0x2E0),
]
PS_TARGET_MASK = 0xF
PS_ACTUAL_MASK = 0xF0
PS_CLEAR = (1 << 31) | (1 << 28) | (0xF << 24) | (0xF << 16) | (1 << 12) | (1 << 10) | PS_TARGET_MASK
PS_ACTIVE = 0xF


def klog(ev, **kw):
    line = "H14W8 " + json.dumps({"ev": ev, **kw})
    try:
        with open("/dev/kmsg", "w") as f:
            f.write(line + "\n")
    except OSError as e:
        print(f"klog failed: {e}", file=sys.stderr)
    print(line, flush=True)


def check(addr):
    lo, hi = ENGINE_KILL
    assert not (lo <= addr < hi), f"refusing address in kill window: {addr:#x}"


class DevMem:
    def __init__(self):
        self.fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        self.maps = {}

    def window(self, base, size):
        key = (base, size)
        if key not in self.maps:
            page = 0x1000
            b = base & ~(page - 1)
            e = (base + size + page - 1) & ~(page - 1)
            m = mmap.mmap(self.fd, e - b, mmap.MAP_SHARED,
                          mmap.PROT_READ | mmap.PROT_WRITE, offset=b)
            self.maps[key] = (m, b, base - b)
        m, b, delta = self.maps[key]
        return m, delta

    def rd32(self, addr):
        check(addr)
        for (base, size) in list(self.maps):
            if base <= addr < base + size:
                m, b, delta = self.maps[(base, size)]
                return struct.unpack_from("<I", m, delta + (addr - base))[0]
        raise KeyError(f"address {addr:#x} outside mapped windows")

    def wr32(self, addr, val):
        check(addr)
        for (base, size) in list(self.maps):
            if base <= addr < base + size:
                m, b, delta = self.maps[(base, size)]
                struct.pack_into("<I", m, delta + (addr - base), val)
                return
        raise KeyError(f"address {addr:#x} outside mapped windows")


def ps_raise(d):
    m, delta = d.window(PMGR_BASE, PMGR_SPAN)
    for name, off in PS_CHAIN:
        reg = PMGR_BASE + off
        v = struct.unpack_from("<I", m, delta + off)[0]
        klog("ps.raise", name=name, addr=f"{reg:#x}", old=f"{v:#010x}")
        if (v & PS_ACTUAL_MASK) >> 4 == PS_ACTIVE and (v & 0x800) == 0:
            klog("ps.raise.already", name=name, val=f"{v:#010x}")
            continue
        nv = (v & ~PS_CLEAR) | PS_ACTIVE
        struct.pack_into("<I", m, delta + off, nv)
        deadline = time.time() + 0.5
        while time.time() < deadline:
            cur = struct.unpack_from("<I", m, delta + off)[0]
            if (cur & PS_ACTUAL_MASK) >> 4 == PS_ACTIVE and (cur & 0x800) == 0:
                break
            time.sleep(0.001)
        else:
            klog("ps.raise.TIMEOUT", name=name, val=f"{cur:#010x}")
            sys.exit(2)
        klog("ps.raise.ok", name=name, val=f"{cur:#010x}")


def main():
    d = DevMem()
    d.window(ANE_BASE, 0x1900000)   # covers tunables + +0x1840048; stops well before DART
    m, delta = d.window(PMGR_BASE, PMGR_SPAN)

    klog("run.begin", tunables=len(TUNABLES))

    # sanity read (reads are proven safe): RVBAR bit0
    rvbar = d.rd32(ANE_BASE + 0x1050000)
    klog("rvbar.read", addr=f"{ANE_BASE + 0x1050000:#x}", val=f"{rvbar:#010x}", bit0=rvbar & 1)

    ps_raise(d)

    # THE TEST: m1n1 static tunables, exact order, pre-logged.
    for i, (off, val) in enumerate(TUNABLES):
        addr = ANE_BASE + off
        klog("tunable.pre", i=i, addr=f"{addr:#x}", val=f"{val:#010x}")
        d.wr32(addr, val)
        rb = d.rd32(addr)
        klog("tunable.post", i=i, addr=f"{addr:#x}", readback=f"{rb:#010x}",
             match=rb == val)

    # SCRATCH probe: read (safe), then write the readback value back.
    klog("scratch.read.pre", addr=f"{SCRATCH:#x}")
    sv = d.rd32(SCRATCH)
    klog("scratch.read.ok", val=f"{sv:#010x}")
    klog("scratch.write.pre", addr=f"{SCRATCH:#x}", val=f"{sv:#010x}")
    d.wr32(SCRATCH, sv)
    rb = d.rd32(SCRATCH)
    klog("scratch.write.ok", readback=f"{rb:#010x}")

    klog("verdict", result="APERTURE_UNLOCKED",
         detail="all tunable writes + SCRATCH write completed without abort")
    print("VERDICT: APERTURE_UNLOCKED")


if __name__ == "__main__":
    main()
