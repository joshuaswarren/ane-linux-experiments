#!/usr/bin/env python3
"""Dump the full consolidated input staging region and map all four ports'
data positions within it."""
import ctypes
import json
import os
import sys
from pathlib import Path

import numpy as np

os.environ["ANEFORGE_PATH"] = "/tmp/aneforge-capture-fix"
sys.path.insert(0, "/tmp/aneforge-capture-fix")
import aneforge._runtime as rt  # noqa: E402

DUMP = Path("/tmp/jw16-first-submit-ref4b/scan")
DUMP.mkdir(exist_ok=True)
lib = rt._lib._ensure()
PORTS = ["t7", "t2", "t0", "t20"]
SURF = {}

TARGET = (["t7", "t2", "t0", "t20"], ["t15", "t31", "t35", "t37", "t41", "t50", "t52", "t53"])
HIT = [False]


def walk_regions():
    libc = ctypes.CDLL(None)
    task = int(ctypes.c_uint32.in_dll(libc, "mach_task_self_").value)

    class Info(ctypes.Structure):
        _fields_ = [(f"f{i}", ctypes.c_uint32) for i in range(7)] + \
                   [("offset", ctypes.c_uint64)] + \
                   [(f"g{i}", ctypes.c_uint32) for i in range(8)]

    addr = ctypes.c_uint64(0)
    regions = []
    while True:
        depth = ctypes.c_uint32(0)
        infocnt = ctypes.c_uint32(15)
        size = ctypes.c_uint64(0)
        a2 = ctypes.c_uint64(addr.value)
        info = Info()
        kr = libc.mach_vm_region_recurse(
            ctypes.c_uint(task), ctypes.byref(a2), ctypes.byref(size),
            ctypes.byref(depth), ctypes.byref(info), ctypes.byref(infocnt))
        if kr != 0:
            break
        regions.append((int(a2.value), int(size.value), int(info.f0)))
        addr = ctypes.c_uint64(int(a2.value) + int(size.value))
    return regions


orig_execute = rt.Program.execute


def patched_execute(self):
    is_target = (list(self._inputs) == TARGET[0] and list(self._outputs) == TARGET[1])
    result = orig_execute(self)
    if is_target and not HIT[0]:
        HIT[0] = True
        views = {}
        for p in PORTS:
            ptr, nbytes = ctypes.c_void_p(), ctypes.c_size_t()
            rc = lib.ane_e5rt_program_input_buffer(
                self._handle, p.encode(), ctypes.byref(ptr), ctypes.byref(nbytes))
            raw = ctypes.string_at(ptr.value, nbytes.value)
            SURF[p] = raw
            views[p] = np.ascontiguousarray(self.input_view(p)).astype(np.float16)
            (DUMP / f"apple-in-{p}.bin").write_bytes(raw)
        np.savez(str(DUMP / "views.npz"), **{f"v-{p}": v for p, v in views.items()})

        fp = {p: SURF[p][:256] for p in PORTS}
        CH = 4 * 1024 * 1024
        dumped = set()
        for a, sz, prot in walk_regions():
            if sz < 4096 or not (prot & 1):
                continue
            n = min(sz, 32 * 1024 * 1024)
            buf = (ctypes.c_ubyte * n)()
            outsz = ctypes.c_uint64(0)
            libc = ctypes.CDLL(None)
            kr = libc.mach_vm_read_overwrite(
                ctypes.c_uint(int(ctypes.c_uint32.in_dll(libc, "mach_task_self_").value)),
                ctypes.c_uint64(a), ctypes.c_uint64(n),
                ctypes.cast(buf, ctypes.c_void_p), ctypes.byref(outsz))
            if kr != 0:
                continue
            blob = bytes(buf[:outsz.value])
            for p in PORTS:
                j = blob.find(fp[p])
                if j >= 0 and a not in dumped:
                    dumped.add(a)
                    lo = max(0, j - 65536)
                    hi = min(len(blob), j + 262144)
                    (DUMP / f"staging-{a:#x}-j{j:#x}.bin").write_bytes(blob[lo:hi])
                    print(f"port {p}: copy at region {a:#x} + {j:#x} -> dumped {hi-lo} bytes", flush=True)
        if not dumped:
            print("no staging copies found this run", flush=True)
        os._exit(0)
    return result


rt.Program.execute = patched_execute

gguf = os.environ["ANEFORGE_GGUF"]
ref = json.load(open(os.environ["ANEFORGE_CHUNK"]))
pr = ref["prompts"][0]
ids = pr.get("prompt_token_ids") or pr.get("prompt_ids")
from aneforge.qwen35 import load_gguf  # noqa: E402
m = load_gguf(gguf, resid_scale=1.0)
m.ane_lm_head = False
gen = m.generate(ids, max_new_tokens=1, temperature=0.0, top_p=1.0, top_k=0,
                 batched_prefill=False)
print(f"generated: {gen}", flush=True)
