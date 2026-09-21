#!/usr/bin/env python3
"""Capture regression for the qmm weight-fetch calibration diagnostic.

Runs the micro's --pass report verification against the PRESERVED real
capture (strict-layout, same-shape single-row calibration on t6001-test-host,
diag.6f70d4fa wheel) and asserts the empirical facts that the parser
and route conclusions depend on:

  - strict layout under the source flush convention (j emitted before
    its flush work): 4 joins, calibration regions 2-4 exactly one
    tick-ful dispatch each, one stable kernel enum;
  - calibrated enum 397 = QmmVecQ4WordSubgroupF16 -> PROXY ROUTE
    (single-row python calls do not route to the decode fused
    QmmVecQ4MultiSubgroupF16 412);

so any future parser or route change that silently breaks the capture
convention fails here. Raw capture: fixtures/calib-v23.ndjson (sha256
438fefb858c39bc9bae19da2da21d0dfdeea64c84068b1e671e8c58bfa9783da).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MICRO = REPO / "scripts/qmm_weight_curve_micro.py"
CAPTURE = Path(os.environ.get("ANE_CALIB_CAPTURE", REPO / "fixtures/calib-v23.ndjson"))
EXPECTED_SHA = ("438fefb858c39bc9bae19da2da21d0dfdeea64c84068b1e671e8c58b"
                "fa9783da")


def test_capture_regression():
    import hashlib
    import os
    import tempfile
    sha = hashlib.sha256(CAPTURE.read_bytes()).hexdigest()
    assert sha == EXPECTED_SHA, f"capture drifted: {sha}"
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "calib-report-regression.json"
        proc = subprocess.run(
            [sys.executable, str(MICRO), "--pass", "report",
             "--profile", str(CAPTURE), "--out", str(out)],
            capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        r = json.loads(out.read_text())
    cal = r["calibration"]
    assert "strict" in cal["verdict"], cal["verdict"]
    assert cal["j_count"] == 4
    assert cal["region_counts"] == {"0": 66, "1": 1, "2": 1, "3": 1,
                                    "4": 1}, cal["region_counts"]
    assert cal["region_enums"]["1"] == [397]
    assert cal["region_enums"]["2"] == [397]
    assert cal["region_enums"]["3"] == [397]
    assert cal["region_enums"]["4"] == [397]
    assert cal["calibrated_enum"] == 397
    assert "PROXY ROUTE" in r["route"], r["route"]


def test_compiled_capture_regression():
    import hashlib
    import os
    cap = Path(os.environ.get("ANE_CALIBC_CAPTURE",
               REPO / "fixtures/calibc-20260920T074637Z.ndjson"))
    sha = hashlib.sha256(cap.read_bytes()).hexdigest()
    assert sha == ("53a6b7042ed5fc12c73b5688afa4acc1fc280178609fcd24f2f09"
                   "6f749dfce0c"), f"capture drifted: {sha}"
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "calibc-report.json"
        proc = subprocess.run(
            [sys.executable, str(MICRO), "--pass", "report",
             "--profile", str(cap), "--out", str(out)],
            capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        r = json.loads(out.read_text())
        assert "strict" in r["calibration"]["verdict"]
        assert r["calibration"]["calibrated_enum"] == 412
        assert r["calibration"]["region_counts"] == {
            "0": 141, "1": 1, "2": 1, "3": 1, "4": 1}
        assert "CONFIRMED" in r["route"], r["route"]


if __name__ == "__main__":
    test_capture_regression()
    test_compiled_capture_regression()
    print("PASS: preserved captures reproduce strict layout, single-row "
          "PROXY ROUTE, and compiled 412 CONFIRMED route")
