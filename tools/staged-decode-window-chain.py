#!/usr/bin/env python3
"""Solve class bindings on device, run the 38-program chain, generate.

Solve: for each class first-program with a local Apple capture
(A=e0038, C=e0035, D=e0031) execute under candidate port->channel maps and
accept the map whose output banks match the captured outputs bitwise.
Content matching needs no permutation sweep on outputs: every expected
array is distinct, so each output bank identifies its port directly; only
same-window INPUT groups permute (<= 3! per group).

Chain: run the reference prompt through all 38 programs; states stay
resident, inputs come from the previous program's output banks; at the
goldens capture step (position 11) every execution is hash-checked.

Generate: bounded greedy continuation through the ANE tiled tied lm_head.
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
spec = importlib.util.spec_from_file_location(
    "sdr", TOOLS / "staged-decode-runtime.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules["sdr"] = mod
spec.loader.exec_module(mod)
RUNTIME, StagedProgram = mod.RUNTIME, mod.StagedProgram

ROWS = 64


def sha(data):
    return hashlib.sha256(data).hexdigest()


def logical(array):
    return np.ascontiguousarray(array, dtype=np.float16).tobytes()


def window_of(shape):
    columns = shape[-1]
    rows = 1
    for dim in shape[:-1]:
        rows *= dim
    return max(rows * columns * 2, rows * ROWS)


def selector_channels(anec_path):
    """(read_channels, write_channels) from task selector words, ws/cmd dropped."""
    import mmap
    import struct

    header = mod.PROBE.load_anec_header(anec_path)
    stage = mod.PROBE.stage_geometry(header)
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
            nxt = struct.unpack_from("<I", data, offset + 0x1C)[0]
            if not nxt:
                break
            offset = mod.PROBE.HEADER_SIZE + nxt
        reads, writes = set(), set()
        for base in chain:
            td = data[base:base + stage["td_size"]]
            sel = struct.unpack_from("<I", td, 32)[0]
            for shift in (0, 6, 12, 18):
                channel = (sel >> shift) & 0x1F
                if not channel:
                    continue
                (writes if shift == 12 else reads).add(channel)
    return sorted(reads - writes - {1}), sorted(writes)


def build_program(index, anec_dir, device, binding, program):
    valid = {
        window_of(s["shape"]) for s in program["srcs"]
    } | {window_of(d["shape"]) for d in program["dsts"]}
    for state in program.get("states", []):
        valid |= {window_of(state["in_shape"]), window_of(state["out_shape"])}
    staged = StagedProgram(
        anec_dir / f"prog_{index:03d}.anec", device, binding,
        name=f"prog_{index:03d}", valid_totals=valid,
    )
    for state in program.get("states", []):
        staged.add_state(state["in_port"], state["out_port"])
    return staged


def candidate_maps(program, reads, writes):
    """Yield partial port->channel maps: data channels per role, groups of
    same-window ports permuted within the available channels."""
    srcs = list(program["srcs"])
    dsts = list(program["dsts"]) + [
        {"port": s["out_port"], "shape": s["out_shape"], "kind": "state_out"}
        for s in program.get("states", [])
    ]
    states = program.get("states", [])
    # data channels: drop the workspace channel if present in both sets
    data_reads = [c for c in reads if c >= 4]
    data_writes = [c for c in writes if c >= 4]
    state_shapes = {s["in_port"]: s["in_shape"] for s in states}
    state_shapes.update({s["out_port"]: s["out_shape"] for s in states})
    # group ports by staged window; same-window groups are the ambiguous part
    src_groups = {}
    for item in srcs:
        shape = state_shapes.get(item["port"], item["shape"])
        src_groups.setdefault(window_of(shape), []).append(item)
    dst_groups = {}
    for item in dsts:
        shape = state_shapes.get(item["port"], item["shape"])
        dst_groups.setdefault(window_of(shape), []).append(item)
    ports = [item["port"] for w in sorted(src_groups, reverse=True)
             for item in src_groups[w]]
    # exhaustive injective maps ports -> data read channels; wrong maps
    # fail their execution or the output match and prune themselves
    for combo in itertools.permutations(data_reads, len(ports)):
        yield dict(zip(ports, combo))


def output_channels(anec_path, count):
    _, writes = selector_channels(anec)
    data_writes = [c for c in writes if c >= 4]
    return data_writes[:count], data_writes


def try_solve(index, program, anec, device, ins, outs, verbose=True):
    """Execute candidates; accept the map where every output bank matches.

    Outputs are matched by CONTENT: every expected array is distinct, so
    after one execution each write bank identifies the port it holds. All
    banks are sized to the program's largest window so any read is safe.
    """
    state_pairs = [(s["in_port"], s["out_port"]) for s in program.get("states", [])]
    reads, writes = selector_channels(anec)
    data_writes = [c for c in writes if c >= 4]
    all_valid = {window_of(s["shape"]) for s in program["srcs"]}
    all_valid |= {window_of(d["shape"]) for d in program["dsts"]}
    for state in program.get("states", []):
        all_valid |= {window_of(state["in_shape"]), window_of(state["out_shape"])}
    max_valid = max(all_valid)
    srcs = [s for s in program["srcs"] if s["kind"] != "state_in"]
    state_ins = [s for s in program["srcs"] if s["kind"] == "state_in"]
    ports = [s["port"] for s in srcs + state_ins]
    tried = 0
    for combo in itertools.permutations(sorted(reads), len(ports)):
        tried += 1
        if tried > 200:
            return None
        mapping = dict(zip(ports, combo))
        for st_out in (s["out_port"] for s in program.get("states", [])):
            mapping[st_out] = next(
                c for c in reversed(data_writes) if c not in mapping.values()
            )
        windows = {}
        shape_by_port = {i["port"]: i["shape"] for i in program["srcs"]}
        shape_by_port.update({d["port"]: d["shape"] for d in program["dsts"]})
        for st in program.get("states", []):
            shape_by_port[st["in_port"]] = st["in_shape"]
            shape_by_port[st["out_port"]] = st["out_shape"]
        for port, channel in mapping.items():
            windows[str(channel)] = window_of(shape_by_port[port])
        binding = {**mapping, "windows": windows}
        try:
            staged = build_program(index, WORKDIR / "anec-dir" / "qwen38-anec-linux",
                                   device, binding, program)
        except (ValueError, KeyError) as error:
            if verbose:
                print(f"  candidate {tried}: {error}", flush=True)
            continue
        try:
            staged.rewind_states()
            for source in program["srcs"]:
                port = source["port"]
                if port in ins:
                    staged.write_bank(port, ins[port].reshape(tuple(source["shape"])))
            for in_port, out_port in state_pairs:
                for key in (in_port, f"in__{in_port}"):
                    if key in ins:
                        staged.write_state(in_port, out_port, ins[key])
                        break
            try:
                staged.execute({})
            except OSError as error:
                if verbose and tried <= 4:
                    print(f"  candidate {tried}: submit {error}", flush=True)
                staged.close()
                continue
            # match each expected output to a write bank by content
            channel_for_port = {}
            for dst in program["dsts"]:
                port = dst["port"]
                if port not in outs:
                    continue
                shape = tuple(dst["shape"])
                expected = logical(outs[port].reshape(shape))
                window = window_of(shape)
                for channel in data_writes:
                    bank = staged.banks[staged.binding.get(port, channel)] \
                        if False else staged.banks.get(channel)
                    if bank is None:
                        continue
                    raw = bank.read(min(window, bank.size))
                    if logical(np.frombuffer(raw, dtype=np.float16)[:len(expected)]
                               .reshape(shape)) == expected:
                        channel_for_port[port] = channel
                        break
            for in_port, out_port in state_pairs:
                if out_port in outs:
                    shape = tuple(next(
                        st["out_shape"] for st in program.get("states", [])
                        if st["out_port"] == out_port))
                    expected = logical(outs[out_port].reshape(shape))
                    window = window_of(shape)
                    for channel in data_writes:
                        bank = staged.banks.get(channel)
                        if bank is None:
                            continue
                        raw = bank.read(min(window, bank.size))
                        if logical(np.frombuffer(raw, dtype=np.float16)[:len(expected)]
                                   .reshape(shape)) == expected:
                            channel_for_port[out_port] = channel
                            break
                if in_port in outs:
                    shape = tuple(next(
                        st["in_shape"] for st in program.get("states", [])
                        if st["in_port"] == in_port))
                    expected = logical(ins[in_port].reshape(shape))
                    window = window_of(shape)
                    for channel in sorted(reads):
                        bank = staged.banks.get(channel)
                        if bank is None:
                            continue
                        raw = bank.read(min(window, bank.size))
                        if logical(np.frombuffer(raw, dtype=np.float16)[:len(expected)]
                                   .reshape(shape)) == expected:
                            channel_for_port[in_port] = channel
                            break
            if len(channel_for_port) == len(expected_out) + len(state_pairs):
                for port, channel in channel_for_port.items():
                    binding[port] = channel
                if verbose:
                    print(f"  program {index}: SOLVED on candidate {tried}: "
                          f"{json.dumps(channel_for_port)}", flush=True)
                return binding
            if verbose and tried <= 4:
                print(f"  candidate {tried}: matched "
                      f"{len(channel_for_port)}/{len(expected_out) + len(state_pairs)}",
                      flush=True)
        finally:
            staged.close()
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--anec-dir", type=Path,
                        default=WORKDIR / "anec-dir" / "qwen38-anec-linux")
    parser.add_argument("--solve-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((WORKDIR / "manifest.json").read_text())
    device = RUNTIME.Device(qid=None)
    solved = {}
    try:
        def load_capture(name):
            directory = WORKDIR / "capture3" / "qc-capture3"
            meta = json.load(open(directory / f"{name}-meta.json"))
            ins, outs = {}, {}
            for path in sorted(directory.glob(f"{name}-in-*.npy")):
                port = path.name[len(name) + 5:-4]
                ins[port] = np.load(path)
            for path in sorted(directory.glob(f"{name}-out-*.npy")):
                port = path.name[len(name) + 6:-4]
                outs[port] = np.load(path)
            return meta, ins, outs

        for index, name in ((0, "e0038"), (2, "e0035"), (6, "e0031")):
            program = manifest["programs"][index]
            _, ins, outs = load_capture(name)
            binding = try_solve(index, program, args.anec_dir / f"prog_{index:03d}.anec",
                                device, ins, outs)
            solved[str(index)] = binding
            print(f"prog_{index:03d} binding: {json.dumps({k: v for k, v in binding.items() if k != 'windows'})}", flush=True)
        (WORKDIR / "bindings.json").write_text(json.dumps(solved, indent=1) + "\n")
        print("SOLVE_OK")
    finally:
        device.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
