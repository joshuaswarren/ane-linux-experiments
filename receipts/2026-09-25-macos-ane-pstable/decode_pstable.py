#!/usr/bin/env python3
"""Decode pmgr ps words from pstable samples (pmgr-ps.bin = PA 0x28e080000, 0x4040 bytes)."""
import struct
import sys
from pathlib import Path

NAMED = {
    0x218: "afnc0_lw0", 0x260: "ane_sys", 0x2e0: "ane_cpu",
    0x4000: "ane_sys_mpm", 0x4008: "ane_td", 0x4010: "ane_base",
    0x4018: "ane_set1", 0x4020: "ane_set2", 0x4028: "ane_set3", 0x4030: "ane_set4",
}


def fields(w):
    return (f"act={(w >> 4) & 0xf:x} tgt={w & 0xf:x} auto_en={(w >> 28) & 1} "
            f"ps_auto={(w >> 24) & 0xf:x} ps_min={(w >> 16) & 0xf:x} "
            f"b29-31={(w >> 29) & 7:x} devdis={(w >> 10) & 1} parent_off={(w >> 11) & 1}")


d = Path(sys.argv[1])
order = sorted(d.glob("*.pmgr"), key=lambda p: (p.stem.rstrip("0123456789"), int("0" + "".join(c for c in p.stem if c.isdigit()))))
order = [p for k in ("idle", "load", "after") for p in order if p.stem.startswith(k)]
words = {p.stem: struct.unpack(f"<{len(p.read_bytes()) // 4}I", p.read_bytes()) for p in order}
names = [p.stem for p in order]

print("## Named ANE domains (PA 0x28e080000 + off)\n")
print("| off | domain | " + " | ".join(names) + " |")
print("|---|---|" + "---|" * len(names))
for off, nm in NAMED.items():
    print(f"| {off:#x} | {nm} | " + " | ".join(f"{words[n][off // 4]:08x}" for n in names) + " |")

print("\n## Field decode, first idle vs peak load\n")
peak = next((n for n in names if n.startswith("load") and words[n][0x4008 // 4] & 0xf0 == 0xf0
             and words[n][0x2e0 // 4] & 0xf0 == 0xf0), names[-1])
for off, nm in NAMED.items():
    print(f"- {nm}@{off:#x}: idle {words[names[0]][off // 4]:08x} ({fields(words[names[0]][off // 4])}); "
          f"{peak} {words[peak][off // 4]:08x} ({fields(words[peak][off // 4])})")

print("\n## Every other word in the block that changes across samples\n")
n_words = min(len(w) for w in words.values())
for i in range(n_words):
    off = i * 4
    if off in NAMED:
        continue
    vals = [words[n][i] for n in names]
    if len(set(vals)) > 1:
        print(f"- {off:#06x}: " + " ".join(f"{v:08x}" for v in vals))

print("\n## Nonzero ps-shaped words that stay constant (idle == load)\n")
for i in range(n_words):
    off = i * 4
    vals = {words[n][i] for n in names}
    if off not in NAMED and len(vals) == 1 and (v := vals.pop()) and (v & 0x300 or v & 0xff):
        print(f"{off:#06x}={v:08x}", end="  ")
print()
