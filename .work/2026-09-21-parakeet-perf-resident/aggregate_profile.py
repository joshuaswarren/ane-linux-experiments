#!/usr/bin/env python3
"""Aggregate the profiled per-segment breakdown from a profiled lease run.

Reads /var/tmp/ane-runtime/fused-e2e/profiled-<TS>/out-meas-*/e2e-report.json
and computes median per-segment breakdown across the 5 measured runs.

Outputs a JSON summary suitable for committing as a receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

MEL = "5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
HID = "38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX = "db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def stats(vals):
    if not vals:
        return None
    return {
        "n": len(vals),
        "median": statistics.median(vals),
        "median_ms": statistics.median(vals) / 1e6,
        "min_ms": min(vals) / 1e6,
        "max_ms": max(vals) / 1e6,
        "p95_ms": sorted(vals)[int(0.95 * len(vals))] / 1e6,
        "sum_ms": sum(vals) / 1e6,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run_dir", type=Path)
    p.add_argument("out_path", type=Path)
    args = p.parse_args()

    # Find all measured run dirs
    meas = sorted(args.run_dir.glob("out-meas-*"))
    print(f"Found {len(meas)} measured runs in {args.run_dir}", file=sys.stderr)

    # Per-run summary
    runs = []
    # Per-round profile aggregations across all rounds in all runs
    all_round_profiles = []  # list of profile dicts from each round
    all_session_profiles = []  # list of session_profile dicts

    for d in meas:
        rep = json.loads((d / "e2e-report.json").read_text())
        stages = {s["stage"]: s["wall_ms"] for s in rep.get("stages", [])}
        # Hash gates
        gold_mel = sha(d / "mel.npy") == MEL
        gold_hid = sha(d / "encoder_hidden.npy") == HID
        gold_trx = sha(d / "transcript.txt") == TRX
        gold_all = gold_mel and gold_hid and gold_trx
        # Get prefix from execution
        prefix = rep.get("execution", {}).get("matching_prefix")
        # Get ANE log
        ane_log = rep.get("ane", {}).get("log", [])
        # Collect all round profiles
        run_round_profiles = []
        for entry in ane_log:
            prof = entry.get("profile")
            if prof is None:
                continue
            run_round_profiles.append(prof)
            all_round_profiles.append(prof)
            sp = prof.get("session_profile")
            if sp is not None:
                all_session_profiles.append(sp)
        runs.append({
            "run": d.name,
            "encoder_ane_ms": stages.get("encoder_ane"),
            "total_ms": rep.get("timing", {}).get("total_pipeline_ms"),
            "goldens_bitexact": gold_all,
            "mel_bitexact": gold_mel,
            "hidden_bitexact": gold_hid,
            "transcript_bitexact": gold_trx,
            "matching_prefix": prefix,
            "round_count": len(run_round_profiles),
            "round_profiles_with_session_profile": sum(1 for p in run_round_profiles if p.get("session_profile")),
        })

    encoder_ane_ms_vals = [r["encoder_ane_ms"] for r in runs if r["encoder_ane_ms"] is not None]
    total_ms_vals = [r["total_ms"] for r in runs if r["total_ms"] is not None]

    # Aggregate per-segment
    def fields(field_name, source):
        """source: 'vulkan_encoder' or 'parent'"""
        out = []
        for p in all_round_profiles if source == "vulkan_encoder" else all_session_profiles:
            if field_name in p:
                out.append(p[field_name])
        return out

    summary = {
        "schema": "m1-test-host-profiled-perf-battery-aggregate/1",
        "host": "m1-test-host",
        "lock_inode": 27,
        "identity_pin": {
            "worker_sha256": "944f2a86cea719c4c10f6cd1a08c4c6df50b001cac0e381c38ca1f26277920cf",
            "libane_sha256": "1ab9d95debcc8b5fee3b6653dfce0b50412bc7efef43c2d2167dc83ce270ca49",
            "driver_sha256": "7087accecede1f556ed604d28fe88a8f6e5e90df202bc8cdf50c4cea51c76bfd",
            "driver_buildid": "ac55e1bc3359f444d1746a058d83620fd8b0bbd4",
            "placement": "AC (island-attn-a-kt + island-pv on T8103 ANE)",
            "transport": "resident-batch (ANE_ISLAND_MODE unset)",
            "profile_env": "ANE_RESIDENT_PROFILE=1",
        },
        "runs": runs,
        "gates": {
            "all_goldens_bitexact": all(r["goldens_bitexact"] for r in runs),
            "all_status_match": all(r["matching_prefix"] == 104 for r in runs if r["matching_prefix"] is not None),
            "n_runs_with_prefix_104": sum(1 for r in runs if r["matching_prefix"] == 104),
            "total_rounds_collected": len(all_round_profiles),
            "total_session_profiles": len(all_session_profiles),
        },
        "encoder_ane_ms": {
            "median": statistics.median(encoder_ane_ms_vals) if encoder_ane_ms_vals else None,
            "min": min(encoder_ane_ms_vals) if encoder_ane_ms_vals else None,
            "max": max(encoder_ane_ms_vals) if encoder_ane_ms_vals else None,
        },
        "total_ms": {
            "median": statistics.median(total_ms_vals) if total_ms_vals else None,
            "min": min(total_ms_vals) if total_ms_vals else None,
            "max": max(total_ms_vals) if total_ms_vals else None,
        },
        "per_segment_vulkan_encoder_ms": {
            "marshal_eval_ns": stats(fields("marshal_eval_ns", "vulkan_encoder")),
            "session_round_ns": stats(fields("session_round_ns", "vulkan_encoder")),
            "back_conv_ns": stats(fields("back_conv_ns", "vulkan_encoder")),
            "sum_ns": stats(fields("sum_ns", "vulkan_encoder")),
        },
        "per_segment_parent_side_ns": {
            "encode_ns": stats(fields("encode_ns", "parent")),
            "write_call_ns": stats(fields("write_call_ns", "parent")),
            "first_byte_ns": stats(fields("first_byte_ns", "parent")),
            "output_read_ns": stats(fields("output_read_ns", "parent")),
            "header_lines_ns": stats(fields("header_lines_ns", "parent")),
            "trailing_ns": stats(fields("trailing_ns", "parent")),
            "sum_ns": stats(fields("sum_ns", "parent")),
        },
    }

    args.out_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
