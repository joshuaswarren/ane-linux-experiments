#!/usr/bin/env python3
"""H14 W13 read-only prerequisite audit on t6021-test-host. Zero writes.

Whitelist reads only, in the W3-phase1-proven-safe set, valid ONLY while all
eight ANE genpd domains are on (verified via pm_genpd before any MMIO).
Single-shot: one read per address, klog each address BEFORE the access,
abort on any exception, no retries.

Addresses (ANE base 0x284000000, +0x200000000 translation applied):
  pmgr ps words   0x28e0802e0 (ane_cpu), 0x28e084000..0x28e084030 (7 words)
  CPU_CONTROL     0x284000044
  RVBAR           0x285050000  (eng + 0x1050000)
  mailbox file    0x285408110 a2i_control, 0x285408114 i2a_control,
                  0x285408800 a2i_send0, 0x285408830 i2a_recv0
  RTB/VERS region 0x285840000 (VERS), 0x285840048..0x285840064 (SCRATCH0-7)
"""
import mmap
import os
import sys

PAGE = 0x1000
READS = {
    "pmgr_ane_cpu":     0x28E0802E0,
    "pmgr_ane_sys_mpm": 0x28E084000,
    "pmgr_ane_td":      0x28E084008,
    "pmgr_ane_base":    0x28E084010,
    "pmgr_ane_set1":    0x28E084018,
    "pmgr_ane_set2":    0x28E084020,
    "pmgr_ane_set3":    0x28E084028,
    "pmgr_ane_set4":    0x28E084030,
    "cpu_control":      0x284000044,
    "rvbar":            0x285050000,
    "a2i_control":      0x285408110,
    "i2a_control":      0x285408114,
    "a2i_send0":        0x285408800,
    "i2a_recv0":        0x285408830,
    "vers":             0x285840000,
    "scratch0":         0x285840048,
    "scratch7":         0x285840064,
}


def klog(msg):
    with open("/dev/kmsg", "w") as f:
        f.write(f"h14-audit: {msg}\n")


def rd32(fd, addr):
    with mmap.mmap(fd, PAGE, offset=addr & ~0xFFF, access=mmap.ACCESS_READ) as m:
        return int.from_bytes(m[addr & 0xFFF:(addr & 0xFFF) + 4], "little")


def domains_on():
    want = ["ane_cpu", "ane_sys_mpm", "ane_td", "ane_base",
            "ane_set1", "ane_set2", "ane_set3", "ane_set4"]
    states = {}
    with open("/sys/kernel/debug/pm_genpd/pm_genpd_summary") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and parts[0] in want:
                states[parts[0]] = parts[1]
    off = [n for n in want if states.get(n) != "on"]
    return states, off


def main():
    if os.geteuid() != 0:
        print("must run as root", file=sys.stderr)
        return 2
    states, off = domains_on()
    print("genpd:", states)
    if off:
        print(f"ABORT: domains not on: {off} — engine window reads unsafe")
        return 3
    print("all 8 domains on; proceeding with whitelist reads")

    fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    results = {}
    try:
        for name, addr in READS.items():
            klog(f"audit.read.pre addr={addr:#x} name={name}")
            val = rd32(fd, addr)
            results[name] = val
            print(f"{name:16s} {addr:#012x} = {val:#010x}")
            klog(f"audit.read.post addr={addr:#x} val={val:#x}")
    except Exception as e:
        print(f"ABORT: {e}")
        return 4

    print("\n-- gate analysis --")
    rv = results["rvbar"]
    print(f"RVBAR bit0 (released latch): {rv & 1} (W8 read 0x1)")
    cc = results["cpu_control"]
    print(f"CPU_CONTROL RUN bit4: {(cc >> 4) & 1} (W10: 0 = stopped)")
    for n in ("a2i_control", "i2a_control"):
        v = results[n]
        print(f"{n}: {v:#010x} (enable={v & 1}, empty={(v >> 17) & 1}) (W10: 0x00020001)")
    print(f"SCRATCH7: {results['scratch7']:#010x}")
    print(f"VERS: {results['vers']:#010x}")
    print("done; zero writes performed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
