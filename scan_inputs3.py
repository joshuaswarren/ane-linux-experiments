#!/usr/bin/env python3
"""scan_inputs3: self-contained. At the first prog_002 execute: fingerprint
search for every input port's raw buffer across mapped regions, then read
each hit's full buffer and compare RAW vs RAW. Dumps transformed copies."""
import ctypes
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np

os.environ["ANEFORGE_PATH"] = "/tmp/aneforge-capture-fix"
sys.path.insert(0, "/tmp/aneforge-capture-fix")
import aneforge._runtime as rt  # noqa: E402

DUMP = Path("/tmp/jw16-first-submit-ref4b/input-surfaces2")
DUMP.mkdir(exist_ok=True)
lib = rt._lib._ensure()

TARGET = (["t7", "t2", "t0", "t20"], ["t15", "t31", "t35", "t37", "t41", "t50", "t52", "t53"])
HIT = [False]


def task_port():
    libc = ctypes.CDLL(None)
    return int(ctypes.c_uint32.in_dll(libc, "mach_task_self_").value)


def read_at(task, addr, size):
    libc = ctypes.CDLL(None)
    buf = (ctypes.c_ubyte * size)()
    outsz = ctypes.c_uint64(0)
    kr = libc.mach_vm_read_overwrite(
        ctypes.c_uint(task), ctypes.c_uint64(addr), ctypes.c_uint64(size),
        ctypes.cast(buf, ctypes.c_void_p), ctypes.byref(outsz))
    if kr != 0:
        return None
    return bytes(buf[:outsz.value])


def walk_regions(libc):
    task = task_port()
    addr = ctypes.c_uint64(0)
    info = ctypes.c_uint32 * 15
    regions = []
    while True:
        depth = ctypes.c_uint32(0)
        infocnt = ctypes.c_uint32(15)
        size = ctypes.c_uint64(0)
        a2 = ctypes.c_uint64(addr.value)
        infostruct = info()
        kr = libc.mach_vm_region_recurse(
            ctypes.c_uint(task), ctypes.byref(a2), ctypes.byref(size),
            ctypes.byref(depth), ctypes.byref(infostruct), ctypes.byref(infocnt))
        if kr != 0:
            break
        words = struct.unpack_from("15I", bytes(infostruct))
        prot = int(words[0])
        regions.append((int(a2.value), int(size.value), prot))
        addr = ctypes.c_uint64(int(a2.value) + int(size.value))
    return regions


orig_execute = rt.Program.execute


def patched_execute(self):
    is_target = (list(self._inputs) == TARGET[0] and list(self._outputs) == TARGET[1])
    result = orig_execute(self)
    if is_target and not HIT[0]:
        HIT[0] = True
        libc = ctypes.CDLL(None)
        task = task_port()
        # SOURCES: raw ANE-visible input buffers
        srcs = {}
        for p in self._inputs:
            ptr, nbytes = ctypes.c_void_p(), ctypes.c_size_t()
            rc = lib.ane_e5rt_program_input_buffer(
                self._handle, p.encode(), ctypes.byref(ptr), ctypes.byref(nbytes))
            if rc == 0 and ptr.value:
                srcs[p] = (ctypes.string_at(ptr.value, nbytes.value), int(nbytes.value),
                           int(ptr.value))
        print("sources:", {p: (hex(srcs[p][2]), srcs[p][1]) for p in srcs}, flush=True)
        regions = walk_regions(libc)
        print(f"regions: {len(regions)}", flush=True)
        # build search space once: concatenated readable regions with base map
        for port, (raw, nb, src_addr) in srcs.items():
            fp = raw[:512]
            hits = []
            for a, s, prot in regions:
                if s < 4096 or not (prot & 1):
                    continue
                if a == src_addr:
                    continue
                blob = read_at(task, a, min(s, 256 * 1024 * 1024))
                if blob is None:
                    continue
                start = 0
                while True:
                    j = blob.find(fp, start)
                    if j < 0:
                        break
                    hits.append(a + j)
                    start = j + 512
            print(f"port {port}: {len(hits)} surface copies found", flush=True)
            for h in hits:
                got = read_at(task, h, nb)
                if got is None:
                    print(f"  {h:#x}: unreadable", flush=True)
                    continue
                if got == raw:
                    print(f"  {h:#x}: IDENTICAL full buffer", flush=True)
                    continue
                a = np.frombuffer(got, dtype=np.uint16)
                b = np.frombuffer(raw, dtype=np.uint16)
                nd = int(np.count_nonzero(a != b))
                name = f"{DUMP}/staged-{port}-{h:#x}.bin"
                open(name, "wb").write(got)
                print(f"  {h:#x}: TRANSFORMED {nd}/{b.size} differ -> dumped {name}", flush=True)
        print("COPY-COMPLETE", flush=True)
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
