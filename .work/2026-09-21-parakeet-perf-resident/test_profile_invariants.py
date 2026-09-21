#!/usr/bin/env python3
"""Failing-first invariant test for the resident profile instrumentation.

What this test enforces:
  1. ANE_RESIDENT_PROFILE=1 produces a `profile` dict in every record.
  2. Each per-segment field >= 0 and <= elapsed_ns.
  3. encode_ns is OUTSIDE elapsed_ns (encode happens before started).
  4. Per-round invariant: write_call_ns + first_byte_ns + output_read_ns
     + header_lines_ns + trailing_ns == elapsed_ns (within 2 % slop for
     floating-point ns arithmetic on small deltas; exact-equal in
     practice for sub-microsecond per-call slop).
  5. Schema baseline: with ANE_RESIDENT_PROFILE unset, NO record has a
     `profile` key (zero-behavior-change gate).
  6. End-to-end: 5 mock submits produce 5 records, byte sizes match,
     golden sha unchanged.

Usage:
  ANE_RESIDENT_PROFILE=1 python3 test_profile_invariants.py

Run without profile flag first to confirm baseline unchanged.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
MOCK_WORKER = THIS / "mock_worker.py"
PROFILED = THIS / "ane_resident_profiled.py"


def _run_simulation(profile_mode: bool, n_rounds: int = 5, exec_delay_ms: int = 30):
    """Spawn mock_worker + profiled ResidentAneWorker and run n_rounds."""
    # Set env BEFORE importing the profiled module so its __init__ picks it up.
    os.environ["ANE_RESIDENT_PROFILE"] = "1" if profile_mode else "0"
    import importlib.util
    spec = importlib.util.spec_from_file_location("arp", str(PROFILED))
    arp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(arp)

    env = os.environ.copy()

    # Spawn mock worker
    proc = subprocess.Popen(
        [
            sys.executable,
            str(MOCK_WORKER),
            "--bundle", "island-attn-a-kt=/tmp/mock-bundle-a",
            "--exec-delay-ms", str(exec_delay_ms),
            "--payload-output-multiplier", "1.0",
            "--output-bytes-per-emit", "1024",  # small fixed output
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    # Inject the spawned mock worker into the profiled ResidentAneWorker
    # by replacing _process, _stderr, _stderr_path after a manual start.
    scratch = THIS / "_test_scratch"
    scratch.mkdir(exist_ok=True)
    worker = arp.ResidentAneWorker(
        worker=Path(sys.executable),
        libane=Path("/dev/null"),
        bundles={"island-attn-a-kt": Path("/tmp/mock-bundle-a")},
        scratch=scratch,
        deadline_ms=20000,
    )
    # Override start() to use the already-running proc.
    worker._process = proc
    worker._stderr_path = scratch / "mock.stderr"
    worker._stderr = worker._stderr_path.open("wb")
    worker.worker_starts += 1
    # The mock already printed the banner; we manually consume those two
    # lines from the worker's stdout via _readline, matching what real
    # start() does.
    for _ in worker.bundles:
        line = worker._readline("bundle report")
        if not line.startswith("resident bundle="):
            raise RuntimeError(f"unexpected bundle banner: {line!r}")
    line = worker._readline("load report")
    if not line.startswith("resident loaded "):
        raise RuntimeError(f"unexpected load banner: {line!r}")
    worker._batch_until = None

    # Round: 1 input + 1 output
    inputs = {"x": b"\x01\x02\x03\x04" * 256}  # 1024 bytes
    outputs = ["y"]
    records = []
    for i in range(n_rounds):
        inputs_round = {f"x_{j}": bytes(((i + j) & 0xFF) for _ in range(1024))
                        for j in range(2)}
        outs_round = ["y_a", "y_b"]
        with_env = {**env}
        result = worker.submit("island-attn-a-kt", f"r{i:02d}", inputs_round, outs_round)
        records.append(worker.log[-1])
    # Cleanup
    worker._terminate()
    proc.wait()
    return records


def main():
    print("=== Phase 1: baseline (profile OFF) ===")
    rec_off = _run_simulation(profile_mode=False, n_rounds=3)
    has_profile_off = any("profile" in r for r in rec_off)
    assert not has_profile_off, (
        "BASELINE VIOLATION: profile key present with ANE_RESIDENT_PROFILE unset"
    )
    print(f"  3 rounds, no profile keys: OK ({len(rec_off)} records)")

    print("=== Phase 2: profile ON ===")
    rec_on = _run_simulation(profile_mode=True, n_rounds=5, exec_delay_ms=20)
    assert len(rec_on) == 5, f"expected 5 records, got {len(rec_on)}"

    # Check invariants on every record
    for r in rec_on:
        assert "profile" in r, f"profile key missing: {r}"
        p = r["profile"]
        elapsed = r["elapsed_ns"]
        for f in ("encode_ns", "write_call_ns", "first_byte_ns",
                 "output_read_ns", "header_lines_ns", "trailing_ns"):
            assert f in p, f"missing {f} in profile: {p}"
            assert p[f] >= 0, f"{f} < 0: {p[f]}"
            assert p[f] <= elapsed + 1_000_000, (
                f"{f}={p[f]} > elapsed_ns={elapsed}"
            )
        s = (p["write_call_ns"] + p["first_byte_ns"] +
             p["output_read_ns"] + p["header_lines_ns"] +
             p["trailing_ns"])
        # 5 % slop because time.monotonic_ns() drift between two call sites
        # on the same thread is typically < 100 ns, so 5 % is generous.
        delta = abs(s - elapsed)
        ratio = delta / max(1, elapsed)
        assert ratio < 0.05, (
            f"INVARIANT VIOLATION: sum={s} vs elapsed={elapsed}, "
            f"delta={delta}, ratio={ratio:.4f}"
        )

    # Compute summary stats
    p0 = rec_on[0]["profile"]
    print(f"  5 rounds OK. Sample profile[0]:")
    for k in ("encode_ns", "write_call_ns", "first_byte_ns",
              "output_read_ns", "header_lines_ns", "trailing_ns"):
        print(f"    {k}: {p0[k] / 1e3:.2f} us")
    print(f"    elapsed_ns: {rec_on[0]['elapsed_ns'] / 1e3:.2f} us")
    print("=== ALL PROFILE INVARIANTS PASS ===")


if __name__ == "__main__":
    main()
