#!/usr/bin/env python3
"""Window-6 diff: compare a regdump to eos-data.bin and to the AneGap3 patchbay guesses.

usage: macos-window6-diff.py <dump-dir> <eos-data.bin>
  <dump-dir> holds dump.bin + index.json as written by aneregdump.
Prints:
  - per-range identity (name, pa, len, status, sha256[16])
  - DATA carveout vs file (byte equality + 4K block diff offsets)
  - patchbay TLV walk at DATA+0x6aa0..0x6d00 for both ref and live, side-by-side
  - targeted comparison vs AneGap3 guesses (CpAd, WrAd, SOC_, SOCR, GKTS, ARcM, ZSTR, DILS,
    SSSC, qF8v, SVSD, LCSD, BPTP) with measured values when present
"""
import hashlib, json, struct, sys


def sha16(b):
    return hashlib.sha256(b).hexdigest()[:16]


def fletcher16(b):
    """Fletcher-16 (8-bit one's-complement), standard."""
    s1 = 0
    s2 = 0
    for byte in b:
        s1 = (s1 + byte) & 0xff
        s2 = (s2 + s1) & 0xff
    return s1, s2


def walk_patchbay(d, base, end):
    """Packed entries: tag(4 ascii) + len(u32 LE) + value(len). Walk until junk."""
    out, o = [], base
    while o + 8 <= end:
        tag = d[o:o + 4]
        if not all(0x20 <= c < 0x7f for c in tag):
            break
        n = struct.unpack_from("<I", d, o + 4)[0]
        if n > 64 or o + 8 + n > end:
            break
        val = d[o + 8:o + 8 + n]
        out.append((tag.decode(errors="replace"), n, val.hex(), int.from_bytes(val, "little")))
        o += 8 + n
    return out


def main():
    dd, ref_path = sys.argv[1], sys.argv[2]
    idx = json.load(open(f"{dd}/index.json"))
    dump = open(f"{dd}/dump.bin", "rb").read()
    ref = open(ref_path, "rb").read()

    ranges = idx["ranges"] if isinstance(idx, dict) and "ranges" in idx else idx
    by_name = {r["name"]: r for r in ranges}

    print("== ranges (live)")
    for r in ranges:
        print(f"{r['name']:24s} pa={r['pa']} len={r['len']} off={r.get('off', '?')} "
              f"status={r.get('status')} sha256={r.get('sha256', '')[:16]}")

    fw = by_name.get("fw-data")
    if not fw:
        print("no fw-data range in dump")
        sys.exit(2)

    off = fw["off"] if "off" in fw else 0
    live = dump[off:off + fw["len"]]
    n = min(len(ref), 0x3e8000)
    same = live[:n] == ref[:n]
    print(f"\n== DATA segment vs reference")
    print(f"  live[0:0x3e8000] sha {sha16(live[:n])}  ref sha {sha16(ref[:n])}")
    print(f"  match: {'IDENTICAL' if same else 'DIFFERS'}")
    if not same:
        diffs = [a for a in range(0, n, 0x1000) if live[a:a + 0x1000] != ref[a:a + 0x1000]]
        print(f"  differing 4K blocks: {len(diffs)}  first offsets: "
              + " ".join(f"{a:#x}" for a in diffs[:16]))

    print("\n== patchbay walk (reference file vs live DATA)")
    A, E = 0x6aa0, 0x6d00
    rt = {t: (n_, h, v) for t, n_, h, v in walk_patchbay(ref, A, E)}
    lt = {t: (n_, h, v) for t, n_, h, v in walk_patchbay(live, A, E)}
    keys = list(dict.fromkeys(list(rt) + list(lt)))
    for t in keys:
        r, l = rt.get(t), lt.get(t)
        mark = "SAME" if r == l else "DIFF"
        def fmt(e):
            return "absent" if e is None else f"len={e[0]} raw={e[1]} val={e[2]:#x}"
        print(f"  {t}: ref[{fmt(r)}]  live[{fmt(l)}]  {mark}")

    print("\n== targeted patchbay comparison (AneGap3 guesses)")
    g = {
        "_COS": ("SOC_", 0x6001),
        "RCOS": ("SOCR", 0x11),
        "dApC": ("CpAd", 0x285000000),
        "dArW": ("WrAd", 0x285400000),
    }
    for tag, (name, want) in g.items():
        live_e = lt.get(tag)
        if live_e is None:
            print(f"  {name} ({tag}): absent in live; AneGap3 guess 0x{want:x}")
            continue
        got = live_e[2]
        ok = "MATCH" if got == want else "DIFF"
        print(f"  {name} ({tag}): live=0x{got:x} AneGap3=0x{want:x} {ok}")
    for tag, want_guess in (
        ("GKTS", 0xaff),
        ("ARcM", 0x00400000),
        ("ZSTR", 0x00c05000),
        ("DILS", None),
        ("SSSC", None),
        ("qF8v", None),
        ("SVSD", None),
        ("LCSD", None),
        ("BPTP", None),
    ):
        live_e = lt.get(tag)
        if live_e is None:
            print(f"  {tag}: absent in live")
            continue
        got = live_e[2]
        if want_guess is None:
            print(f"  {tag}: live=0x{got:x} (no AneGap3 guess)")
        else:
            ok = "MATCH" if got == want_guess else "DIFF"
            print(f"  {tag}: live=0x{got:x} AneGap3=0x{want_guess:x} {ok}")

    print("\n== text-copy sanity (text_phys+0x7c000, 0x8000)")
    head_e = by_name.get("fw-text-head")
    adt_e = by_name.get("fw-text-adt")
    print(f"  head range: {head_e and (head_e.get('pa'), head_e.get('len'))}")
    print(f"  adt range: {adt_e and (adt_e.get('pa'), adt_e.get('len'))}")


if __name__ == "__main__":
    main()
