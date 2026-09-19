#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""H14/W9 fw->host surface scan — bounded pre/post snapshot diff.

After the EP0 HELLO goes out, the driver only watches the i2a pair
(+0x1170000/4, known heartbeat).  This scan snapshots the MBI-adjacent
read surfaces (all read safely on this box in W2/W3/W8) before the
insmod and again after the MGMT session ends, then diffs:

  sudo python3 h14_w9_surface_scan.py pre    # before insmod
  sudo python3 h14_w9_surface_scan.py post   # after session/rmmod decision

Any changed word outside the i2a heartbeat pair is a candidate fw->host
message surface.  Reads only; every write-class address in these windows
was read-only in every prior lane.
"""
import json, mmap, os, struct, sys, time

ANE_BASE = 0x284000000
ENGINE_KILL = (0x285C04000, 0x285C28000)
SCAN_PATH = "/var/tmp/w9-scan-%s.json"

# (name, off_lo, off_hi) inside ANE_BASE, 4-byte steps, end exclusive.
REGIONS = [
    ("tunables", 0x000000, 0x001000),
    ("rvbar",    0x1050000, 0x1050010),
    ("i2a",      0x1170000, 0x1170010),
    ("scratch",  0x1840040, 0x1840070),
    ("doorbell", 0x1844000, 0x1844010),
    ("a2i_rd",   0x184c000, 0x184c010),
    ("a2i_wr",   0x1850000, 0x1850010),
]
HEARTBEAT = {0x1170000, 0x1170004}   # i2a pair: constant ticking, type-0


def klog(ev, **kw):
    line = "H14W9 " + json.dumps({"ev": ev, **kw})
    with open("/dev/kmsg", "w") as k:
        k.write(line + "\n")
    print(line, flush=True)


def check(addr):
    lo, hi = ENGINE_KILL
    assert not (lo <= addr < hi), f"refusing address in kill window: {addr:#x}"


def snapshot():
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    page = 0x1000
    b = ANE_BASE & ~(page - 1)
    m = mmap.mmap(fd, 0x1900000, mmap.MAP_SHARED,
                  mmap.PROT_READ | mmap.PROT_WRITE, offset=b)
    snap = {}
    for name, lo, hi in REGIONS:
        klog("scan.region", name=name,
             addr=f"{ANE_BASE + lo:#x}-{ANE_BASE + hi:#x}", n=(hi - lo) // 4)
        words = []
        for off in range(lo, hi, 4):
            check(ANE_BASE + off)
            words.append(struct.unpack_from("<I", m, off)[0])
        snap[name] = words
    m.close()
    os.close(fd)
    return snap


def main():
    mode = sys.argv[1]
    assert mode in ("pre", "post"), "usage: h14_w9_surface_scan.py pre|post"
    path = SCAN_PATH % mode
    snap = snapshot()
    with open(path, "w") as f:
        json.dump(snap, f)
    klog("scan.saved", mode=mode, path=path)
    if mode != "post":
        return
    with open(SCAN_PATH % "pre") as f:
        pre = json.load(f)
    changes = []
    for name, lo, hi in REGIONS:
        for i, (a, b) in enumerate(zip(pre[name], snap[name])):
            if a != b:
                off = lo + i * 4
                changes.append((name, off, a, b))
    if not changes:
        klog("scan.diff", result="no-changes")
        print("VERDICT: SURFACES_QUIET")
        return
    for name, off, a, b in changes:
        klog("scan.change", region=name, addr=f"{ANE_BASE + off:#x}",
             pre=f"{a:#010x}", post=f"{b:#010x}",
             heartbeat=off in HEARTBEAT)
    n_real = sum(1 for c in changes if c[0] not in HEARTBEAT and
                 not (c[0] == "i2a"))
    print(f"VERDICT: SURFACES_CHANGED total={len(changes)} "
          f"non_heartbeat={n_real}")


if __name__ == "__main__":
    main()
