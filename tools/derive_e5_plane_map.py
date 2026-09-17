#!/usr/bin/env python3
"""t602x/h14g e5-oracle plane-map derivation attempt (2026-09-17).

Runs the known-answer gate specified for the T6021 oracle mints: parse the
Espresso e5bundlecache program (H13D.e5 / H14C.e5), recover the weight-plane
permutation by matching the pair28 watermark to emitted positions, and check
the result against the independently-derived H13/M1 maps (hwx route + device
gates):

    oproj (375,1024,1024):  g_inv(P) = ((P>>5)<<5) | ((P&1)<<4) | ((P>>1)&15)
    mm1   (375,1024,4096):  P_half(g,c,L) = 16384*pi256(g) + c + 16L,
                            pi256(g) = (g & ~31) | ((g&15)<<1) | ((g>>4)&1)
    mm2   (375,4096,1024):  identity group order, 16-output group split across
                            two 32768-half planes:
                            c<8  -> 32768*(2g)   + 8L + c
                            c>=8 -> 32768*(2g+1) + 8L + (c-8)

RESULT (see receipts/2026-09-17-t6021-plane-derivation.md): the e5 container
embeds NO weight payload and NO weight descriptors — the only cross-geometry
variant bytes are in/out tensor shapes, extern buffer sizes, and the geometry
name inside the provenance path. There is no permutation in the container to
recover, so the gate FAILS by data absence and NO t6021 map may be claimed.

Usage: python3 tools/derive_e5_plane_map.py [MINTS_DIR]
  MINTS_DIR defaults to receipts/2026-09-17-t6021-h14g-oracle-mints/
  Prints the container layout, diff accounting, watermark verification, and
  the per-formula gate verdict; exit 0 either way (the verdict is data).
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_MINTS = REPO / "receipts/2026-09-17-t6021-h14g-oracle-mints"
HOSTS = ["jw14m2-t6021-host", "macstudio-t6000-host"]
GEOMS = ["oproj", "mm1", "mm2"]
ARCHES = ["h14g", "h13"]

EVEN_BASE, ODD_BASE, PAIR_MASK = 0x0400, 0x8400, 0x3FFF


# ---------------------------------------------------------------- e5 loading
def load_e5(mints: Path, host: str, geom: str, arch: str) -> bytes:
    hits = [p for p in (mints / host / geom / f"cache_{arch}").rglob("*.e5")
            if not p.name.startswith("._")]
    assert len(hits) == 1, f"expected one .e5 for {host}/{geom}/{arch}, got {hits}"
    return hits[0].read_bytes()


def load_weights(mints: Path, host: str, geom: str) -> bytes:
    p = mints / host / geom / "weights.bin"
    if not p.exists():  # >3 MiB copies were trimmed from the repo archive
        import subprocess
        gen = mints / "make_capture.py"
        out = Path("/tmp/plane-derive-regen") / geom
        subprocess.run([sys.executable, str(gen), geom, str(out)], check=True,
                       capture_output=True)
        p = out / "weights.bin"
    return p.read_bytes()


# ------------------------------------------------------- container structure
def strings_of(buf: bytes):
    """All [u32 len][ascii] string records — the named-section/symbol anchors."""
    out, i = [], 0
    while i < len(buf) - 4:
        n = struct.unpack_from("<I", buf, i)[0]
        if 1 <= n <= 128 and i + 4 + n <= len(buf):
            s = buf[i + 4:i + 4 + n]
            if all(32 <= c < 127 for c in s):
                out.append((i, s.decode()))
                i += 4 + n
                continue
        i += 1
    return out


def u32_fields(buf: bytes):
    return {off: v for off in range(0, len(buf) - 3, 4)
            for v in [struct.unpack_from("<I", buf, off)[0]]}


def diff_ranges(a: bytes, b: bytes, join: int = 2):
    rs = []
    for i in range(len(a)):
        if a[i] != b[i]:
            if rs and i <= rs[-1][1] + join:
                rs[-1][1] = i
            else:
                rs.append([i, i])
    return rs


def describe_layout(buf: bytes) -> str:
    """Human-readable layout of one e5 program (macstudio oproj is canonical)."""
    lines = [f"H13D.e5 layout ({len(buf)} B):"]
    strs = strings_of(buf)
    named = [(off, s) for off, s in strs]
    chip = struct.unpack_from("<H", buf, len(buf) - 8)[0]
    lines.append(f"  trailer __sym_desc__ content ({buf[-12:].hex()}): "
                 f"magic=0x{buf[-12:-8][::-1].hex()} chip_id=0x{chip:04x} pad=0")
    for off, s in named:
        if s.startswith("__") or s in ("main",) or "main_" in s or s in ("t0", "t1"):
            lines.append(f"  0x{off:04x}: {s!r}")
    # tensor shape blocks: locate (bytes, 0, 0x38, 0x14, 0x34, 0x48) anchors
    for m in range(len(buf) - 24):
        if buf[m:m + 4] == b"\x00\xb8\x0b\x00" or buf[m:m + 4] == b"\x00\xe0\x2e\x00":
            lines.append(f"  0x{m:04x}: tensor byte_count=0x{struct.unpack_from('<I', buf, m)[0]:x}")
    return "\n".join(lines)


# ------------------------------------------------------------- gate helpers
def known_h13_maps():
    """The three H13/M1 maps to reproduce, as emitted-position lookups.

    Each returns dict: emitted plane-half position -> source pair index p
    over the full weight payload of that geometry (W = N*K halves).
    """
    def oproj_map():
        # 64 planes x 16384 halves; plane P holds group g_inv(P), layout
        # within plane matches the source row-major (c outer, L inner) pairs.
        m = {}
        for P in range(64):
            g = ((P >> 5) << 5) | ((P & 1) << 4) | ((P >> 1) & 0xF)
            for c in range(16):
                for L in range(1024):
                    m[P * 16384 + c * 16 + L] = g * 16384 + c * 16 + L
        return m

    def mm1_map():
        m = {}
        for g in range(256):
            pg = (g & ~31) | ((g & 15) << 1) | ((g >> 4) & 1)
            for c in range(16):
                for L in range(1024):
                    m[16384 * pg + c + 16 * L] = g * 16384 + c * 16 + L
        return m

    def mm2_map():
        m = {}
        for g in range(64):
            for c in range(16):
                plane, cc = (2 * g, c) if c < 8 else (2 * g + 1, c - 8)
                for L in range(4096):
                    m[32768 * plane + 8 * L + cc] = g * 65536 + c * 16 + L
        return m

    return {"oproj": oproj_map, "mm1": mm1_map, "mm2": mm2_map}


def extract_weight_descriptors(buf: bytes):
    """Attempt the specified parse: find (src_offset, dst_plane) DMA pairs
    referencing the external BLOBFILE weights payload inside the e5.

    Returns list of (offset, value) candidates: any u32/u64 that could be a
    weight-payload source byte offset (>=0x80, even) or a plane-sized copy
    length (32768/65536 B x k), with known non-weight fields excluded.
    """
    known_nonweight = {0x0, 0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0x7, 0x8, 0xc, 0x10,
                       0x14, 0x18, 0x1c, 0x20, 0x24, 0x28, 0x2c, 0x30, 0x38,
                       0x48, 0x177, 0x400, 0x800, 0x1000, 0x2000, 0xa4,
                       0xbb800, 0x2ee000, 0xc0000, 0x120, 0x150, 0x190, 0x194,
                       0x728, 0x8ec, 0x4d0, 0x360, 0x230, 0x1a8}
    hits = []
    for off in range(0, len(buf) - 3, 4):
        v = struct.unpack_from("<I", buf, off)[0]
        if v in known_nonweight:
            continue
        is_src = 0x80 <= v <= 0x1000000 and v % 2 == 0
        is_plane_len = v in (0x8000, 0x10000, 0x20000, 0x40000, 0x80000)
        if is_src or is_plane_len:
            hits.append((off, v))
    return hits


def verify_watermark(payload: bytes) -> tuple:
    halves = struct.unpack(f"<{len(payload)//2}H", payload)
    ok = sum(1 for p in range(len(halves) // 2)
             if halves[2 * p] == EVEN_BASE + (p & PAIR_MASK)
             and halves[2 * p + 1] == ODD_BASE + ((p >> 14) & PAIR_MASK))
    return ok, len(halves) // 2


# --------------------------------------------------------------------- main
def main() -> None:
    mints = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MINTS
    report = {"mints": str(mints), "arch_invariance": {}, "cross_host": {},
              "cross_geometry_accounting": {}, "watermark_at_rest": {},
              "weight_descriptors": {}, "known_answer_gate": {}}

    e5 = {(h, g, a): load_e5(mints, h, g, a) for h in HOSTS for g in GEOMS for a in ARCHES}
    for h in HOSTS:
        for g in GEOMS:
            same = e5[(h, g, "h14g")] == e5[(h, g, "h13")]
            report["arch_invariance"][f"{h}/{g}"] = same
            print(f"[arch] {h} {g}: h14g == h13 -> {same}")

    # cross-host: normalize the path-salted provenance by aligning on the
    # shared 0x000c0000 (786432) anchor, then diff.
    for g in GEOMS:
        a, b = e5[("macstudio-t6000-host", g, "h14g")], e5[("jw14m2-t6021-host", g, "h14g")]
        best = min(((d, sum(1 for i in range(len(a) - d) if a[i] != b[i + d]))
                    for d in range(0, 33)), key=lambda t: t[1])
        diff_idx = [i for i in range(len(a)) if a[i] != b[i + best[0]]]
        rs = diff_ranges(a, b[best[0]:best[0] + len(a)])
        chip_a = struct.unpack_from("<H", a, len(a) - 8)[0]
        chip_b = struct.unpack_from("<H", b, len(b) - 8)[0]
        report["cross_host"][g] = {"aligned_shift": best[0], "differing": len(diff_idx),
                                   "ranges": [[hex(s), hex(e)] for s, e in rs],
                                   "chip_macstudio": f"0x{chip_a:04x}",
                                   "chip_jw14m2": f"0x{chip_b:04x}"}
        print(f"[host] {g}: shift={best[0]} differing={len(diff_idx)} "
              f"ranges={[(hex(s), hex(e)) for s, e in rs]} "
              f"chip 0x{chip_a:04x} vs 0x{chip_b:04x}")

    # cross-geometry accounting on one host: every differing byte must be an
    # in/out tensor shape, extern size, or the geometry name in the path.
    a = e5[("macstudio-t6000-host", "mm1", "h14g")]
    for g in ("oproj", "mm2"):
        b = e5[("macstudio-t6000-host", g, "h14g")]
        rs = diff_ranges(a, b)
        n = sum(e - s + 1 for s, e in rs)
        report["cross_geometry_accounting"][f"mm1-vs-{g}"] = {
            "differing": n, "ranges": [[hex(s), hex(e)] for s, e in rs]}
        print(f"[geom] mm1 vs {g}: {n} bytes in ranges "
              f"{[(hex(s), hex(e)) for s, e in rs]}")

    # watermark at rest (identity order of the source payload)
    for g in GEOMS:
        payload = load_weights(mints, "jw14m2-t6021-host", g)[0x80:]
        ok, total = verify_watermark(payload)
        report["watermark_at_rest"][g] = {"ok": ok, "total": total}
        print(f"[wm] {g}: {ok}/{total} pairs in source order at rest")

    # the gate itself: any weight-relevant field MUST scale with geometry
    # (oproj W = 2 MiB vs mm1/mm2 W = 8 MiB; mm1 vs mm2 share the identical
    # weight blob but have different known maps). Closure: enumerate every
    # u32 position where oproj and mm1 values differ; a weight byte count
    # (0x200000 / 0x800000) must appear nowhere; and any differing position
    # outside the accounted shape/extern/path ranges would be unexplained.
    o, m1 = e5[("macstudio-t6000-host", "oproj", "h14g")], e5[("macstudio-t6000-host", "mm1", "h14g")]
    fo, fm = u32_fields(o), u32_fields(m1)
    scaled = [hex(off) for off in fo
              if fo[off] != fm.get(off) and not (
                  0xb4 <= off <= 0xdd or 0x3c8 <= off <= 0x438 or 0x7c0 <= off <= 0x804)]
    wcount = [hex(off) for off, v in fo.items() if v in (0x200000, 0x800000)]
    report["weight_descriptors"] = {
        "geometry_scaled_fields_outside_accounted_ranges": scaled,
        "weight_byte_count_fields": wcount}
    print(f"[desc] geometry-scaled fields outside accounted ranges -> {scaled or 'NONE'}")
    print(f"[desc] weight byte-count fields (0x200000/0x800000) -> {wcount or 'NONE'}")

    # The three formulas are computed (they are closed-form and known-good);
    # the gate asks whether the e5 provides ANY data to validate them against.
    # It does not: no weight payload, no descriptors. Verdict per formula.
    for g, fn in known_h13_maps().items():
        m = fn()
        verdict = ("NOT REPRODUCIBLE FROM E5 — container embeds no weight "
                   "payload and no weight descriptors; watermark matching has "
                   "no emitted positions to match against")
        report["known_answer_gate"][g] = {"map_size": len(m), "verdict": verdict}
        print(f"[gate] {g}: FAIL — {verdict}")
        del m

    out = REPO / ".local/ane-plane-derive/gate-verdict.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"\nverdict JSON -> {out}")
    print(describe_layout(e5[("macstudio-t6000-host", "oproj", "h14g")]))


if __name__ == "__main__":
    main()
