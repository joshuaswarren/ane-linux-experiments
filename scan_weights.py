#!/usr/bin/env python3
"""scan_weights: locate the staged weight buffer(s) in our own address space.

Walks Mach VM regions, scans readable regions for the HWX kernel section's
leading fingerprint, and for every located copy diffs the full kernel image
vs the on-disk original. Exact and transformed copies are both reported;
transformed copies are dumped for transform derivation."""
import ctypes
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

os.environ["ANEFORGE_PATH"] = "/tmp/aneforge-capture-fix"
sys.path.insert(0, "/tmp/aneforge-capture-fix")

DUMP = Path("/tmp/jw16-first-submit-ref4b/scan")
DUMP.mkdir(exist_ok=True)
KERN_PATH = Path("/tmp/jw16-first-submit-ref4b/kern.bin")
KERN = KERN_PATH.read_bytes()
FP = KERN[:8192]
LIBC = ctypes.CDLL(None)


def task_port():
    libc = ctypes.CDLL(None)
    return ctypes.c_uint32.in_dll(libc, "mach_task_self_").value


class VMRegionSubmapInfo64(ctypes.Structure):
    _fields_ = [
        ("protection", ctypes.c_uint32), ("max_protection", ctypes.c_uint32),
        ("inheritance", ctypes.c_uint32), ("shared", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32), ("behavior", ctypes.c_uint32),
        ("user_wired_count", ctypes.c_uint32), ("offset", ctypes.c_uint64),
        ("user_tag", ctypes.c_uint32), ("pages_resident", ctypes.c_uint32),
        ("pages_shared_now_private", ctypes.c_uint32), ("pages_swapped_out", ctypes.c_uint32),
        ("pages_dirtied", ctypes.c_uint32), ("pages_reusable", ctypes.c_uint32),
        ("shadow_depth", ctypes.c_int32), ("dump_count", ctypes.c_uint32),
    ]


def walk_regions():
    libc = ctypes.CDLL(None)
    task = ctypes.c_uint32(task_port())
    addr = ctypes.c_uint64(0)
    size = ctypes.c_uint64(0)
    info = VMRegionSubmapInfo64()
    out = []
    while True:
        depth = ctypes.c_uint32(0)
        infocnt = ctypes.c_uint32(len(VMRegionSubmapInfo64._fields_))
        kr = libc.mach_vm_region_recurse(
            task, ctypes.byref(addr), ctypes.byref(size), ctypes.byref(depth),
            ctypes.byref(info), ctypes.byref(infocnt))
        if kr != 0:
            break
        out.append((int(addr.value), int(size.value), int(info.protection)))
        addr = ctypes.c_uint64(int(addr.value) + int(size.value))
    return out


def scan(kern):
    task_port()
    regions = walk_regions()
    big = [(a, s, p) for a, s, p in regions if s >= 64 * 1024 * 1024 and (p & 1)]
    print(f"regions >=64MB readable: {len(big)}", flush=True)
    hits = []
    for a, s, p in big:
        try:
            buf = ctypes.string_at(a, s)
        except Exception as e:
            print(f"  region {a:#x}+{s:#x} unreadable: {e}", flush=True)
            continue
        pos = 0
        found = []
        while True:
            pos = buf.find(FP, pos)
            if pos < 0:
                break
            found.append(pos)
            pos += 8192
        if found:
            print(f"  region {a:#x}+{s:#x}: {len(found)} fingerprint hits at {found[:4]}", flush=True)
            for loc in found:
                if loc + len(kern) <= s:
                    same = buf[loc:loc + len(kern)] == kern
                    hits.append((a, loc, same))
                    if not same:
                        (DUMP / f"staged-{a:#x}-{loc:#x}.bin").write_bytes(buf[loc:loc + len(kern)])
        else:
            # multiset fallback: compare value histograms on the first 1 MB
            a_hist = np.bincount(np.frombuffer(buf[:1024 * 1024], dtype=np.uint16), minlength=65536)
            k_hist = np.bincount(np.frombuffer(kern[:1024 * 1024], dtype=np.uint16), minlength=65536)
            if a_hist.sum() and k_hist.sum():
                corr = float(np.corrcoef(a_hist, k_hist)[0, 1])
                if corr > 0.9:
                    print(f"  region {a:#x}+{s:#x}: histogram corr {corr:.3f} — multiset candidate", flush=True)
    return hits


def report(hits):
    print("\n=== staged weight buffer report ===", flush=True)
    for a, loc, same in hits:
        print(f"region {a:#x} offset {loc:#x}: {'EXACT copy of kernel' if same else 'TRANSFORMED copy'}", flush=True)
    if not hits:
        print("no verbatim-fingerprint copies found — staged copy is transformed or absent", flush=True)


if __name__ == "__main__":
    if os.environ.get("SCAN_ONLY") == "1":
        report(scan(KERN))
        sys.exit(0)
    # pipeline mode: import after scan hook is armed
    import aneforge._runtime as rt  # noqa: E402

    TARGET_SIG = (["t7", "t2", "t0", "t20"], ["t15", "t31", "t35", "t37", "t41", "t50", "t52", "t53"])
    HIT = [False]

    orig_execute = rt.Program.execute

    def patched_execute(self):
        is_target = (list(self._inputs) == TARGET_SIG[0] and list(self._outputs) == TARGET_SIG[1])
        if is_target and not HIT[0]:
            HIT[0] = True
            print("target execute reached — scanning process memory", flush=True)
            hits = scan(KERN)
            report(hits)
        return orig_execute(self)

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
