"""CLI contract tests for tools/hwx_check.py (issue #12 review fix 6).

The checker must exit non-zero when any input fails and when no path is
given; a PASS prints and exits 0. The shebang must stay on line 1.
"""

import subprocess
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
CHECK = ROOT / "tools" / "hwx_check.py"
FRESH64 = ROOT / "tools" / "fresh-64.hwx.sample"  # real H13 output: FAIL


def run_check(*args):
    return subprocess.run([sys.executable, str(CHECK), *args],
                          capture_output=True, text=True)


def test_shebang_is_line_1():
    assert CHECK.read_text().startswith("#!/usr/bin/env python3\n")


def test_exit_nonzero_on_rejected_file(tmp_path):
    p = tmp_path / "bad.hwx"
    p.write_bytes(b"\xce\xfa\xef\xbe" + b"\0" * 36)  # bad header fields
    r = run_check(str(p))
    assert r.returncode == 1, f"stdout={r.stdout}"
    assert "FAIL" in r.stdout


def test_exit_nonzero_on_real_h13_sample():
    r = run_check(str(FRESH64))
    assert r.returncode == 1, f"stdout={r.stdout}"
    assert "FAIL" in r.stdout


def test_exit_nonzero_without_args():
    r = run_check()
    assert r.returncode == 2
    assert "usage" in (r.stdout + r.stderr).lower()


def test_exit_zero_on_pass(tmp_path):
    """PASS prints rc 0. Needs a container this branch's checker accepts; the
    real H16 fixture is gated on PR #13's relocation-ordinal fix, so this
    exercises the pass path via a stubbed validator."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("hwx_check", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    p = tmp_path / "ok.hwx"
    p.write_bytes(b"x")
    orig = mod.validate
    mod.validate = lambda path: type("I", (), {"subtype": 7, "tasks": 1,
        "surface_count": 2, "text": type("T", (), {"size": 16})(),
        "regions": []})()
    try:
        rc = mod.main([str(p)])
    finally:
        mod.validate = orig
    assert rc == 0


def test_annotation_without_nul_is_rejected(tmp_path):
    """cmd 8 payload with no NUL byte: must be an explicit rejection, not an
    accidental pass through the padding comparison (fix: reject ann < 0)."""
    hdr = (struct.pack("<I", 0xBEEFFACE) + struct.pack("<I", 0x80) +
           struct.pack("<I", 9) + struct.pack("<I", 2) + struct.pack("<I", 1) +
           struct.pack("<I", 16) + struct.pack("<I", 0x200000) + struct.pack("<I", 0))
    p = tmp_path / "ann.hwx"
    p.write_bytes(hdr + b"\x08" + struct.pack("<I", 16) + b"A" * 8)
    r = run_check(str(p))
    assert r.returncode == 1, f"stdout={r.stdout}"
    assert "FAIL" in r.stdout
    assert "annotation" in r.stdout
