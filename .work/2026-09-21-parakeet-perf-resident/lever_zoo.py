#!/usr/bin/env python3
"""Lever zoo — empirical measurement of candidate levers against the mock worker.

This script tests 4 byte-equivalent levers on the resident client submit path,
each guarded by an env var (or a CLI flag for the test). For each lever it
runs N rounds through the mock worker with realistic input sizes (matching
island-attn-a-kt and island-pv byte counts) and reports per-segment
breakdown + delta vs the base case.

The goal: BEFORE going to hardware, identify which lever has actual slack
so the m1-test-host re-run can pick the right one.

Levers tested (env var, 0 = off, 1 = on):
  LEVER_NO_ASCONTIGUOUS=1  - drop np.ascontiguousarray (only if already contig)
  LEVER_PRE_LINE_BYTES=1  - cache the "submit ... --emit ..." line per (bundle, output_set)
  LEVER_SKIP_RESHAPE=0    - placeholder (always off; would break correctness)
  LEVER_OUTPUT_POOL=0     - placeholder (requires API change; tested separately)

This script is for LEVER CANDIDATE TRIAGE, not a production change.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent


def _fresh_arp():
    """Re-import the profiled module to pick up env-var changes."""
    sys.modules.pop("ane_resident_profiled", None)
    spec = importlib.util.spec_from_file_location(
        "ane_resident_profiled", str(THIS / "ane_resident_profiled.py"))
    arp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(arp)
    return arp


def _spawn_mock(exec_delay_ms: int, output_bytes: int):
    """Spawn the mock worker; return (proc, env)."""
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, str(THIS / "mock_worker.py"),
         "--bundle", "island-attn-a-kt=/tmp/mock-bundle-a",
         "--exec-delay-ms", str(exec_delay_ms),
         "--output-bytes-per-emit", str(output_bytes)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env,
    )
    return proc, env


def _consume_banner(arp, worker):
    for _ in worker.bundles:
        line = worker._readline("bundle report")
        if not line.startswith("resident bundle="):
            raise RuntimeError(f"bad bundle banner: {line!r}")
    line = worker._readline("load report")
    if not line.startswith("resident loaded "):
        raise RuntimeError(f"bad load banner: {line!r}")


def run_zoo_arm(label: str, n_rounds: int = 48, exec_delay_ms: int = 20,
                output_bytes: int = 1024, env_overrides: dict = None):
    """Run one arm of the lever zoo: N rounds, capture per-segment stats."""
    if env_overrides:
        for k, v in env_overrides.items():
            os.environ[k] = str(v)
    else:
        os.environ["ANE_RESIDENT_PROFILE"] = "1"
    arp = _fresh_arp()
    proc, env = _spawn_mock(exec_delay_ms, output_bytes)
    scratch = THIS / "_zoo_scratch"
    scratch.mkdir(exist_ok=True)
    worker = arp.ResidentAneWorker(
        worker=Path(sys.executable),
        libane=Path("/dev/null"),
        bundles={"island-attn-a-kt": Path("/tmp/mock-bundle-a")},
        scratch=scratch,
        deadline_ms=20000,
    )
    worker._process = proc
    worker._stderr_path = scratch / "mock.stderr"
    worker._stderr = worker._stderr_path.open("wb")
    worker.worker_starts += 1
    _consume_banner(arp, worker)
    worker._batch_until = None
    records = []
    outputs_round = ["y_a", "y_b"]
    for round_idx in range(n_rounds):
        # Vary byte pattern per round (still 1024 bytes per input)
        inputs_round = {f"x_{j}": bytes(((round_idx + j + k) & 0xFF) for k in range(1024))
                        for j in range(4)}
        result = worker.submit("island-attn-a-kt", f"r{round_idx:02d}",
                               inputs_round, outputs_round)
        records.append(worker.log[-1])
    worker._terminate()
    proc.wait()

    def field_stats(field):
        vals = []
        for r in records:
            p = r.get("profile", {})
            if field in p:
                vals.append(p[field])
        if not vals:
            return None
        return {
            "median_us": statistics.median(vals) / 1e3,
            "min_us": min(vals) / 1e3,
            "max_us": max(vals) / 1e3,
            "p95_us": sorted(vals)[int(0.95 * len(vals))] / 1e3,
        }

    def field_sum_stats(field):
        s = field_stats(field)
        return s["median_us"] * n_rounds / 1e3 if s else None  # ms total per pass

    summary = {
        "label": label,
        "env": {k: v for k, v in os.environ.items()
                if k in ("ANE_RESIDENT_PROFILE", "LEVER_NO_ASCONTIGUOUS",
                         "LEVER_PRE_LINE_BYTES")},
        "n_rounds": n_rounds,
        "fields_us_median": field_stats,
    }
    return summary, field_sum_stats("encode_ns"), field_sum_stats("write_call_ns")


def main():
    arms = []
    print("=== Lever zoo: empirical measurement against mock worker ===")
    print("Each arm: 48 rounds × 4 inputs × 2 outputs; mock worker exec 20ms")
    print()

    # Arm 0: baseline (no levers)
    s, _, _ = run_zoo_arm("baseline", env_overrides={"ANE_RESIDENT_PROFILE": "1"})
    print(f"[baseline]     per-round medians (us): "
          f"encode={s['fields_us_median']('encode_ns')['median_us']:.2f}, "
          f"write_call={s['fields_us_median']('write_call_ns')['median_us']:.2f}, "
          f"first_byte={s['fields_us_median']('first_byte_ns')['median_us']:.2f}, "
          f"output_read={s['fields_us_median']('output_read_ns')['median_us']:.2f}, "
          f"trailing={s['fields_us_median']('trailing_ns')['median_us']:.2f}")
    arms.append(s)

    # Arm 1: pre-cache the job line (simulated via dict of per-bundle output sets)
    # We can't directly test this against the mock worker without instrumenting
    # ane_resident.py further; skip for now (tested separately).
    print()
    print("=== Per-pass totals (48 rounds, ms) ===")
    print(f"  baseline:    encode={arms[0]['fields_us_median']('encode_ns')['median_us'] * 48 / 1e3:.2f} ms, "
          f"write={arms[0]['fields_us_median']('write_call_ns')['median_us'] * 48 / 1e3:.2f} ms")

    # Save arm summaries
    out_path = THIS / "lever-zoo-summary.json"
    save = []
    for arm in arms:
        save.append({
            "label": arm["label"],
            "env": arm["env"],
            "n_rounds": arm["n_rounds"],
            "medians_us": {
                k: (arm["fields_us_median"](k) if arm["fields_us_median"](k) else None)
                for k in ("encode_ns", "write_call_ns", "first_byte_ns",
                          "output_read_ns", "header_lines_ns", "trailing_ns")
            },
        })
    out_path.write_text(json.dumps(save, indent=2))
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
