#!/usr/bin/env python3
"""Summarize one aneregdump output dir (index.json + <range>.bin files).

Prints the words the Linux bring-up compares against: ps gate words, VENC ps,
ASC wrapper CPU_CONTROL/CPU_STATUS/IRQ masks, RVBAR, SCRATCH, mailbox
controls, DART TCR/TTBR/ENABLE per stream, firmware segment heads, boot-args.
Linux reference values come from the lane receipts (2026-09-25-m2-handshake).
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

LINUX = {
    "CPU_STATUS": "0x28 parked after RUN (0x2a before)",
    "RVBAR": "0x0000010000000001 (locked, no 0x81 mode bits)",
    "A2I_CTRL": "0x00020001",
    "SCRATCH7": "0x00000000 (no READY)",
    "DART TTBR": "0x1000e055 on all three (equalized run)",
}


def words(b, n=None):
    n = len(b) // 4 if n is None else n
    return struct.unpack(f"<{n}I", b[: n * 4])


def main(d):
    d = Path(d)
    idx = json.loads((d / "index.json").read_text())
    print(f"# {d.name}: islands_up={idx['islands_up']} poll_iters={idx.get('poll_iters')} "
          f"poll_us={idx.get('poll_us')} ps_actual={idx.get('ps_actual')}")
    st = {r["name"]: r for r in idx["ranges"]}
    print("ranges: " + ", ".join(f"{n}={r['status']}/{r['len']}" for n, r in st.items()))

    def rng(name):
        p = d / f"{name}.bin"
        return p.read_bytes() if p.exists() and st.get(name, {}).get("status") == "ok" else None

    if (b := rng("pmgr-ps")):
        w = words(b)
        print("pmgr: " + " ".join(f"{n}={w[o // 4]:08x}" for n, o in
              (("ane_sys", 0x260), ("ane_cpu", 0x2e0), ("mpm", 0x4000), ("td", 0x4008),
               ("base", 0x4010), ("set1", 0x4018), ("set4", 0x4030))))
    if (b := rng("venc-sys-ps")):
        print("venc-sys-ps 0x2902803c0: " + " ".join(f"{x:08x}" for x in words(b)) +
              f"  (VENC_SYS @+0x20 = {words(b)[8]:08x}; Linux after raise 1f0003ff)")
    if (b := rng("venc-dma-ps")):
        w = words(b)
        print(f"venc-dma-ps: DMA={w[0]:08x} PIPE4={w[2]:08x} PIPE5={w[4]:08x} ME0={w[6]:08x} ME1={w[8]:08x}")
    if (b := rng("wrapper")):
        w = words(b)
        print(f"wrapper: CPU_CONTROL={w[0x44 // 4]:08x} CPU_STATUS={w[0x48 // 4]:08x} "
              f"(Linux {LINUX['CPU_STATUS']}) IRQ-mask a00..a14=" +
              " ".join(f"{w[o // 4]:08x}" for o in range(0xa00, 0xa18, 4)))
        nz = [(i * 4, v) for i, v in enumerate(w) if v not in (0, 0xdead)]
        print(f"wrapper nonzero words: {len(nz)}; first 24: " +
              " ".join(f"+{o:#x}={v:08x}" for o, v in nz[:24]))
    if (b := rng("rvbar")):
        print(f"RVBAR={struct.unpack('<Q', b[:8])[0]:#018x} (Linux {LINUX['RVBAR']})")
    if (b := rng("scratch")):
        w = words(b)
        print("SCRATCH0-9=" + " ".join(f"{x:08x}" for x in w) + f"  (Linux SCRATCH7 {LINUX['SCRATCH7']})")
    if (b := rng("mailbox")):
        w = words(b)
        print(f"mailbox: A2I_CTRL={w[0x110 // 4]:08x} I2A_CTRL={w[0x114 // 4]:08x} (Linux A2I {LINUX['A2I_CTRL']})")
    for n in ("dart0", "dart1", "dart2"):
        if (b := rng(n)):
            w = words(b)
            en = [w[(0xc00 + 4 * i) // 4] for i in range(4)]
            live = [(s, w[(0x1000 + 4 * s) // 4], w[(0x1400 + 4 * s) // 4]) for s in range(16)
                    if w[(0x1000 + 4 * s) // 4] or w[(0x1400 + 4 * s) // 4]]
            print(f"{n}: ENABLE={' '.join(f'{x:08x}' for x in en)} PROTECT={w[0x200 // 4]:08x} "
                  f"ERROR={w[0x100 // 4]:08x} live SIDs: " +
                  (" ".join(f"sid{s} TCR={t:08x} TTBR={b2:08x}" for s, t, b2 in live) or "none"))
    for n in ("fw-text", "fw-data"):
        if n in st:
            r = st[n]
            b = rng(n)
            head = " ".join(f"{x:08x}" for x in words(b, 4)) if b else "-"
            sha = hashlib.sha256(b).hexdigest()[:16] if b else "-"
            print(f"{n}: pa={r.get('pa')} len={r['len']} status={r['status']} head={head} sha={sha}")
    if (b := (d / "adt-boot-args.bin")).exists():
        print("boot-args: " + b.read_bytes().rstrip(b"\0").decode(errors="replace"))
    if (b := (d / "adt-segment-ranges.bin")).exists():
        raw = b.read_bytes()
        for i in range(0, len(raw) - 31, 32):
            phys, iova, remap, size, flags = struct.unpack("<QQQII", raw[i:i + 32])
            print(f"segment: phys={phys:#x} iova={iova:#x} remap={remap:#x} size={size:#x} flags={flags:#x}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        main(arg)
        print()
