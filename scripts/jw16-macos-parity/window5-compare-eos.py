#!/usr/bin/env python3
"""Compare a window-5 ANERegDump dump against the eos reference and print the patchbay fields.

usage: window5-compare-eos.py <dump-dir> <eos-data.bin>
  <dump-dir> holds dump.bin + index.json as written by aneregdump.
Prints: per-range identity vs reference spans, DATA-segment diff map (4K blocks),
and the packed _rtk_patchbay walk (tag, len, value) at DATA+0x6aa0 for both the
reference file and the live dump.
"""
import hashlib, json, struct, sys


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


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
        out.append((tag.decode(), n, val.hex(), int.from_bytes(val, "little")))
        o += 8 + n
    return out


def main():
    dd, ref_path = sys.argv[1], sys.argv[2]
    idx = json.load(open(f"{dd}/index.json"))
    dump = open(f"{dd}/dump.bin", "rb").read()
    ref = open(ref_path, "rb").read()
    ranges = idx["ranges"] if isinstance(idx, dict) and "ranges" in idx else idx
    by_name = {r["name"]: r for r in ranges}
    print("== ranges")
    for r in ranges:
        print(f"{r['name']:16s} pa={r['pa']:#x} len={r['len']:#x} off={r.get('off', '?'):#x} "
              f"status={r.get('status')} sha256={r.get('sha256', '')[:16]}")
    fw = by_name.get("fw-data")
    if not fw:
        sys.exit("no fw-data range in dump")
    off = fw["off"] if "off" in fw else 0
    live = dump[off:off + fw["len"]]
    n = min(len(ref), 0x3e8000)
    same = live[:n] == ref[:n]
    print(f"\n== DATA segment vs reference: {'IDENTICAL' if same else 'DIFFERS'}")
    print(f"  live[0:0x3e8000] sha {sha(live[:n])}  ref sha {sha(ref[:n])}")
    if not same:
        diffs = [a for a in range(0, n, 0x1000) if live[a:a + 0x1000] != ref[a:a + 0x1000]]
        print(f"  differing 4K blocks: {len(diffs)}  first offsets: "
              + " ".join(f"{a:#x}" for a in diffs[:12]))
    print("\n== patchbay walk (reference file vs live DATA)")
    A, E = 0x6aa0, 0x6d00
    rt = {t: (n_, h, v) for t, n_, h, v in walk_patchbay(ref, A, E)}
    lt = {t: (n_, h, v) for t, n_, h, v in walk_patchbay(live, A, E)}
    for t in dict.fromkeys(list(rt) + list(lt)):
        r, l = rt.get(t), lt.get(t)
        mark = "SAME" if r == l else "DIFF"
        def fmt(e):
            return "absent" if e is None else f"len={e[0]} raw={e[1]} val={e[2]:#x}"
        print(f"{t}: ref[{fmt(r)}]  live[{fmt(l)}]  {mark}")


if __name__ == "__main__":
    main()
