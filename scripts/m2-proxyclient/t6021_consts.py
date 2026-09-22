#!/usr/bin/env python3
"""T6021 (m2-host, J414c M2 Max) ANE ASC bring-up constants.

Sources (do not edit by hand — re-derive with tools/ane-hunter):
  - ADT capture ~/var/tmp/m2-macos-capture-20260921/ane0-dt.txt (ane0@84000000
    32 MiB, dart-ane0@85800000 dart,t8110 4 windows, page-size 0x400000)
  - tools/ane-hunter/driver_consts.py selftest (engine 0x284000000,
    TM engine+0x1C00000)
  - KC ANE_Init chain, NIGHT-SUMMARY 2026-09-21 §3 (RVBAR 0x285050000,
    CPUCTL 0x285400044, SCRATCH7 0x285840064, READY 0x08042006, wake
    0xF7FBDFF9) and §4 (RVBAR = 0x0081000000000001 | (DVA & 0xff7eFFFFFFFFFF80);
    target DVA 0x10000000000 -> RVBAR 0x0081010000000001)
  - m1n1 proxyclient m1n1/hw/ane.py (RVBAR +0x1050000, SCRATCH/GPIO cells
    0x1840000..0x1840064), m1n1/hw/asc.py (CPU_CONTROL +0x44, mailbox)

All addresses are CPU-physical as seen from m1n1 stage 1.
"""
import os
import re
import struct
import sys

CPU_PHYS_OFFSET = 0x200000000

# --- engine + ASC block (ane0 reg window 0: die-local 0x84000000, 32 MiB) ---
ENGINE_BASE = 0x84000000 + CPU_PHYS_OFFSET          # 0x284000000
ENGINE_SIZE = 0x2000000

# ASC control block: kext field [dev+0x4A0] = 0x01400044 -> block at +0x1400000;
# on-box s22/s23 used CPUCTL = 0x285400044 = engine+0x1400044
ASC_BLOCK = ENGINE_BASE + 0x1400000                 # 0x285400000
ASC_CPU_CONTROL = ASC_BLOCK + 0x0044                # 0x285400044, RUN = bit4
ASC_CPU_STATUS = ASC_BLOCK + 0x0048                 # 0x285400048, STOPPED = bit1
ASC_INBOX_CTRL = ASC_BLOCK + 0x8110
ASC_OUTBOX_CTRL = ASC_BLOCK + 0x8114
ASC_INBOX0 = ASC_BLOCK + 0x8800                     # 64-bit
ASC_INBOX1 = ASC_BLOCK + 0x8808
ASC_OUTBOX0 = ASC_BLOCK + 0x8830
ASC_OUTBOX1 = ASC_BLOCK + 0x8838

ASC_RVBAR = ENGINE_BASE + 0x1050000                 # 0x285050000, write64
CPU_CONTROL = ASC_CPU_CONTROL                       # kext name, same register
SCRATCH7 = ENGINE_BASE + 0x1840064                  # 0x285840064 poll cell
SCRATCH6 = ENGINE_BASE + 0x1840060
SCRATCH0 = ENGINE_BASE + 0x1840000                  # fw addr lo after publish
SCRATCH1 = ENGINE_BASE + 0x1840004                  # fw addr hi

READY_MAGIC = 0x08042006                            # SCRATCH7 READY
WAKE_MAGIC = 0xF7FBDFF9                             # kext publish-wake word

# RVBAR mode-bit composition (kext): RVBAR = MODE | (DVA & MASK).
# The latched iBoot value on this box is 0x10000000001 — DVA present
# (DVA 0x10000000000), mode bits 0x0081<<48 MISSING. s23 proved live writes
# are ignored while latched, so mode bits must be in place before RUN.
RVBAR_MODE = 0x0081000000000001
RVBAR_MODE_HI = 0x0081000000000000  # bits 55+48 (the missing mode bits)
RVBAR_DVA_MASK = 0xFF7EFFFFFFFFFF80
FW_DVA = 0x10000000000                              # ASC fetch aperture (s13/s18)
VM_BASE = 0x10000                                   # dart-ane0 ADT vm-base
VM_SIZE = 0x30000

def rvbar_value(dva=FW_DVA):
    """Kext formula; rvbar_value() == 0x0081010000000001 for the fw DVA."""
    return RVBAR_MODE | (dva & RVBAR_DVA_MASK)

# --- dart-ane0 (dart,t8110; die-local 0x85800000 + cpu offset) ---
DART_BASE = 0x85800000 + CPU_PHYS_OFFSET            # 0x285800000
DART_PATH = "/arm-io/dart-ane0"
ANE_PATH = "/arm-io/ane"
DART_SID = 0
DART_PAGE_SIZE = 0x400000

FW_NAME = "selene"
POLL_INTERVAL = 0.001                               # kext polls 1 ms
POLL_A_MAX = 1000                                   # Poll A: <=1000 x 1 ms (READY)
POLL_B_MAX = 1000                                   # Poll B (wake ack)
CMD_TIMEOUT = 5                                   # every proxy roundtrip bounded

ADT_CAPTURE = os.path.expanduser(
    "~/var/tmp/m2-macos-capture-20260921/ane0-dt.txt")


def _adt_ane0_reg(txt):
    """First ane0 'reg' from the ioreg IODeviceTree dump.

    ioreg prints plist 32-bit words little-endian; the ADT stores u64 pairs.
    Returns (die_local_base, size).
    """
    sec = txt[txt.find('"name" = <"ane0">'):]
    m = re.search(r'"reg" = <([0-9a-f]+)>', sec)
    if not m:
        return None, None
    raw = bytes.fromhex(m.group(1))
    words = struct.unpack("<%dI" % (len(raw) // 4), raw)
    base = words[0] | (words[1] << 32)
    size = words[2] | (words[3] << 32)
    return base, size


def validate(verbose=False):
    """Cross-check arithmetic against the hunter constants + ADT capture."""
    notes = []
    ok = True

    def need(cond, msg):
        nonlocal ok
        notes.append(("OK   " if cond else "FAIL ") + msg)
        if not cond:
            ok = False

    need(ENGINE_BASE == 0x284000000, "engine base 0x284000000")
    need(ENGINE_SIZE == 0x2000000, "engine size 32 MiB")
    need(ASC_RVBAR == 0x285050000, "RVBAR 0x285050000 == engine+0x1050000")
    need(CPU_CONTROL == 0x285400044,
         "CPU_CONTROL 0x285400044 == ASC block 0x285400000 + 0x44 (s22 on-box)")
    need(SCRATCH7 == 0x285840064, "SCRATCH7 0x285840064 == engine+0x1840064")
    need(SCRATCH6 == 0x285840060, "SCRATCH6 0x285840060")
    need(ENGINE_BASE + 0x1C00000 == 0x285C00000,
         "TM block engine+0x1C00000 == 0x285C00000 (hunter)")
    need(ENGINE_BASE + 0x1C20400 == 0x285C20400,
         "desc addr engine+0x1C20400 == 0x285C20400 (hunter)")
    need(DART_BASE == 0x285800000, "dart-ane0 base 0x285800000")

    need(rvbar_value() == 0x0081010000000001,
         "rvbar(fw DVA) == 0x0081010000000001 (night-summary target)")
    need(rvbar_value(FW_DVA) ^ RVBAR_MODE == 0x0000010000000000,
         "latched 0x10000000001 == DVA part + enable bit; mode bits add 0x0081<<48")

    if os.path.exists(ADT_CAPTURE):
        txt = open(ADT_CAPTURE, errors="replace").read()
        for needle in ('"name" = <"ane0">', '"name" = <"dart-ane0">',
                       "dart,t8110", "ane,t8020", '"pre-loaded" = <01000000>'):
            need(needle in txt, f"ADT contains {needle}")
        base, size = _adt_ane0_reg(txt)
        need(base == 0x84000000, f"ADT ane0 window0 base 0x{base:x} == 0x84000000")
        need(size == 0x2000000, f"ADT ane0 window0 size 0x{size:x} == 0x2000000")
    else:
        notes.append("SKIP  ADT capture not present at " + ADT_CAPTURE)

    if verbose:
        print("\n".join(notes))
    return ok, notes


if __name__ == "__main__":
    good, notes = validate(verbose=True)
    print("VALIDATION", "PASS" if good else "FAIL")
    sys.exit(0 if good else 1)
