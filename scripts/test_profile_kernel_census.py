#!/usr/bin/env python3
"""Regression: analyze_kernel_census.py must identify kernels by the
profile event's KERNEL ENUM field "e" (declaration order in compute.h),
never by "op" (params.operation, a per-kernel code - e.g. the Qmm bit
width, so every op=4 Qmm Q4 dispatch must NOT collapse onto enum index 4
= CastBoolF32). GPU busy is (t1-t0) * meta.period_ns, not raw ticks.

Event-field contract: overlay/mlx/backend/omarchy/gpu_profiler.h
flush_slot emitf order is k,s,e,op,n,gx,gy,gz,h,tp,bar[,t0,t1],b.

Runnable: pytest scripts/test_profile_kernel_census.py, or
python3 scripts/test_profile_kernel_census.py
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CENSUS = (REPO / "receipts/2026-09-19-gated-barriers-default-t6001-test-host.d/"
          "analyze_kernel_census.py")

ENUM_NAMES = {4: "CastBoolF32", 412: "QmmVecQ4MultiSubgroupF16"}


def write_header(path):
    lines = ["enum class ComputeKernel : uint16_t {"]
    for i in range(413):
        lines.append("    %s," % ENUM_NAMES.get(i, "Filler%d" % i))
    lines.append("};")
    path.write_text("\n".join(lines) + "\n")


def write_profile(path):
    def d(**kw):
        base = {"k": "d", "s": 7, "gx": 1, "gy": 1, "gz": 1, "h": 5,
                "tp": 0, "bar": 1}
        base.update(kw)
        return json.dumps(base)

    recs = [
        json.dumps({"k": "meta", "device": "TestDevice", "period_ns": 2.0,
                    "valid_bits": 64, "pool": 65536, "label": "regression",
                    "host_t0": 1}),
        json.dumps({"k": "b", "o": 1, "dur": 3, "t": 2}),
        # Qmm Q4 decode dispatch: kernel enum 412, op carries bits=4.
        d(e=412, op=4, n=3564, t0=1000, t1=5001000),  # 5e6 ticks * 2ns = 10ms
        # A real bool->f32 cast: enum 4, op 0. Tiny on purpose.
        d(e=4, op=0, n=64, t0=0, t1=100000),          # 1e5 ticks * 2ns = 0.2ms
        # Pool-exhausted dispatch: no timestamps recorded; must be
        # skipped, never crash the census.
        d(e=412, op=4, n=3564),
        json.dumps({"k": "end", "t": 9, "dispatches": 3, "dropped": 1,
                    "submissions": 1, "joins": 1, "barriers": 2,
                    "barriers_skipped": 0}),
    ]
    path.write_text("\n".join(recs) + "\n")


def rows_by_name(stdout):
    rows = {}
    for line in stdout.splitlines():
        parts = line.split()
        # Row shape: <name> <ms 2dp> ms <pct>% n=<int> mean=<us> us
        if len(parts) >= 5 and parts[2] == "ms" and "." in parts[1]:
            rows[parts[0]] = {
                "ms": float(parts[1]),
                "pct": float(parts[3].rstrip("%")),
                "n": int(parts[4].split("=")[1]),
            }
    return rows


def test_census_groups_by_enum_e_with_period():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        header = Path(td) / "compute.h"
        profile = Path(td) / "prof.ndjson"
        write_header(header)
        write_profile(profile)
        proc = subprocess.run(
            [sys.executable, str(CENSUS), str(header), str(profile)],
            capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        out = proc.stdout
        # Skipped no-tick dispatch counted, never crashed on.
        assert "no-tick skipped=1" in out, out
        # Period conversion applied (5000 ticks at 2 ns = 10 ms, not 5).
        assert "total bracketed busy=10.2 ms" in out, out
        rows = rows_by_name(out)
        assert rows["QmmVecQ4MultiSubgroupF16"] == {
            "ms": 10.0, "pct": 98.0, "n": 1}, rows
        assert rows["CastBoolF32"] == {"ms": 0.2, "pct": 2.0, "n": 1}, rows
        # The op-indexed bug ranked CastBoolF32 first (names[4] with the
        # Qmm family's op=4 busy). Top kernel is the Qmm Q4 GEMV.
        top = out.splitlines()[1].split()[0]
        assert top == "QmmVecQ4MultiSubgroupF16", out


def run_census(*profiles):
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        header = Path(td) / "compute.h"
        write_header(header)
        paths = []
        for i, recs in enumerate(profiles):
            p = Path(td) / ("prof%d.ndjson" % i)
            p.write_text("\n".join(recs) + "\n")
            paths.append(p)
        return subprocess.run(
            [sys.executable, str(CENSUS), str(header)] + [str(p) for p in paths],
            capture_output=True, text=True, timeout=60)


META = json.dumps({"k": "meta", "device": "TestDevice", "period_ns": 2.0,
                   "valid_bits": 64, "pool": 65536, "label": "regression",
                   "host_t0": 1})


def test_rejects_negative_enum():
    bad = [META,
           json.dumps({"k": "d", "s": 7, "e": -1, "op": 0, "n": 1, "gx": 1,
                       "gy": 1, "gz": 1, "h": 5, "tp": 0, "bar": 1,
                       "t0": 0, "t1": 1000})]
    proc = run_census(bad)
    # Negative enum is corrupt data (profiler emits uint32): must be
    # rejected, never wrapped onto names[-1] (the LAST enum name).
    assert proc.returncode != 0, proc.stdout
    assert "enum" in (proc.stderr + proc.stdout).lower()


def test_rejects_file_without_own_meta():
    has_meta = [META,
                json.dumps({"k": "d", "s": 7, "e": 412, "op": 4, "n": 1,
                            "gx": 1, "gy": 1, "gz": 1, "h": 5, "tp": 0,
                            "bar": 1, "t0": 0, "t1": 5000000})]
    no_meta = [json.dumps({"k": "d", "s": 8, "e": 4, "op": 0, "n": 1,
                           "gx": 1, "gy": 1, "gz": 1, "h": 5, "tp": 0,
                           "bar": 1, "t0": 0, "t1": 100000})]
    proc = run_census(has_meta, no_meta)
    # A meta-less file must be rejected, not silently inherit the first
    # file's period_ns.
    assert proc.returncode != 0, proc.stdout
    assert "meta" in (proc.stderr + proc.stdout).lower()


def test_rejects_zero_total():
    noticks = [META,
               json.dumps({"k": "d", "s": 7, "e": 412, "op": 4, "n": 1,
                           "gx": 1, "gy": 1, "gz": 1, "h": 5, "tp": 0,
                           "bar": 1})]
    proc = run_census(noticks)
    # No timestamped dispatches: clear rejection, no ZeroDivisionError.
    assert proc.returncode != 0, proc.stdout
    assert "traceback" not in proc.stderr.lower()


if __name__ == "__main__":
    test_census_groups_by_enum_e_with_period()
    test_rejects_negative_enum()
    test_rejects_file_without_own_meta()
    test_rejects_zero_total()
    print("PASS: census groups by kernel enum e with period_ns conversion;"
          " rejects negative enum, meta-less file, zero total")
