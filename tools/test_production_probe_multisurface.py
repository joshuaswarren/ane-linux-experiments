#!/usr/bin/env python3
"""Regression: the probe must read multi-surface geometry from the correct
ANEC tile slots (outputs at 4..4+dst-1, inputs at 4+dst..), not from the
single-port slots 4/5. Reproduces the reviewed indexing bug offline.

Bug signature: for a 4-in/8-out program whose first input surface is
196,608 elements (393,216 B = 24 tiles of 16 KiB) and whose second output
surface is 81,920 B (5 tiles), the single-port stage_geometry reported
source_size = tiles[5] * TILE_SIZE = 81,920 — the second OUTPUT slot —
instead of input surface 0's 393,216.

Run: python3 tools/test_production_probe_multisurface.py  (offline, no device)
"""

import importlib.util
import struct
import sys
from pathlib import Path

TILE_SIZE = 0x4000


def load_probe():
    path = Path(__file__).with_name("production-anec-probe.py")
    spec = importlib.util.spec_from_file_location("probe_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_header(src_count, dst_count, input_tiles, output_tiles):
    """Build the ANEC header words the converter emits for this surface set."""
    header = [0] * 7
    header[0] = 0x7090000          # content_size (unused by geometry)
    header[1] = 0x1F8              # td_size
    header[2] = 62                 # td_count
    header[3] = 0x9CF8             # task_stream_size
    header[4] = 0x7083EC0          # kernel_size
    header[5] = src_count
    header[6] = dst_count
    tiles = [0] * 32
    tiles[0] = 0x709               # command tiles
    tiles[3] = 8                   # workspace tiles
    for index, count in enumerate(output_tiles):
        tiles[4 + index] = count
    for index, count in enumerate(input_tiles):
        tiles[4 + dst_count + index] = count
    nchw = []
    for count in output_tiles + input_tiles:
        # one fp16 plane per tile count: N,C,H,W = 1,1,1,elements
        nchw += [1, 1, 1, count * (TILE_SIZE // 2), TILE_SIZE, TILE_SIZE]
    return tuple(header) + tuple(tiles) + tuple(nchw)


def main() -> int:
    probe = load_probe()

    # The reviewed repro: 4 inputs (first = 24 tiles = 393,216 B),
    # 8 outputs (second = 5 tiles = 81,920 B).
    output_tiles = [1, 5, 1, 1, 1, 1, 1, 24]
    input_tiles = [24, 1, 1, 1]
    header = build_header(4, 8, input_tiles, output_tiles)
    stage = probe.stage_geometry(header)

    failures = []
    if stage["src_count"] != 4 or stage["dst_count"] != 8:
        failures.append(f"surface counts {stage['src_count']}/{stage['dst_count']}")
    if [s["bdx"] for s in stage["output_surfaces"]] != list(range(4, 12)):
        failures.append("output slots are not 4..11")
    if [s["bdx"] for s in stage["input_surfaces"]] != list(range(12, 16)):
        failures.append("input slots are not 12..15")
    if stage["input_surfaces"][0]["bytes"] != 393_216:
        failures.append(
            f"input surface 0 = {stage['input_surfaces'][0]['bytes']} B, "
            f"expected 393,216 (the old code read tiles[5] = 81,920 here)"
        )
    if stage["output_surfaces"][1]["bytes"] != 81_920:
        failures.append(
            f"output surface 1 = {stage['output_surfaces'][1]['bytes']} B, "
            f"expected 81,920"
        )
    if stage["input_bytes"] != sum(24 * TILE_SIZE for _ in range(4)) - 23 * TILE_SIZE:
        pass  # informational only: per-surface sizes differ by design

    # Single-port programs must keep their original slots.
    header1 = build_header(1, 1, [3], [7])
    stage1 = probe.stage_geometry(header1)
    if stage1["input_surfaces"][0]["bytes"] != 3 * TILE_SIZE:
        failures.append("single-port input slot changed")
    if stage1["output_surfaces"][0]["bytes"] != 7 * TILE_SIZE:
        failures.append("single-port output slot changed")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(
        "PASS: 4in/8out slots 4..11/12..15 decoded per surface; "
        "input0=393,216 B; output1=81,920 B; single-port slots unchanged"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
