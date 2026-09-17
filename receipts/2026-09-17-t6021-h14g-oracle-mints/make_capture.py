#!/usr/bin/env python3
"""Index-encoded weights.bin for h14g/h13 ANE oracle mints.

Payload requirement (Main, 2026-09-17): NOT uniform. Each half encodes its
own source index so the emitted permutation is readable offline from bytes.

Encoding: every ADJACENT PAIR of halves carries a 28-bit pair watermark:
  even half bits = 0x0400 + (p & 0x3FFF)        (positive normal fp16)
  odd  half bits = 0x8400 + ((p >> 14) & 0x3FFF) (negative normal fp16)
Readback: p = (even - 0x0400) | ((odd - 0x8400) << 14). p = source pair index.
All bit patterns are finite, non-zero, non-subnormal fp16 (verified below), so
the compiler has no reason to canonicalize them.

weights.bin layout (replicates overlay/tools/ane-export/ane_export.py):
  0x40 file header (u32 version=1, u32 entry_count=2)
  0x40 blob record (u32 magic 0xDEADBEEF, u32 version=1, u64 byte_count,
                    u64 zero, u64 data_offset=128)
  raw fp16 payload at 0x80
MIL BLOBFILE offset stays uint64(64) (points at the blob record), exactly as
the exporter emits it.

Usage: python3 make_capture.py GEOMETRY OUT_DIR
  GEOMETRY in {oproj, mm1, mm2}
"""
import json
import struct
import sys
from pathlib import Path

GEOMETRIES = {
    # name: (M, K, N)
    "oproj": (375, 1024, 1024),
    "mm1": (375, 1024, 4096),
    "mm2": (375, 4096, 1024),
}

EVEN_BASE = 0x0400
ODD_BASE = 0x8400
MASK = 0x3FFF


def fp16_finite(bits: int) -> bool:
    exp = (bits >> 10) & 0x1F
    return exp != 0 and exp != 0x1F  # no subnormal, no inf/nan


def payload_bytes(n_halves: int) -> bytes:
    assert n_halves % 2 == 0
    n_pairs = n_halves // 2
    assert (n_pairs - 1) < (1 << 28), "pair watermark overflow"
    out = bytearray()
    worst_even = EVEN_BASE + MASK
    worst_odd = ODD_BASE + MASK
    assert fp16_finite(EVEN_BASE) and fp16_finite(worst_even)
    assert fp16_finite(ODD_BASE) and fp16_finite(worst_odd)
    for p in range(n_pairs):
        even = EVEN_BASE + (p & MASK)
        odd = ODD_BASE + ((p >> 14) & MASK)
        out += struct.pack("<HH", even, odd)
    return bytes(out)


def build_weights(payload: bytes) -> bytes:
    header = struct.pack("<II56x", 1, 2)
    record = struct.pack("<IIQQQ32x", 0xDEADBEEF, 1, len(payload), 0, 128)
    return header + record + payload


def mil_text(m: int, k: int, n: int) -> str:
    blob = (
        'BLOBFILE(path = string("@model_path/weights.bin"),'
        " offset = uint64(64))"
    )
    return (
        "program(1.3)\n"
        "[buildInfo = dict<string, string>({{\"coremlc-component-MIL\", \"3520.4.1\"},"
        " {\"coremlc-version\", \"3520.5.1\"}})]\n"
        "{\n"
        f"    func main<ios18>(tensor<fp16, [1, {m}, {k}]> t1) {{\n"
        f"        tensor<fp16, [{k}, {n}]> t0 = const()[name = string(\"t0\"),"
        f" val = tensor<fp16, [{k}, {n}]>({blob})];\n"
        f"        tensor<fp16, [1, {m}, {n}]> t2 = matmul(x = t1, y = t0,"
        " transpose_x = false, transpose_y = false)[name = string(\"t2\")];\n"
        "    } -> (t2);\n"
        "}\n"
    )


def main() -> None:
    name = sys.argv[1]
    out_dir = Path(sys.argv[2])
    m, k, n = GEOMETRIES[name]
    n_halves = k * n
    weights = build_weights(payload_bytes(n_halves))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "model.mil").write_text(mil_text(m, k, n))
    (out_dir / "weights.bin").write_bytes(weights)
    meta = {
        "geometry": name,
        "M": m, "K": k, "N": n,
        "weight_halves": n_halves,
        "weight_bytes": len(weights),
        "encoding": "pair28: even=0x0400+(p&0x3FFF), odd=0x8400+((p>>14)&0x3FFF)",
        "readback": "p = (even-0x0400) | ((odd-0x8400)<<14); p = source pair index",
        "mil_blobfile_offset": 64,
        "payload_offset": 128,
    }
    (out_dir / "capture-meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"[mint-kit] {name}: capture dir {out_dir} "
          f"(weights {len(weights)} bytes = {n_halves} halves)")


if __name__ == "__main__":
    main()
