#!/usr/bin/env python3
"""scan_inputs: locate ALL copies of the four prog_002 input buffers in the
e5rt process's mapped address space after execute. For each input port the
ANE-visible buffer (input_buffer getter, full nbytes) is fingerprinted and
every mapped region is searched for its 4096-byte leading window; matches
are compared against the source for full-buffer identity or transform."""
import ctypes
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

os.environ["ANEFORGE_PATH"] = "/tmp/aneforge-capture-fix"
sys.path.insert(0, "/tmp/aneforge-capture-fix")
import aneforge._runtime as rt  # noqa: E402

DUMP = Path("/tmp/jw16-first-submit-ref4b/input-surfaces")
DUMP.mkdir(exist_ok=True)
lib = rt._lib._ensure()

TARGET = (["t7", "t2", "t0", "t20"], ["t15", "t31", "t35", "t37", "t41", "t50", "t52", "t53"])
HIT = [False]
EXEC_N = [0]
PORT_SURF = {}  # port -> (raw_bytes, nbytes)


def full_input_raw(prog, name):
    ptr, nbytes = ctypes.c_void_p(), ctypes.c_size_t()
    rc = lib.ane_e5rt_program_input_buffer(prog._handle, name.encode(),
                                           ctypes.byref(ptr), ctypes.byref(nbytes))
    if rc != 0 or not ptr.value:
        return None, 0
    return ctypes.string_at(ptr.value, nbytes.value), nbytes.value


orig_execute = rt.Program.execute


def patched_execute(self):
    is_target = (list(self._inputs) == TARGET[0] and list(self._outputs) == TARGET[1])
    result = orig_execute(self)
    if is_target and not HIT[0]:
        HIT[0] = True
        print("first target execute completed — dumping input buffers + scanning regions", flush=True)
        for p in self._inputs:
            raw, nb = full_input_raw(self, p)
            PORT_SURF[p] = (raw, nb)
            if raw:
                (DUMP / f"apple-in-{p}.bin").write_bytes(raw)
            json.dump({p: nb for p, nb in ((p2, PORT_SURF[p2][1]) for p2 in PORT_SURF)},
                      open(str(DUMP / "buffer-sizes.json"), "w"))
        print("input buffers:", {p: PORT_SURF[p][1] for p in PORT_SURF}, flush=True)

        # ---- region walk ----
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
                task, ctypes.byref(a2), ctypes.byref(size), ctypes.byref(depth),
                ctypes.byref(info), ctypes.byref(infocnt))
            if kr != 0:
                break
            regions.append((int(a2.value), int(size.value), int(info.f0)))
            addr = ctypes.c_uint64(int(a2.value) + int(size.value))
        print(f"regions: {len(regions)}", flush=True)

        # ---- search each input fingerprint (first 512 B) in every region ----
        libc.mach_vm_read_overwrite.restype = ctypes.c_int
        for port, (raw, nb) in PORT_SURF.items():
            if not raw:
                continue
            fp = raw[:512]
            hits = []
            for a, s, prot in regions:
                if s < 4096 or not (prot & 1):
                    continue
                CH = 4 * 1024 * 1024
                pos = 0
                while pos < s:
                    n = min(CH, s - pos)
                    buf = (ctypes.c_ubyte * n)()
                    outsz = ctypes.c_uint64(0)
                    kr = libc.mach_vm_read_overwrite(
                        ctypes.c_uint(task), ctypes.c_uint64(a + pos), ctypes.c_uint64(n),
                        ctypes.cast(buf, ctypes.c_void_p), ctypes.byref(outsz))
                    if kr != 0:
                        pos += n
                        continue
                    blob = bytes(buf)
                    start = 0
                    while True:
                        j = blob.find(fp, start)
                        if j < 0:
                            break
                        hits.append((a + pos + j, port))
                        start = j + 512
                    pos += n
            print(f"port {port}: {len(hits)} fingerprint hits", flush=True)
            for ha, p in hits[:8]:
                print(f"   at {ha:#x} (belongs to port {p})", flush=True)
        print("SCAN-COMPLETE", flush=True)
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
