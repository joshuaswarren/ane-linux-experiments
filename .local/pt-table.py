#!/usr/bin/env python3
"""ParakeetTransport: build the per-pass transport attribution table from a
pt e2e out dir (run-report.json from the runner + e2e-report.json from the
harness when present). Prints the phase table, byte counts, and the
whole-pipeline multiple of the 292.2 ms macOS divisor."""
import json
import sys

DIVISOR_MS = 292.2

out_dir = sys.argv[1]
runner = json.load(open(f"{out_dir}/run-report.json"))
ane = runner["ane"]
phase_us = ane.get("phase_us", {})

per_round_ms = {}
rounds = ane.get("log", [])
for rec in rounds:
    b = rec.get("bundle", "?")
    d = per_round_ms.setdefault(b, {"n": 0, "elapsed": 0.0, "in": 0, "out": 0})
    d["n"] += 1
    d["elapsed"] += rec.get("elapsed_ns", 0) / 1e6
    d["in"] += rec.get("input_bytes", 0)
    d["out"] += rec.get("output_bytes", 0)

print(f"transport={ane.get('transport')} mode={ane.get('mode')} "
      f"rounds={ane.get('rounds')} submissions={ane.get('submissions')} "
      f"timeouts={ane.get('timeouts')}")
total_in = ane.get("input_bytes", 0)
total_out = ane.get("output_bytes", 0)
print(f"bytes/pass: in={total_in/1e6:.2f} MB out={total_out/1e6:.2f} MB")

print(f"{'component':<34}{'ms/pass':>10}{'share of round wall':>21}")
exec_ms = ane.get("exec_ns", 0) / 1e6
rows = [
    ("client marshal (np->wire bytes)", ane.get("marshal_ns", 0) / 1e6),
    ("client IPC write (stdin pipe)", sum(r.get("write_ns", 0) for r in rounds) / 1e6),
    ("serve recv (stdin payloads)", phase_us.get("recv_us", 0) / 1e3),
    ("serve submit (whole child call)", phase_us.get("submit_us", 0) / 1e3),
    ("  child crecv (socket recv)", phase_us.get("crecv_us", 0) / 1e3),
    ("  child pack (shm->tile->BO)", phase_us.get("pack_us", 0) / 1e3),
    ("  child exec (device ioctls)", phase_us.get("exec_us", 0) / 1e3),
    ("  child read (BO->tile->sink)", phase_us.get("read_us", 0) / 1e3),
    ("serve emit (stdout payloads)", phase_us.get("emit_us", 0) / 1e3),
    ("client IPC read (stdout pipe)", sum(r.get("read_ns", 0) for r in rounds) / 1e6),
    ("client back (bytes->mx.array)", ane.get("back_ns", 0) / 1e6),
]
for name, ms in rows:
    share = f"{100 * ms / exec_ms:.1f}%" if exec_ms else "-"
    print(f"{name:<34}{ms:>10.1f}{share:>21}")
print(f"{'= ane_exec wall (client-measured)':<34}{exec_ms:>10.1f}")
print(f"{'unaccounted inside round wall':<34}"
      f"{exec_ms - sum(m for _, m in rows):>10.1f}")

try:
    e2e = json.load(open(f"{out_dir}/e2e-report.json"))
    stages = e2e.get("stages", [])
    enc = next((s for s in stages if isinstance(s, dict) and s.get("name") == "encoder_ane"), {})
    total = e2e.get("total_pipeline_ms")
    print(f"\nencoder_ane wall_ms={enc.get('wall_ms')} "
          f"ane_exec_ms={e2e.get('ane', {}).get('exec_ms')}")
    if total:
        print(f"whole-pipeline {total:.1f} ms = {total / DIVISOR_MS:.1f}x the "
              f"292.2 ms macOS divisor")
except (OSError, KeyError):
    print("\n(no harness e2e-report.json in this out dir)")

print("\nper-bundle round sums (ms):")
for b, d in per_round_ms.items():
    print(f"  {b:<12} n={d['n']:>3} wall={d['elapsed']:>8.1f} "
          f"in={d['in']/1e6:.2f}MB out={d['out']/1e6:.2f}MB")
