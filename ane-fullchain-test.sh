#!/usr/bin/env bash
# Test the two corrections from eiln's ANE device-tree patch, from userspace.
#
# Source: https://github.com/eiln/linux/commit/bf6651bb55212f2cfab573bd0d49bf5c601b4703
#
# 1. The ANE needs six more PMGR domains that stock Asahi does not describe:
#      ps_ane_base @0xc008   (child of ane_sys_cpu)
#      ps_ane_set1 @0xc010   ps_ane_set2 @0xc018   ps_ane_set3 @0xc020
#      ps_ane_set4 @0xc028   ps_ane_set5 @0xc030   (all children of ane_base)
#    Only 0x470 and 0xc000 were ever raised here, so the task-manager block sat
#    behind an unpowered ane_set domain. That is why engine+0x200 read fine
#    while engine+0x2000c aborted.
#
# 2. The engine window in that patch is 0x26bc04000 size 0x24000, not
#    0x26a000000. Apple's ADT covers the whole ANE region with 32 MiB from
#    0x26a000000; the TM registers sit at offset 0x1c04000 inside it.
#
# Raise the whole chain parent-first, then read TM_TQ_EN at both candidate
# bases. Whichever answers settles the address question too.
#
#   usage: sudo bash ane-fullchain-test.sh [old|new]
set -uo pipefail

BASE_SEL="${1:-new}" python3 - <<'PYEOF'
import mmap, os, struct, time

PMGR   = 0x23B700000
BASES  = {"new": 0x26BC04000, "old": 0x26A000000}
ENGINE = BASES[os.environ.get("BASE_SEL", "new")]
TM     = 0x20000
CHAIN  = [
    ("ps_ane_sys",     0x470),
    ("ps_ane_sys_cpu", 0xC000),
    ("ps_ane_base",    0xC008),
    ("ps_ane_set1",    0xC010),
    ("ps_ane_set2",    0xC018),
    ("ps_ane_set3",    0xC020),
    ("ps_ane_set4",    0xC028),
    ("ps_ane_set5",    0xC030),
]

def say(msg):
    print(msg, flush=True)
    try:
        with open("/dev/kmsg", "w") as fh:
            fh.write(f"ANE_FULLCHAIN: {msg}\n")
    except OSError:
        pass

fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
pm = mmap.mmap(fd, 0x40000, mmap.MAP_SHARED,
               mmap.PROT_READ | mmap.PROT_WRITE, offset=PMGR)

ok = True
for name, off in CHAIN:
    before = struct.unpack("<I", pm[off:off + 4])[0]
    pm[off:off + 4] = struct.pack("<I", (before & ~0xF & ~(1 << 28)) | 0xF)
    actual = None
    for _ in range(200):
        v = struct.unpack("<I", pm[off:off + 4])[0]
        actual = (v >> 4) & 0xF
        if actual == 0xF:
            break
        time.sleep(0.005)
    say(f"{name:<15} @{off:#06x} before={before:#010x} actual={actual:#x}")
    if actual != 0xF:
        ok = False
pm.close()
say("CHAIN_ALL_ACTIVE" if ok else "CHAIN_INCOMPLETE")

os.system("sync")
time.sleep(0.3)
say(f"about to read TM_TQ_EN at {ENGINE + TM + 0xC:#x}")
eng = mmap.mmap(fd, 0x4000, mmap.MAP_SHARED, mmap.PROT_READ, offset=ENGINE + TM)
tq_en = struct.unpack("<I", eng[0x0C:0x10])[0]
status = struct.unpack("<I", eng[0x54:0x58])[0]
committed = struct.unpack("<I", eng[0x44:0x48])[0]
say(f"TM_READ_OK TM_TQ_EN={tq_en:#010x} TM_STATUS={status:#010x} "
    f"TM_COMMITTED={committed:#010x}")
eng.close()

os.close(fd)
say("FULLCHAIN_COMPLETE")
PYEOF
echo "rc=$?"
