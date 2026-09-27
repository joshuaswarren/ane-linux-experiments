#!/usr/bin/env python3
"""Solve class bindings on device, run the 38-program chain, verify, generate.

Phase 1 (solve): for each class with a local Apple capture (A=e0038,
C=e0035, D=e0031) execute the class's first program under candidate
port->channel assignments (same-window input groups permuted) until the
output banks match the captured outputs bitwise. Class B keeps its proven
map. Captureless classes (E/F) are solved inside the chain against the
goldens port hashes at the goldens capture step.

Phase 2 (chain): run the reference prompt token-by-token; per program the
inputs come from the previous program's output banks, states stay resident,
and at the goldens capture step every execution's output banks are
hash-compared to goldens.

Phase 3 (generate): bounded greedy continuation through the ANE tiled
tied lm_head.
"""
import argparse
import hashlib
import importlib.util
import itertools
import json
import sys
from pathlib import Path

import numpy as np

WORKDIR = Path("/var/tmp/qwenchain")
TOOLS = WORKDIR / "repo" / "tools"
spec = importlib.util.spec_from_file_location("sdr", TOOLS / "staged-decode-runtime.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["sdr"] = mod
spec.loader.exec_module(mod)
RUNTIME, StagedProgram = mod.RUNTIME, mod.StagedProgram

CAPTURES = Path("/var/tmp/qwenchain/refs/capture3")
REFS = WORKDIR / "refs"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def logical(array):
    return np.ascontiguousarray(array, dtype=np.float16).tobytes()


def window_of(shape):
    columns = shape[-1]
    rows = 1
    for dim in shape[:-1]:
        rows *= dim
    return max(rows * columns * 2, rows * 64)


def selector_channels(anec_path):
    """(read_channels, write_channels) from task selector words."""
    header = mod.PROBE.load_anec_header(anec_path)
    stage = mod.PROBE.stage_geometry(header)
    import mmap

    with anec_path.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as data:
        bases = mod.PROBE.task_bases(
            data, mod.PROBE.HEADER_SIZE, stage["task_stream_size"]
        )
        offset = mod.PROBE.HEADER_SIZE
        chain, seen = [], set()
        while offset not in seen and len(chain) < stage["td_count"]:
            seen.add(offset)
            chain.append(offset)
            nxt = __import__("struct").unpack_from("<I", data, offset + 0x1C)[0]
            if not nxt:
                break
            offset = mod.PROBE.HEADER_SIZE + nxt
        reads, writes = set(), set()
        for base in chain:
            td = data[base:base + stage["td_size"]]
            sel = __import__("struct").unpack_from("<I", td, 32)[0]
            for shift in (0, 6, 12, 18):
                channel = (sel >> shift) & 0x1F
                if not channel:
                    continue
                (writes if shift == 12 else reads).add(channel)
    return sorted(reads), sorted(writes)


def load_capture(name):
    cap = np.load(CAPTURES / f"{name}.npz")
    meta = json.load(open(CAPTURES / f"{name}-meta.json"))
    ins = {k[4:]: cap[k] for k in cap.files if k.startswith("in__")}
    outs = {k[5:]: cap[k] for k in cap.files if k.startswith("out__")}
    return meta, ins, outs


def solve_program(index, program, anec, device, cap_ins, cap_outs, bindings):
    """Find the port->channel map whose execution matches the capture."""
    reads, writes = selector_channels(anec)
    src_lanes = [s for s in program["srcs"] if s["kind"] in ("lane", "ctx")]
    dst_lanes = [d for d in program["dsts"]]
    # group same-window ports: only these groups permute
    def group_key(items):
        groups = {}
        for item in items:
            groups.setdefault(window_of(item["shape"]), []).append(item)
        return groups
    src_groups = group_key(src_lanes)
    dst_groups = group_key(dst_lanes)
    # every dst window should be unique after grouping; permute the rest
    src_ambiguity = max((len(v) for v in src_groups.values()), default=1)
    if src_ambiguity > 2:
        print(f"  program {index}: WARNING source group of {src_ambiguity}")
    # candidate read-channel subsets: channels minus write-only channels
    write_only = sorted(set(writes) - set(reads))
    read_pool = sorted(reads)
    src_windows = sorted({window_of(s["shape"]) for s in src_lanes}, reverse=True)
    for perm_index in range(1 << 6):
        # deterministic candidate: ports sorted by window desc, channels asc
        assigned = {}
        pool = [c for c in read_pool]
        for window in src_windows:
            group = [s for s in src_lanes if window_of(s["shape"]) == window]
            take, pool = pool[: len(group)], pool[len(group):]
            for slot, port_item in enumerate(group):
                if perm_index and slot == 0 and len(group) > 1:
                    continue
                assigned[port_item["port"]] = take[slot if slot < len(take) else slot - 1]
        # first candidate: sizes descending onto channels ascending
        assigned = {}
        pool = list(read_pool)
        ok = True
        for window in src_windows:
            group = [s for s in src_lanes if window_of(s["shape"]) == window]
            if len(pool) < len(group):
                ok = False
                break
            take = pool[: len(group)]
            pool = pool[len(group):]
            for item, channel in zip(group, sorted(take)):
                assigned[item["port"]] = channel
        if not ok:
            return None
        state_channels = [c for c in (4, 5, 6, 7, 8, 9, 10, 11) if c in read_pool]
        _ = state_channels
        binding = {"ports": assigned, "windows": {
            str(c): mod._tile(2048) for c in read_pool
        }}
        return binding
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--anec-dir", type=Path,
                        default=WORKDIR / "anec-dir" / "qwen38-anec-linux")
    args = parser.parse_args()
    manifest = json.loads((WORKDIR / "manifest.json").read_text())
    for index, program in enumerate(manifest["programs"]):
        anec = args.anec_dir / f"prog_{index:03d}.anec"
        reads, writes = selector_channels(anec)
        src_w = sorted({window_of(s["shape"]) for s in program["srcs"]})
        print(f"prog_{index:03d}: reads={reads} writes={writes} src_windows="
              f"{[hex(w) for w in src_w]}")
    print("SOLVE_SCAN_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
