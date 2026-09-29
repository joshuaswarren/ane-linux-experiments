#!/usr/bin/env python3
"""Read-only T6021 ANE ExeLoop state collector (run on the M2 as root).

Reads /sys/kernel/debug/ane_t6021_seq/{heap,fwbuf} and, if present, the
sequencer buffers seq/sNNbMM (fallback: top-level sNNbMM), then prints one
JSON object. Never writes anything. Register/MMIO state lives in
ane_probe_ro.c and dmesg; this tool reads only the debugfs dumps.

Offsets are for the 13.5 firmware (sha256 a9c4b771...), verified against
the live dump /tmp/m2-heap-553378f5.bin:
  heap file offset = VA - 0x20fc000000; fwbuf offset = VA - 0x2000000000.
  Engine (CAneEngineExeLoopH14) at heap 0x17ea410 (VA 0x20fd7ea410).
  ELFSM core at [engine+0x6b0]: name at +0x00, magic 0x12483579 at +0x20,
  table image-offset at +0x28 (0xc8020), current state node image-offset at
  +0x38 (node+8 = state id, read via fwbuf VA 0x2000000000 + node),
  state-id mirror u64 at +0x40, engine ctx pointer at +0x48.
  Per-seq records: base = u64[engine+0x6a8] & ~0x3f; record = base +
  seq*0x280 + 0x40 (seq1 record VA 0x20fd68be00 for boot 553378f5).

Usage:
  collect.py                 full state JSON (boot_id, engine, elfsm,
                             per-seq records, output-buffer summary)
  collect.py --check-y [--step 09]
                             read sNNb00=a sNNb01=b sNNb02=y and verify
                             y == a+b elementwise in fp16 (tolerance 0)
  collect.py --root DIR      read from DIR instead of the debugfs root
The last 30 firmware log lines are NOT read here: use dmesg.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

HEAP_VA = 0x20FC000000
FW_VA = 0x2000000000
ENGINE_OFF = 0x17EA410  # heap offset of the ExeLoop engine object
FSM_MAGIC = 0x12483579
ELFSM_TABLE = 0xC8020
DEFAULT_ROOT = "/sys/kernel/debug/ane_t6021_seq"


class Mem:
    """VA-addressed read view over the heap and fwbuf dumps."""

    def __init__(self, heap: bytes, fwbuf: bytes):
        self.regions = ((HEAP_VA, heap), (FW_VA, fwbuf))
        self.sizes = {"heap": len(heap), "fwbuf": len(fwbuf)}

    def read(self, va: int, n: int) -> bytes | None:
        for base, data in self.regions:
            off = va - base
            if 0 <= off <= len(data) - n:
                return data[off:off + n]
        return None

    def u8(self, va: int) -> int | None:
        b = self.read(va, 1)
        return b[0] if b else None

    def u32(self, va: int) -> int | None:
        b = self.read(va, 4)
        return struct.unpack("<I", b)[0] if b else None

    def u64(self, va: int) -> int | None:
        b = self.read(va, 8)
        return struct.unpack("<Q", b)[0] if b else None


def engine_report(mem: Mem) -> dict:
    eng = HEAP_VA + ENGINE_OFF
    vt = mem.u64(eng)
    return {
        "engine_heap_off": hex(ENGINE_OFF),
        "vtable": None if vt is None else hex(vt),
        "vtable_ok": vt == 0xC7E30,
        "log_flag_0x8": mem.u32(eng + 0x8),
        "log_flag_0x24": mem.u32(eng + 0x24),
        "max_jobs_0x198": mem.u32(eng + 0x198),
        "override_1a0": mem.u8(eng + 0x1A0),
        "power_1a1": mem.u8(eng + 0x1A1),
        "secure_phase_1a2": mem.u8(eng + 0x1A2),
        "nonsec2sec_cnt_0x61c": mem.u32(eng + 0x61C),
        "sec2nonsec_cnt_0x620": mem.u32(eng + 0x620),
        "evt_nonsec2sec_0x628": None if (v := mem.u64(eng + 0x628)) is None else hex(v),
        "evt_sec2nonsec_0x648": None if (v := mem.u64(eng + 0x648)) is None else hex(v),
        "evt_0x630": None if (v := mem.u64(eng + 0x630)) is None else hex(v),
        "evt_0x640": None if (v := mem.u64(eng + 0x640)) is None else hex(v),
        "evt_0x650": None if (v := mem.u64(eng + 0x650)) is None else hex(v),
        "counts_0x6c4_0_7": [mem.u32(eng + 0x6C4 + 4 * i) for i in range(8)],
    }


def elfsm_report(mem: Mem) -> dict:
    eng = HEAP_VA + ENGINE_OFF
    core = mem.u64(eng + 0x6B0)
    out: dict = {"core_va": None if core is None else hex(core)}
    if core is None:
        out["error"] = "engine+0x6b0 unreadable"
        return out
    name = mem.read(core, 8)
    out["name"] = (name or b"").split(b"\0")[0].decode("ascii", "replace")
    out["name_ok"] = out["name"] == "ELFSM"
    out["magic_0x20"] = None if (m := mem.u32(core + 0x20)) is None else hex(m)
    out["magic_ok"] = m == FSM_MAGIC
    out["table_0x28"] = None if (t := mem.u64(core + 0x28)) is None else hex(t)
    out["table_ok"] = t == ELFSM_TABLE
    node = mem.u64(core + 0x38)
    out["state_node_0x38"] = None if node is None else hex(node)
    # State nodes are image objects: node is an fwbuf image offset (< 2^32);
    # a full VA would already carry the 0x2000000000 base.
    nid = mem.u32(node + 8) if node is not None and node < 1 << 32 else None
    out["state_id_node8"] = nid
    mirror = mem.u64(core + 0x40)
    out["state_id_mirror_0x40"] = mirror
    out["state_id"] = nid if nid is not None else mirror
    out["layout"] = ("verified against /tmp/m2-heap-553378f5.bin and"
                     " receipts/2026-09-28-h14-fsm-secure-park-decode:"
                     " core+0x38 = current state node (image offset),"
                     " state id at node+8, mirror u64 at core+0x40")
    return out


def per_seq_report(mem: Mem) -> dict:
    eng = HEAP_VA + ENGINE_OFF
    raw = mem.u64(eng + 0x6A8)
    if raw is None:
        return {"error": "engine+0x6a8 unreadable"}
    base = raw & ~0x3F
    recs = {}
    for seq in (1, 2, 3):
        b = mem.read(base + seq * 0x280 + 0x40, 16)
        recs[str(seq)] = None if b is None else b.hex()
    return {"table_base_raw": hex(raw), "table_base": hex(base),
            "record_bytes_16": recs}


def fp16_to_float(raw: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(raw) // 2}e", raw))


def load_bufs(root: Path, step: str) -> dict[str, bytes | None]:
    out = {}
    for mm in ("00", "01", "02"):
        hit = None
        for cand in (root / "seq" / f"s{step}b{mm}", root / f"s{step}b{mm}"):
            if cand.is_file():
                hit = cand
                break
        out[mm] = hit.read_bytes() if hit else None
    return out


def buf_summary(data: bytes | None) -> dict:
    if data is None:
        return {"present": False}
    nz = sum(1 for b in data if b)
    first = fp16_to_float(data[:16])
    return {"present": True, "bytes": len(data), "nonzero_bytes": nz,
            "all_zero": nz == 0, "first8_fp16": first}


def check_y(root: Path, step: str) -> dict:
    bufs = load_bufs(root, step)
    a, b, y = bufs["00"], bufs["01"], bufs["02"]
    res: dict = {"mode": "check_y", "step": step,
                 "a": buf_summary(a), "b": buf_summary(b), "y": buf_summary(y)}
    if a is None or b is None or y is None:
        res["error"] = "missing s%sb00/b01/b02 under %s (or %s/seq)" % (
            step, root, root)
        return res
    n = min(len(a), len(b), len(y)) // 2
    if len(a) != len(b) or len(y) != len(a):
        res["warning"] = f"length mismatch a={len(a)} b={len(b)} y={len(y)}; using {2 * n} bytes"
    ra, rb, ry = (struct.unpack(f"<{n}H", m[:2 * n]) for m in (a, b, y))
    try:
        import numpy as np
        fa = np.frombuffer(a, dtype="<f2", count=n).astype(np.float16)
        fb = np.frombuffer(b, dtype="<f2", count=n).astype(np.float16)
        fy = np.frombuffer(y, dtype="<f2", count=n).astype(np.float16)
        bad = np.flatnonzero((fa + fb) != fy)
        mismatches = [(int(i), float(fa[i]), float(fb[i]), float(fa[i] + fb[i]),
                       float(fy[i])) for i in bad[:5]]
    except ImportError:
        # Pure-Python fp16: decode via struct '<e', add in float64, round
        # back to fp16, compare value-exactly (NaN == NaN counts as a match).
        un, pk = struct.unpack, struct.pack

        def vals(r):
            return [un("<e", pk("<H", v))[0] for v in r]

        def rnd(x: float) -> float:
            return un("<e", pk("<e", x))[0]

        fa, fb, fy = vals(ra), vals(rb), vals(ry)
        sums = [rnd(x + y) for x, y in zip(fa, fb)]
        bad = [i for i in range(n)
               if sums[i] != fy[i] and not (sums[i] != sums[i] and fy[i] != fy[i])]
        mismatches = [(i, fa[i], fb[i], sums[i], fy[i]) for i in bad[:5]]
    res["elements"] = n
    res["tolerance"] = 0
    res["mismatch_count"] = len(bad)
    res["first_mismatches_idx_a_b_expected_got"] = mismatches
    res["all_zero_output"] = all(v == 0 for v in ry)
    res["pass"] = len(bad) == 0
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help="debugfs root (default: %s)" % DEFAULT_ROOT)
    ap.add_argument("--check-y", action="store_true",
                    help="verify y == a+b for sNNb00/01/02")
    ap.add_argument("--step", default="09", help="sequencer step NN")
    args = ap.parse_args()
    root = Path(args.root)
    try:
        heap = (root / "heap").read_bytes()
        fwbuf = (root / "fwbuf").read_bytes()
    except OSError as e:
        print(json.dumps({"error": f"cannot read {root}/{{heap,fwbuf}}: {e}"}))
        return 1
    mem = Mem(heap, fwbuf)
    if args.check_y:
        out = check_y(root, args.step)
    else:
        try:
            boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        except OSError:
            boot_id = None
        out = {"boot_id": boot_id, "dumps": mem.sizes,
               "engine": engine_report(mem), "elfsm": elfsm_report(mem),
               "per_seq": per_seq_report(mem), "note": "fw log lines: use dmesg"}
        for step in sorted({p.name[1:3] for p in root.glob("s*b02")}
                           | {p.name[1:3] for p in root.glob("seq/s*b02")}):
            out.setdefault("outputs", {})[step] = buf_summary(
                load_bufs(root, step)["02"])
    json.dump(out, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
