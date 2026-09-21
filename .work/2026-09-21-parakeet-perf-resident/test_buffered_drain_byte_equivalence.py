#!/usr/bin/env python3
"""Failing-first byte-equivalence test for LEVER_BUFFERED_DRAIN.

Verifies that running the same set of submits through:
  - ResidentAneWorker with LEVER_BUFFERED_DRAIN=0  (base)
  - ResidentAneWorker with LEVER_BUFFERED_DRAIN=1  (lever on)
produces byte-identical outputs in the same order, with hash-checked equality.

Failing-first: this test FAILS if the lever produces even one byte of
difference. It is the gate before any hardware touch.
"""

from __future__ import annotations

import importlib.util
import statistics
import subprocess
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
BUFFERED = THIS / "ane_resident_buffered.py"


def _spawn_mock():
    return subprocess.Popen(
        [sys.executable, str(THIS / "mock_worker.py"),
         "--bundle", "island-attn-a-kt=/tmp/mock-bundle-a",
         "--exec-delay-ms", "10",
         "--output-bytes-per-emit", "1024"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def _consume_banner(worker):
    for _ in worker.bundles:
        line = worker._readline("bundle report")
        if not line.startswith("resident bundle="):
            raise RuntimeError(f"bad bundle banner: {line!r}")
    line = worker._readline("load report")
    if not line.startswith("resident loaded "):
        raise RuntimeError(f"bad load banner: {line!r}")


def run_with_lever(lever_on: bool, n_rounds: int = 10):
    """Spawn one mock + one ResidentAneWorker; return list of (round, results)."""
    import importlib
    sys.modules.pop("ane_resident_buffered", None)
    spec = importlib.util.spec_from_file_location(
        "ane_resident_buffered", str(BUFFERED))
    arp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(arp)

    import os
    os.environ["ANE_RESIDENT_PROFILE"] = "1"
    os.environ["LEVER_BUFFERED_DRAIN"] = "1" if lever_on else "0"

    proc = _spawn_mock()
    scratch = THIS / "_test_scratch"
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
    _consume_banner(worker)
    worker._batch_until = None

    captured = []
    for round_idx in range(n_rounds):
        inputs = {f"x_{j}": bytes(((round_idx + j + k) & 0xFF) for k in range(1024))
                  for j in range(4)}
        outputs = ["y_a", "y_b"]
        result = worker.submit("island-attn-a-kt", f"r{round_idx:02d}",
                               inputs, outputs)
        captured.append((round_idx, result, worker.log[-1]))
    worker._terminate()
    proc.wait()
    return captured


def main():
    print("=== Phase A: lever OFF (base) ===")
    base = run_with_lever(False)
    print(f"  {len(base)} rounds, all results captured")

    print("=== Phase B: lever ON (buffered_drain) ===")
    lever = run_with_lever(True)
    print(f"  {len(lever)} rounds, all results captured")

    # Byte equivalence check
    for (ri_a, results_a, log_a), (ri_b, results_b, log_b) in zip(base, lever):
        assert ri_a == ri_b, f"round order mismatch"
        assert set(results_a.keys()) == set(results_b.keys()), (
            f"round {ri_a}: output key set differs: {set(results_a.keys())} vs {set(results_b.keys())}"
        )
        for k in results_a:
            assert results_a[k] == results_b[k], (
                f"round {ri_a} output {k}: byte mismatch\n"
                f"  base:   {results_a[k][:32].hex()}...\n"
                f"  lever: {results_b[k][:32].hex()}..."
            )
            # Hash check
            import hashlib
            ha = hashlib.sha256(results_a[k]).hexdigest()
            hb = hashlib.sha256(results_b[k]).hexdigest()
            assert ha == hb, f"round {ri_a} output {k}: sha256 differs {ha} vs {hb}"

    print(f"  All {len(base)} rounds: byte-identical, hash-identical")
    print("=== ALL BYTE-EQUIVALENCE INVARIANTS PASS ===")


if __name__ == "__main__":
    main()
