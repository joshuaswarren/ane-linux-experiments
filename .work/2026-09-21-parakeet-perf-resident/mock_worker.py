#!/usr/bin/env python3
"""Mock worker for resident client harness.

Speaks the same wire protocol as mlx-omarchy-ane-worker --serve, but runs
in-process in a thread, so tests can run end-to-end without /dev/accel.

Wire protocol observed (see ane_resident.py):
  banner per bundle: "resident bundle=<name> loaded=<n> programs=<m>\n"
  global load report: "resident loaded <n> programs detail=<...>\n"
  per submit (after parent writes "submit <bundle> --inline ... --emit ...\n"
             plus the inline input payloads):
    "out <name> <length>\n" + <length bytes>          (repeated per emit)
    "job status=0 bundle=<name> elapsed_ms=<int> iterations=<int> "
        "input_bytes=<int> output_bytes=<int> stage_ms=<int> save_ms=<int>\n"

  batch open:  parent writes "batch <deadline_ms>\n" -> "batch opened <text>\n"
  batch close: parent writes "batch-end\n" -> "batch closed rounds=<int>\n"
  quit:        parent writes "quit\n" -> "resident released <text>\n"

The mock accepts arbitrary inputs, echoes them back as outputs of identical
byte size, with optional artificial exec delay (--exec-delay-ms) so we can
reproduce the real worker's per-job compute wait.

Usage:
  python3 mock_worker.py --bundle island-attn-a-kt=<dir> \
      [--bundle island-pv=<dir>] \
      [--exec-delay-ms 50]

This script is NOT installed as the real worker. Tests import
_resident_under_test and point it at this script via Popen.
"""

from __future__ import annotations

import argparse
import sys
import time


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", action="append", default=[],
                   help="name=path (path is unused; name is registered)")
    p.add_argument("--exec-delay-ms", type=int, default=50,
                   help="artificial per-job exec delay")
    p.add_argument("--payload-output-multiplier", type=float, default=1.0,
                   help="echo input bytes back as output bytes * multiplier")
    p.add_argument("--output-bytes-per-emit", type=int, default=0,
                   help="if > 0, override output size with this fixed byte count")
    p.add_argument("--flush-every-emit", action="store_true",
                   help="flush stdout after every emit (mimics flushed-stdout worker)")
    p.add_argument("--quit-after", type=int, default=-1,
                   help="quit after N submits (testing)")
    args = p.parse_args()

    bundles = {}
    for spec in args.bundle:
        name, path = spec.split("=", 1)
        bundles[name] = path
        sys.stdout.write(f"resident bundle={name} loaded=1 programs=2\n")
        sys.stdout.flush()

    sys.stdout.write(f"resident loaded {2 * len(bundles)} programs detail=mock\n")
    sys.stdout.flush()

    submits = 0
    while True:
        line_bytes = sys.stdin.buffer.readline()
        if not line_bytes:
            return
        try:
            line = line_bytes.decode("ascii").rstrip("\n")
        except UnicodeDecodeError:
            continue
        cmd = line.strip()
        if cmd == "quit":
            sys.stdout.write("resident released mock\n")
            sys.stdout.flush()
            return
        if cmd.startswith("batch "):
            sys.stdout.write(f"batch opened {cmd[len('batch '):]} mock\n")
            sys.stdout.flush()
            continue
        if cmd == "batch-end":
            sys.stdout.write(f"batch closed rounds={submits}\n")
            sys.stdout.flush()
            continue
        if cmd.startswith("submit "):
            parts = cmd.split()
            bundle = parts[1]
            if bundle not in bundles:
                sys.stdout.write(f"job status=1 bundle={bundle} error=unknown\n")
                sys.stdout.flush()
                continue
            # Consume --inline name=length then read `length` bytes from stdin
            in_bytes = 0
            out_emits = []  # list of (name, length)
            i = 2
            while i < len(parts):
                tok = parts[i]
                if tok == "--inline":
                    name_len = parts[i + 1]
                    name, length = name_len.split("=", 1)
                    length = int(length)
                    sys.stdin.buffer.read(length)  # consume; we don't echo
                    in_bytes += length
                    i += 2
                elif tok == "--emit":
                    out_emits.append(parts[i + 1])
                    i += 2
                else:
                    i += 1
            # Simulate worker exec
            t_exec_start = time.monotonic_ns()
            time.sleep(args.exec_delay_ms / 1000)
            # Emit outputs
            started = time.monotonic_ns()
            for name in out_emits:
                if args.output_bytes_per_emit > 0:
                    out_len = args.output_bytes_per_emit
                else:
                    out_len = int(in_bytes * args.payload_output_multiplier / max(1, len(out_emits)))
                sys.stdout.write(f"out {name} {out_len}\n")
                sys.stdout.buffer.write(b"\x00" * out_len)
                if args.flush_every_emit:
                    sys.stdout.flush()
            elapsed_ms = int((time.monotonic_ns() - started) / 1e6)
            sys.stdout.write(
                f"job status=0 bundle={bundle} elapsed_ms={elapsed_ms} "
                f"iterations=1 input_bytes={in_bytes} "
                f"output_bytes={sum(int(in_bytes*args.payload_output_multiplier/max(1,len(out_emits))) for _ in out_emits)} "
                f"stage_ms=0 save_ms=0\n"
            )
            sys.stdout.flush()
            submits += 1
            if 0 <= args.quit_after <= submits:
                return
            continue
        # Unknown command: ignore


if __name__ == "__main__":
    main()
