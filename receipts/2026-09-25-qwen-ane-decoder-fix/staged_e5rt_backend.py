#!/usr/bin/env python3
"""ANEForge e5rt backend for staged_qwen_runner.py -- VALIDATION ONLY (macOS).

The bootstrap (run-e5rt-backend.py) imports THIS module and calls setup(chunks);
the runner later loads this same FILE under a different module object via
importlib -- so state resolves through sys.modules["staged_e5rt_backend"],
never through this file's own globals.

model(path): path is ignored; chunk index = open sequence (manifest order).
predict(inarrs): feeds srcs to the e5rt program in input_ports order, executes,
returns outputs in output_ports order (lane dsts then state outs).
"""
import hashlib
import json
import os
import sys
import numpy as np

_LOGPATH = os.environ.get("STAGED_SHIM_LOG")
_seq = {"n": 0}


def _mod():
    m = sys.modules.get("staged_e5rt_backend")
    assert m is not None and getattr(m, "_ref", None) is not None, \
        "run-e5rt-backend.py must import staged_e5rt_backend and call setup(chunks) first"
    return m


def setup(chunks):
    global _ref
    _ref = chunks


class model:
    _seq = 0

    def __init__(self, path, lib_path=None):
        m = _mod()
        self.ci = m.model._seq
        m.model._seq += 1
        self.net = m._ref[self.ci]["net"]
        self.in_ports = list(self.net.input_ports)    # [(tensor, port)] ordered
        self.out_ports = list(self.net.output_ports)
        self.src_count = len(self.in_ports)
        self.dst_count = len(self.out_ports)

    def predict(self, inarrs):
        pr = self.net.prog
        assert len(inarrs) == self.src_count
        rec = None
        if _LOGPATH:
            _seq["n"] += 1
            rec = {"seq": _seq["n"], "ci": self.ci, "in": [], "out": []}
        for (t, port), arr in zip(self.in_ports, inarrs):
            if rec is not None:
                rec["in"].append([str(port), hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()[:12]])
            pr.set_input(port, arr)
        pr.execute()
        outs = [pr.read_output(port) for _, port in self.out_ports]
        if rec is not None:
            for (_, port), arr in zip(self.out_ports, outs):
                rec["out"].append([str(port), hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()[:12]])
            with open(_LOGPATH, "a") as f:
                f.write(json.dumps(rec) + "\n")
        return outs

    def close(self):
        pass
