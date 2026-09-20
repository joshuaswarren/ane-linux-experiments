#!/usr/bin/env python3
"""Executable integer assertions for every hex-arithmetic claim in the
rvbar-lifecycle receipt (pass11 correction, Main directive 2026-09-20).

Run: python3 tools/check_vm_window.py
Fails (exit 1) on any arithmetic or window-membership regression.
"""
import sys

STAGED_FW_DVA = 0x3FFFF800000          # Linux staged firmware surface DVA
DART_ANE0_VM_BASE = 0x10000000000      # ADT dart-ane0 vm-base (1 TiB)
DART_ANE0_VM_SIZE = 0x30000000000      # ADT dart-ane0 vm-size (3 TiB)
RVBAR_FOLD_MASK = 0xFF7EFFFFFFFFF800   # bits the RVBAR fold DROPS

failures = []


def chk(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond:
        failures.append(name)


vm_end = DART_ANE0_VM_BASE + DART_ANE0_VM_SIZE
chk('vm_end = vm_base + vm_size = 0x40000000000 (4 TiB)',
    vm_end == 0x40000000000)
chk('vm_size = 3 TiB (0x30000000000)', DART_ANE0_VM_SIZE == 3 * 2**40)
chk('staged 0x3ffff800000 = 4 TiB - 8 MiB (0x800000)',
    STAGED_FW_DVA == 0x40000000000 - 0x800000)
chk('staged INSIDE dart-ane0 window (>= vm_base)',
    STAGED_FW_DVA >= DART_ANE0_VM_BASE)
chk('staged INSIDE dart-ane0 window (< vm_end)',
    STAGED_FW_DVA < vm_end)
chk('fold retention: staged & ~fold_mask == 0',
    (STAGED_FW_DVA & ~RVBAR_FOLD_MASK & ((1 << 64) - 1)) == 0)
chk('fold compose round-trip: entry bits == staged',
    (0x0081000000000001 | (STAGED_FW_DVA & RVBAR_FOLD_MASK)) & RVBAR_FOLD_MASK
    == STAGED_FW_DVA)

# Latched-entry window membership (value from the owner's live read64 —
# update LATCHED_ENTRY when the owner posts the exact bits).
LATCHED_ENTRY = None  # e.g. 0x1FFF8000000 — set from the live read
if LATCHED_ENTRY is not None:
    chk('latched entry INSIDE dart-ane0 window',
        DART_ANE0_VM_BASE <= LATCHED_ENTRY < vm_end)
    chk('latched entry fold-retention clean',
        (LATCHED_ENTRY & ~RVBAR_FOLD_MASK & ((1 << 64) - 1)) == 0)
else:
    print('SKIP latched-entry checks (owner read64 value not yet provided)')

print('ALL OK' if not failures else f'{len(failures)} FAILED')
sys.exit(0 if not failures else 1)

# --- ps differential (Main-directed retraction addendum) ---
W8_CPU_PS = 0x1F0003FF   # w8-run.out: ane_cpu proven-working word
A3_CPU_PS = 0x0F0001FF   # attempt-3 stalled word (owner capture)
_xor = W8_CPU_PS ^ A3_CPU_PS
chk('ps xor W8^A3 = 0x10000200 (bit9 + bit28 only)', _xor == 0x10000200)
chk('missing in A3 = {9, 28} (NOT bit20)',
    [b for b in range(32) if (W8_CPU_PS >> b) & 1 and not (A3_CPU_PS >> b) & 1] == [9, 28])
print('W8 bits:', [b for b in range(32) if (W8_CPU_PS >> b) & 1])
print('A3 bits:', [b for b in range(32) if (A3_CPU_PS >> b) & 1])
