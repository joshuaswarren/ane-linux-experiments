#!/usr/bin/env python3
"""Inproc e5rt-bundle backend for staged_qwen_runner.py (Linux, omarchy-ane shim).

Lazy setup: on first model() this reads env
  STAGED_EXPORT       export dir (manifest.json + prog_NNN/cache/...)
  STAGED_INPROC_SHIM  ane_inproc shim .so      (default /var/tmp/encwall-decomp/libane_inproc_whole.so)
  STAGED_LIBANE       libane.so path           (default /usr/lib/libane.so)
and opens ONE InProcessAne session over all program bundle dirs.

backend contract: model(path) per program (path unused; program index = open order),
src_count/dst_count, predict(inarrs) -> list of fp16 arrays in out-port order.
Every submit is deadline-bounded and quarantine-checked by the shim; a failure
raises and terminates the run (contract linux_ane: fallback forbidden).
"""
import ctypes
import json
import os
import sys
from pathlib import Path

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.environ.get("STAGED_INPROC_DIR", "/var/tmp/encwall-decomp/inproc-tmp"))
from ane_inproc import InProcessAne

_SESSION = None
_MANIFEST = None


def _bundle_dir(prog_dir: Path) -> Path:
    cache = prog_dir / "cache"
    hits = [d for d in cache.rglob("*") if d.is_dir() and "bundlecache" in d.name]
    if hits:
        return hits[0]
    hits = [d for d in cache.iterdir() if d.is_dir()]
    return hits[0] if hits else cache


def _ensure_session():
    global _SESSION, _MANIFEST
    if _SESSION is not None:
        return
    export = Path(os.environ["STAGED_EXPORT"])
    _MANIFEST = json.load(open(export / "manifest.json"))
    shim = Path(os.environ.get("STAGED_INPROC_SHIM",
                               "/var/tmp/encwall-decomp/libane_inproc_whole.so"))
    libane = Path(os.environ.get("STAGED_LIBANE", "/usr/lib/libane.so"))
    bundles = {}
    for ci in range(_MANIFEST["n_programs"]):
        name = f"prog_{ci:03d}"
        bundles[name] = _bundle_dir(export / name)
    _SESSION = InProcessAne(shim, libane, bundles, deadline_ms=20000)


class model:
    _seq = 0

    def __init__(self, path, lib_path=None):
        _ensure_session()
        self.ci = model._seq
        model._seq += 1
        pr = _MANIFEST["programs"][self.ci]
        self.src_count = len(pr["srcs"])
        self.dst_count = len(pr["dsts"]) + len(pr["states"])
        self._name = f"prog_{self.ci:03d}"
        self._in_names = [s["port"] for s in pr["srcs"]]
        self._out_names = [x["port"] for x in pr["dsts"]] + \
                          [s["out_port"] for s in pr["states"]]
        self._out_sizes = [int(np.prod(s["shape"])) * 2 for s in pr["dsts"]] + \
                          [int(np.prod(s["out_shape"])) * 2 for s in pr["states"]]
        self._out_bufs = {n: ctypes.create_string_buffer(sz)
                          for n, sz in zip(self._out_names, self._out_sizes)}

    def predict(self, inarrs):
        assert len(inarrs) == self.src_count
        inputs = {n: np.ascontiguousarray(a, np.float16).tobytes()
                  for n, a in zip(self._in_names, inarrs)}
        _SESSION.submit(self._name, inputs, self._out_bufs)
        outs = []
        for n, sz in zip(self._out_names, self._out_sizes):
            a = np.frombuffer(bytes(self._out_bufs[n]), dtype=np.float16, count=sz // 2)
            outs.append(a)
        return outs

    def close(self):
        pass
