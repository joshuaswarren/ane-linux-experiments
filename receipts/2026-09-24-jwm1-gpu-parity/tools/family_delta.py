#!/usr/bin/env python3
"""Render the per-op-family decode microbench into a ranked delta table
vs the M1 macOS reference (receipts/2026-09-23-m1host-decode-gap-batchbudget/family-table-m1-macos-vs-linux.md).
"""
import argparse, json, os, sys

# families from the macOS reference (eb1e711 + family-table-m1-macos-vs-linux.md)
MACOS = {
    "linear qmm[16x2048]": 2.33,
    "linear qmm[2048x2048]": 28.63,
    "linear qmm[2048x6144]": 78.8,
    "linear qmm[4096x2048]": 56.36,
    "linear qmm[512x2048]": 7.56,
    "linear qmm[6144x2048]": 84.5,
    "rms_norm rms_norm": 1.52,
    "conv+silu[6144x4]": 3.66,
    "lm_head full composed": 4242.07,
    "rope": 3.64,
    "sdpa": 5.81,
}

CALLS_PER_TOK = {
    # from the eb1e711 receipt's family table (Linux compile-ON decode capture)
    "linear qmm[16x2048]": 6.2,
    "linear qmm[2048x2048]": 37.2,
    "linear qmm[2048x6144]": 18.6,
    "linear qmm[4096x2048]": 18.6,
    "linear qmm[512x2048]": 18.6,
    "linear qmm[6144x2048]": 18.6,
    "rms_norm rms_norm": 118.8,
    "conv+silu[6144x4]": 18.6,
    "lm_head full composed": 1.0,
    "rope": 12.4,
    "sdpa": 18.6,
}

# family_bench.py emits keys like "linear qmm[2048x2048]" etc.
def linux_keys(linux_json):
    return {k: v for k, v in linux_json.items()
            if isinstance(v, (int, float)) and k in MACOS}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--linux", required=True, help="families-linux-*.json")
    p.add_argument("--macos", default="", help="override macos reference json (else use MACOS)")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    linux = json.load(open(a.linux))
    rows = []
    for k, mac_us in MACOS.items():
        linux_us = linux.get(k)
        if linux_us is None:
            continue
        calls = CALLS_PER_TOK.get(k, 0)
        ratio = linux_us / mac_us if mac_us else 0
        delta = (linux_us - mac_us) * calls
        rows.append((k, calls, mac_us, linux_us, ratio, delta))
    rows.sort(key=lambda r: -r[5])
    with open(a.out, "w") as f:
        f.write("| family | calls/tok | macOS us | Linux us | ratio | delta us/tok |\n")
        f.write("| --- | ---: | ---: | ---: | ---: | ---: |\n")
        total = 0
        for k, calls, mac_us, linux_us, ratio, delta in rows:
            f.write(f"| {k} | {calls:.1f} | {mac_us:.2f} | {linux_us:.2f} | {ratio:.2f}x | {delta:.0f} |\n")
            total += delta
        f.write(f"| **TOTAL benched delta** |  |  |  |  | **{total:.0f}** |\n")
        f.write("\n# per-family decode tok/s + e2e (from `_decode_tok_s_3trials`)\n")
        if "_decode_tok_s_3trials" in linux:
            f.write(f"# decode tok/s trials: {linux['_decode_tok_s_3trials']}\n")
        if "_mlx_version" in linux:
            f.write(f"# mlx version: {linux['_mlx_version']}\n")
        if "_device_info" in linux:
            f.write(f"# device: {linux['_device_info']}\n")
    print(f"wrote {a.out}; total delta {total:.0f} us/tok")

if __name__ == "__main__":
    main()
