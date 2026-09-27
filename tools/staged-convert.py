#!/usr/bin/env python3
"""Batch-convert the staged Qwen decoder HWX set to Linux .anec artifacts.

The staged export compiles one HWX per manifest program (compile order pinned
by prog_NNN build dirs), but the HWX directory numbering is the export order,
not the runtime order, and superseded compiles may sit alongside the live
ones. This driver pairs every manifest program to its HWX by surface/geometry
signature, validates the pairing against the known pairs, applies the staged
td_size policy (header clamp stays 0x1f8 unless the program carries register
records at task offsets >= 0x1f8, in which case the header carries the true
maximum descriptor extent), and writes one .anec plus a conversion receipt.

  python3 tools/staged-convert.py \
    --hwx-dir /v/.../qwen38-staged-hwx-h13g \
    --manifest manifest.json --pairing hwx-manifest-pairing.json \
    --out-dir anec/ [--manifest-progs dir-with-prog_NNN/weights.bin]
"""

import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path


def load_converter():
    path = Path(__file__).with_name("hwxv2-to-anec.py")
    spec = importlib.util.spec_from_file_location("hwxv2_to_anec", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def task_extents(conv, data) -> tuple[int, int]:
    """Return (max_extent, first_extent) over the linked task stream."""
    image = conv.parse_hwx(data)
    offsets = conv.find_task_offsets(data, image.content_offset, image.content_size)
    if not offsets:
        raise ValueError("no task descriptors")
    bounds = list(offsets) + [image.task_stream_size]
    extents = [bounds[i + 1] - bounds[i] for i in range(len(offsets))]
    return max(extents), extents[0]


def hwx_signature(conv, data) -> dict:
    image = conv.parse_hwx(data)
    return {
        "input_size": image.input_size,
        "output_size": image.output_size,
        "workspace_size": image.workspace_size,
        "td_count": image.td_count,
        "kernel_size": image.kernel_size,
        "kernel_is_blob": image.kernel_is_blob,
        "content_size": image.content_size,
    }


def port_class(program: dict) -> str:
    lanes_in = [s["lane"] for s in program["srcs"] if s["kind"] == "lane"]
    lanes_out = [d["lane"] for d in program["dsts"] if d["kind"] == "lane"]
    has_ctx = any(s["kind"] == "ctx" for s in program["srcs"])
    if program.get("group_start"):
        return "A"
    if lanes_in == ["x", "o", "z"] and lanes_out == ["h"]:
        return "F" if has_ctx else "E"
    if lanes_out == ["o"]:
        return "B"
    if has_ctx:
        return "D"
    return "C"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hwx-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pairing", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest-progs", type=Path,
                        help="dir with prog_NNN/weights.bin for blob kernels")
    args = parser.parse_args(argv)

    conv = load_converter()
    manifest = json.loads(args.manifest.read_text())
    programs = manifest["programs"]
    known = {}
    if args.pairing is not None:
        for row in json.loads(args.pairing.read_text()):
            known[row["manifest_index"]] = row["hwx_prog"]

    files = {}
    for path in sorted(args.hwx_dir.glob("prog_*/model.hwx")):
        with path.open("rb") as stream, __import__("mmap").mmap(
            stream.fileno(), 0, access=__import__("mmap").ACCESS_READ
        ) as data:
            files[path.parent.name] = hwx_signature(conv, data)
    if not files:
        raise SystemExit(f"no model.hwx under {args.hwx_dir}")

    # assign known pairs first, then match the rest by signature cluster
    assignment: dict[int, str] = {}
    for index, name in known.items():
        if name not in files:
            raise SystemExit(f"pairing names {name} but no such HWX exists")
        assignment[index] = name
        del files[name]

    remaining: dict[int, str] = {}
    for index, program in enumerate(programs):
        if index in assignment:
            continue
        remaining[index] = port_class(program)
    clusters: dict[tuple, list[str]] = {}
    for name, sig in files.items():
        clusters.setdefault(tuple(sorted(sig.items())), []).append(name)
    by_class: dict[str, list[int]] = {}
    for index, cls in remaining.items():
        by_class.setdefault(cls, []).append(index)

    # a class matches exactly one cluster of equal size; several classes may
    # share a cluster only when their counts fill it exactly
    unresolved = []
    for cls, indexes in sorted(by_class.items()):
        candidates = [names for names in clusters.values() if len(names) == len(indexes)]
        if len(candidates) == 1:
            for index, name in zip(indexes, sorted(candidates[0])):
                assignment[index] = name
                del clusters[tuple(sorted(files[name].items()))]
                del files[name]
        else:
            unresolved.append((cls, len(indexes), len(candidates)))
    if unresolved:
        for cls, want, got in unresolved:
            sizes = sorted(
                (len(names), files[names[0]]["kernel_size"]) for names in clusters.values()
            )
            print(f"class {cls}: {want} programs, {got} exact-size clusters; "
                  f"free cluster sizes/kernels: {sizes[:8]}", file=sys.stderr)
        raise SystemExit("ambiguous HWX pairing; extend the pairing file")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    receipts = []
    for index, program in enumerate(programs):
        name = assignment[index]
        path = args.hwx_dir / name / "model.hwx"
        with path.open("rb") as stream, __import__("mmap").mmap(
            stream.fileno(), 0, access=__import__("mmap").ACCESS_READ
        ) as data:
            max_extent, first_extent = task_extents(conv, data)
            sig = hwx_signature(conv, data)
            override = max_extent if max_extent > 0x1F8 else None
            if override is not None and override > 0x3FC:
                raise SystemExit(f"{name}: extent {override:#x} exceeds driver bound")
            blob_path = None
            if sig["kernel_is_blob"]:
                if args.manifest_progs is None:
                    raise SystemExit(f"{name}: blob kernel needs --manifest-progs")
                blob_path = args.manifest_progs / name / "weights.bin"
            image = conv.convert_hwx_file(
                str(path), str(args.out_dir / f"prog_{index:03d}.anec"),
                len(program["srcs"]), len(program["dsts"]),
                blob_path=blob_path, td_size_override=override,
            )
        receipts.append({
            "manifest_index": index, "hwx_prog": name,
            "class": port_class(program),
            "td_first_extent": first_extent, "td_max_extent": max_extent,
            "td_size_override": override,
            "signature": sig,
            "in_ports": [s["port"] for s in program["srcs"]],
            "out_ports": [d["port"] for d in program["dsts"]],
        })
        print(f"prog_{index:03d} <- {name} class={port_class(program)} "
              f"td={override if override else 'clamp0x1f8'} "
              f"kernel={sig['kernel_size']:#x}")
    receipt = args.out_dir / "convert-receipt.json"
    receipt.write_text(json.dumps({
        "hwx_dir": str(args.hwx_dir), "manifest": str(args.manifest),
        "programs": receipts,
    }, indent=1) + "\n")
    print(f"wrote {len(receipts)} anec + {receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
