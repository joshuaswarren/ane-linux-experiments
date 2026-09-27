#!/usr/bin/env python3
"""Dump the staged weight region via mach_vm_read_overwrite (safe reads)."""
import ctypes
import itertools
import os
import sys

import numpy as np

os.environ["ANEFORGE_PATH"] = "/tmp/aneforge-capture-fix"
sys.path.insert(0, "/tmp/aneforge-capture-fix")

KERN = open("/tmp/jw16-first-submit-ref4b/kern.bin", "rb").read()
libc = ctypes.CDLL(None)


def task_port():
    libc2 = ctypes.CDLL(None)
    return ctypes.c_uint32.in_dll(libc2, "mach_task_self_").value


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


def read_safe(addr, size):
    """mach_vm_read_overwrite into a fresh buffer; returns bytes or None."""
    buf = (ctypes.c_ubyte * size)()
    outsz = ctypes.c_uint64(0)
    kr = libc.mach_vm_read_overwrite(
        ctypes.c_uint32(task_port()), ctypes.c_uint64(addr), ctypes.c_uint64(size),
        ctypes.cast(buf, ctypes.c_void_p), ctypes.byref(outsz))
    if kr != 0:
        return None
    return bytes(buf[: outsz.value])


def walk_regions():
    task = ctypes.c_uint32(task_port())
    addr = ctypes.c_uint64(0)
    info = VMRegionSubmapInfo64()
    out = []
    while True:
        depth = ctypes.c_uint32(0)
        infocnt = ctypes.c_uint32(len(VMRegionSubmapInfo64._fields_))
        size = ctypes.c_uint64(0)
        a2 = ctypes.c_uint64(addr.value)
        kr = libc.mach_vm_region_recurse(
            task, ctypes.byref(a2), ctypes.byref(size), ctypes.byref(depth),
            ctypes.byref(info), ctypes.byref(infocnt))
        if kr != 0:
            break
        out.append((int(a2.value), int(size.value), int(info.protection)))
        addr = ctypes.c_uint64(int(a2.value) + int(size.value))
    return out


def main():
    kh = np.frombuffer(KERN[:1024 * 1024], dtype=np.uint16)
    khist = np.bincount(kh, minlength=65536)
    cands = []
    for a, s, p in walk_regions():
        if s < 60 * 1024 * 1024 or not (p & 1):
            continue
        raw = read_safe(a, 1024 * 1024)
        if raw is None:
            print(f"region {a:#x}+{s:#x}: unreadable", flush=True)
            continue
        ah = np.bincount(np.frombuffer(raw, dtype=np.uint16), minlength=65536)
        corr = float(np.corrcoef(ah, khist)[0, 1]) if ah.sum() and khist.sum() else 0.0
        print(f"region {a:#x}+{s:#x}: corr={corr:.4f}", flush=True)
        if corr > 0.9:
            cands.append((a, s))
    kh = np.frombuffer(KERN[:1024 * 1024], dtype=np.uint16)
    khist = np.bincount(kh, minlength=65536)
    for a, s in cands:
        # find the kernel fingerprint inside the region and dump the whole region
        CH = 16 * 1024 * 1024
        hit = None
        pos = 0
        while pos < s and hit is None:
            n = min(CH, s - pos)
            chunk = read_safe(a + pos, n)
            if chunk is None:
                pos += n
                continue
            j = chunk.find(KERN[:4096])
            if j >= 0:
                hit = pos + j
            pos += n
        print(f"region {a:#x} size {s:#x}: kernel fingerprint at region offset "
              f"{hex(hit) if hit is not None else 'NOT FOUND'}", flush=True)
        full = read_safe(a, s)
        if full is None:
            print("full read failed", flush=True)
            continue
        name = f"/tmp/jw16-first-submit-ref4b/scan/staged-full-{a:#x}.bin"
        os.makedirs(os.path.dirname(name), exist_ok=True)
        open(name, "wb").write(full)
        print(f"dumped {name} ({len(full)} bytes)", flush=True)


main()
