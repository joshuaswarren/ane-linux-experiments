#!/usr/bin/env python3
"""Analyze the diagnostics wheel's profile.jsonl (MLX_OMARCHY_GPU_PROFILE)
plus an external host-markers stream. Produce a one-token decode timeline:
per-kernel µs/tok, dispatches/tok, submissions/tok, GPU busy µs, host
record/submit µs, ranked.
"""
import argparse, json, os, re, sys
from collections import defaultdict

p = argparse.ArgumentParser()
p.add_argument("--profile", required=True, help="path to MLX_OMARCHY_GPU_PROFILE NDJSON")
p.add_argument("--markers", required=True, help="path to host CLOCK_MONOTONIC NDJSON")
p.add_argument("--compute-h", action="store_true", help="load ComputeKernel enum")
p.add_argument("--out-prefix", required=True)
a = p.parse_args()

# --- parse markers ---
markers = []
for line in open(a.markers):
    line = line.strip()
    if not line:
        continue
    markers.append(json.loads(line))

def marker_ns(name):
    for m in markers:
        if m["p"] == name:
            return m["t"]
    return None

prefill_start = marker_ns("prefill_start")
prefill_done = marker_ns("prefill_done")
done = marker_ns("done")
# decode_N markers -> list of decode iteration timestamps
decode_marks = sorted([m for m in markers if m["p"].startswith("decode_")],
                      key=lambda m: int(m["p"].split("_")[1]))

# --- parse profile NDJSON ---
recs = []
for line in open(a.profile):
    line = line.strip()
    if not line:
        continue
    try:
        recs.append(json.loads(line))
    except json.JSONDecodeError:
        pass

# profile records carry fields like:
#  {"op": "dispatch", "kernel": "QmmVecQ4...", "gx": ..., "gy": ..., "gz": ...,
#   "t_start_ns": ..., "t_end_ns": ..., "bytes": ...}
#  {"op": "submit", ...}
#  {"op": "host_record", ...}
# plus prefill/decode markers (set by the harness when crossing token
# boundaries) - tokens are denominated by an integer token_idx.

# Try to discover the field layout from the first record.
if recs:
    sample = recs[0]
    fields = sorted(sample.keys())
else:
    fields = []
with open(a.out_prefix + ".fields.txt", "w") as f:
    f.write("\n".join(fields) + "\n")
    f.write(f"# records: {len(recs)}\n")
    f.write(f"# markers: {len(markers)} (prefill_done at +{(prefill_done - prefill_start)/1e6:.3f} ms if both set)\n")
if prefill_start is not None and prefill_done is not None:
    with open(a.out_prefix + ".prefill.txt", "w") as f:
        f.write(f"prefill_host_wall_ms: {(prefill_done - prefill_start) / 1e6:.3f}\n")
if len(decode_marks) >= 2:
    deltas_ns = [decode_marks[i+1]["t"] - decode_marks[i]["t"]
                 for i in range(len(decode_marks) - 1)]
    deltas_ns_sorted = sorted(deltas_ns)
    n = len(deltas_ns_sorted)
    p50 = deltas_ns_sorted[n // 2] / 1e3   # us
    p10 = deltas_ns_sorted[n // 10] / 1e3
    p90 = deltas_ns_sorted[(9 * n) // 10] / 1e3
    wall_per_tok_us = sum(deltas_ns) / len(deltas_ns) / 1e3
    decode_tok_s = 1e6 / wall_per_tok_us if wall_per_tok_us > 0 else 0.0
    with open(a.out_prefix + ".timeline.txt", "w") as f:
        f.write(f"decode_tokens: {len(decode_marks) - 1}\n")
        f.write(f"wall_per_tok_us: {wall_per_tok_us:.3f}\n")
        f.write(f"decode_tok_s: {decode_tok_s:.3f}\n")
        f.write(f"p10_us: {p10:.3f}\n")
        f.write(f"p50_us: {p50:.3f}\n")
        f.write(f"p90_us: {p90:.3f}\n")

# per-kernel aggregation
# detect record shape
def get(d, *keys, default=None):
    for k in keys:
        if k in d:
            return d[k]
    return default

# Filter to records inside the decode region (between decode_0 and decode_{N-1} t).
decode_region = None
if decode_marks:
    decode_region = (decode_marks[0]["t"], decode_marks[-1]["t"])

kernel_dur = defaultdict(int)   # ns total
kernel_count = defaultdict(int)
kernel_bytes = defaultdict(int)
gpu_busy_ns = 0
submits = 0
dispatches = 0
host_record_ns = 0
host_submit_ns = 0
for r in recs:
    if decode_region is not None:
        t0 = get(r, "t_start_ns", "gpu_t_start_ns")
        t1 = get(r, "t_end_ns", "gpu_t_end_ns")
        if t0 is not None and (t0 < decode_region[0] or t0 > decode_region[1]):
            continue
    op = get(r, "op", "kind", "event")
    kname = get(r, "kernel", "name", "id")
    if op is None:
        continue
    if op in ("dispatch", "kernel") and kname:
        dur = get(r, "dur_ns", "duration_ns", "t_ns")
        bytes_ = get(r, "bytes", "size", 0) or 0
        if dur is None and get(r, "t_start_ns") is not None and get(r, "t_end_ns") is not None:
            dur = r["t_end_ns"] - r["t_start_ns"]
        if dur is None:
            dur = 0
        kernel_dur[kname] += int(dur)
        kernel_count[kname] += 1
        kernel_bytes[kname] += int(bytes_)
        gpu_busy_ns += int(dur)
        dispatches += 1
    elif op == "submit":
        submits += 1
        d = get(r, "dur_ns", "duration_ns")
        if d:
            host_submit_ns += int(d)
    elif op in ("host_record", "record"):
        d = get(r, "dur_ns", "duration_ns")
        if d:
            host_record_ns += int(d)

n_tok = len(decode_marks) - 1 if decode_marks else 0
rows = []
for kname in kernel_count:
    rows.append((kname, kernel_count[kname], kernel_dur[kname] / max(1, n_tok) / 1000.0,
                 kernel_bytes[kname] / max(1, n_tok), kernel_count[kname] / max(1, n_tok)))
rows.sort(key=lambda r: -r[2])

# write kernel table
with open(a.out_prefix + ".kernels.txt", "w") as f:
    f.write(f"# decode tokens measured: {n_tok}\n")
    f.write(f"# dispatches/token: {dispatches/max(1,n_tok):.1f}\n")
    f.write(f"# submissions/token: {submits/max(1,n_tok):.3f}\n")
    f.write(f"# GPU busy us/token (sum of per-dispatch GPU duration): {gpu_busy_ns/max(1,n_tok)/1000:.1f}\n")
    f.write(f"# host_record us/token: {host_record_ns/max(1,n_tok)/1000:.1f}\n")
    f.write(f"# host_submit us/token: {host_submit_ns/max(1,n_tok)/1000:.1f}\n")
    f.write("# kernel | n/tok | us/tok | MB/tok | n/tok(col)\n")
    for r in rows:
        f.write(f"{r[0]} | {r[1]/max(1,n_tok):.1f} | {r[2]:.1f} | {r[3]/1e6:.2f} | {r[4]:.1f}\n")

# small summary file
with open(a.out_prefix + ".summary.json", "w") as f:
    json.dump({
        "n_tok": n_tok,
        "dispatches_per_tok": dispatches / max(1, n_tok),
        "submits_per_tok": submits / max(1, n_tok),
        "gpu_busy_us_per_tok": gpu_busy_ns / max(1, n_tok) / 1000,
        "host_record_us_per_tok": host_record_ns / max(1, n_tok) / 1000,
        "host_submit_us_per_tok": host_submit_ns / max(1, n_tok) / 1000,
        "fields": fields,
    }, f, indent=1)
print(f"wrote {a.out_prefix}.{{kernels,timeline,prefill,summary.json,fields.txt}}")
