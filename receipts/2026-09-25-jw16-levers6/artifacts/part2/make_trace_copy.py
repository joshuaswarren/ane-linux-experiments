#!/usr/bin/env python3
"""Derive fused_e2e_trace.py from fused_e2e.py: stage trace_markers + abs t0/t1.

Runs ON jw16. Asserts every patch applied exactly once; prints sha256 of both.
"""
import hashlib
import sys

SRC = "/var/tmp/parakeet-recover/fused_e2e.py"
DST = "/var/tmp/parakeet-recover/fused_e2e_trace.py"

src = open(SRC).read()

old_run = """    def run(self, name: str, work):
        before = self._snapshot()
        started = time.monotonic_ns()
        result = work()
        elapsed = time.monotonic_ns() - started
        after = self._snapshot()
        self.records.append(
            {
                "stage": name,
                "wall_ns": elapsed,
                "wall_ms": round(elapsed / 1e6, 3),
"""
new_run = """    def run(self, name: str, work):
        before = self._snapshot()
        started = time.monotonic_ns()
        _trace_marker(f"PARAKEET_BEGIN {name}")
        result = work()
        _trace_marker(f"PARAKEET_END {name}")
        elapsed = time.monotonic_ns() - started
        after = self._snapshot()
        self.records.append(
            {
                "stage": name,
                "wall_ns": elapsed,
                "wall_ms": round(elapsed / 1e6, 3),
                "t0_ns": started,
                "t1_ns": started + elapsed,
"""
assert src.count(old_run) == 1, "Stages.run anchor not unique"
src = src.replace(old_run, new_run)

helper = '''
_TRACE_MARKER_FP = None

def _trace_marker(msg: str) -> None:
    """Emit a stage boundary into the ftrace ring (no-op if unavailable)."""
    global _TRACE_MARKER_FP
    if _TRACE_MARKER_FP is None:
        import os as _os
        path = _os.environ.get(
            "PARAKEET_TRACE_MARKER", "/sys/kernel/tracing/trace_marker")
        try:
            _TRACE_MARKER_FP = open(path, "w")
        except OSError:
            _TRACE_MARKER_FP = False
    if _TRACE_MARKER_FP:
        _TRACE_MARKER_FP.write(msg + "\\n")
        _TRACE_MARKER_FP.flush()

'''
anchor = "\nclass Stages:"
assert src.count(anchor) == 1, "class Stages anchor not unique"
src = src.replace(anchor, helper + anchor)

open(DST, "w").write(src)
for p in (SRC, DST):
    print(hashlib.sha256(open(p, "rb").read()).hexdigest(), p)
