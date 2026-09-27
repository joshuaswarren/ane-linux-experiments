#!/usr/bin/env python3
"""Dump per-program TD channel geometry for the staged anec set.

Window workdir defaults; override with --workdir. Pure offline decode.
"""
import argparse
import importlib.util
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--workdir", type=Path, default=Path("/var/tmp/qwenchain"))
args = parser.parse_args()
TOOLS = args.workdir / "repo" / "tools"
spec = importlib.util.spec_from_file_location("sdr", TOOLS / "staged-decode-runtime.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

out = {}
for path in sorted((args.workdir / "anec-dir" / "qwen38-anec-linux").glob("prog_*.anec")):
    stage, channels = mod.decode_channels(path)
    out[path.stem] = {
        str(ch): {"read": r, "write": w} for ch, (r, w) in sorted(channels.items())
    }
manifest = json.load(open(args.workdir / "manifest.json"))
receipt = json.load(open(args.workdir / "anec-dir" / "qwen38-anec-linux" / "convert-receipt.json"))
classes = {p["manifest_index"]: p["class"] for p in receipt["programs"]}
for index, program in enumerate(manifest["programs"]):
    name = f"prog_{index:03d}"
    chans = out[name]
    src_windows = {}
    for source in program["srcs"]:
        port = source["port"]
        shape = source["shape"]
        columns = shape[-1]
        rows = 1
        for dim in shape[:-1]:
            rows *= dim
        src_windows[source["lane"]] = max(rows * columns * 2, rows * 64)
    print(f"== {name} class={classes.get(index)}")
    for lane, window in src_windows.items():
        candidates = [ch for ch, t in chans.items() if max(t) == window]
        print(f"   {lane:6s} window={window:#x} channels={candidates}")
(args.workdir / "td-decode.json").write_text(json.dumps({
    "channels": out, "classes": classes,
}, indent=1) + "\n")
print("TD_DUMP_OK")
