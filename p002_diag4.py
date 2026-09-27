#!/usr/bin/env python3
"""Diag4: global search for unique in-values across the whole t53 surface."""
import importlib.util
import mmap
import struct
from contextlib import ExitStack

import numpy as np

src = open("/var/tmp/jw16-first-submit/prog002_verify.py").read().split("def main()")[0]
exec(src)

datas = {"t7": t7.reshape(-1).tobytes(), "t2": t2.reshape(-1).tobytes(),
         "t0": t0.reshape(-1).tobytes(), "t20": pack_state(t20)}
binds = {5: datas["t7"], 6: datas["t2"], 4: datas["t0"], 7: datas["t20"]}
for b, pb in OUT_PREFILL.items():
    binds[b] = pb

with ANEC.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
    bases = probe.task_bases(data, probe.HEADER_SIZE, stage["task_stream_size"])
    with ExitStack() as bufs:
        device = bufs.enter_context(runtime.Device(qid=None))
        command = bufs.enter_context(device.buffer(stage["content_size"]))
        probe.copy_content(data, probe.HEADER_SIZE, stage["content_size"], command.map)
        ws = bufs.enter_context(device.buffer(stage["workspace_size"]))
        ws.write(b"\0" * stage["workspace_size"])
        btsp = bufs.enter_context(device.buffer(stage["task_stream_size"]))
        boot = probe.build_original_prefix(data, probe.HEADER_SIZE,
                                           stage["task_stream_size"], bases,
                                           stage["td_count"])
        btsp.write(boot)
        fw = struct.unpack_from("<I", btsp.map)[0]
        btsp.map.seek(0)
        btsp.map.write(struct.pack("<I", (fw & 0xF00FFFF) | (0x40 << 16)))
        B = {}
        for bank, db in sorted(binds.items()):
            b = bufs.enter_context(device.buffer(tile(len(db))))
            b.write(b"\xff" * b.size)
            b.write(db)
            B[bank] = b
        req = runtime.Submit(tsk_size=stage["task_stream_size"], td_count=stage["td_count"],
                             td_size=stage["td_size"], btsp_handle=btsp.bo.handle, pad=0)
        req.handles[0] = command.bo.handle
        req.handles[3] = ws.bo.handle
        for bank, b in B.items():
            req.handles[bank] = b.bo.handle
        fcntl.ioctl(device.fd, runtime.IOCTL_SUBMIT, req)
        raw = np.frombuffer(B[14].read(), dtype=np.float16)
        inmat = t20.reshape(6144, 3)
        surf = raw.view(np.uint16)  # whole 196608-element surface
        flat = inmat.reshape(-1).view(np.uint16)
        uniq, cnts = np.unique(flat, return_counts=True)
        uniqset = set(int(u) for u, c in zip(uniq, cnts) if c == 1)
        # for unique values: (logical_index (i,c)) -> surface flat index
        found = {}
        for i in range(6144):
            for c in range(3):
                v = int(inmat[i, c].view(np.uint16))
                if v in uniqset:
                    hits = np.flatnonzero(surf == np.uint16(v & 0xFFFF))
                    if len(hits) == 1:
                        found[(i, c)] = int(hits[0])
        print("unique values located:", len(found), "of", len(uniqset), flush=True)
        for (i, c), f in sorted(found.items())[:24]:
            print(f"  logical ({i},{c}) -> surf flat {f} (row {f//32}, slot {f%32})", flush=True)
        # derive pattern: col2 at (i, slot1)?  col0/col1 at?
        import collections
        bycol = {0: [], 1: [], 2: []}
        for (i, c), f in found.items():
            bycol[c].append((i, f))
        for c in (0, 1, 2):
            pts = bycol[c][:8]
            print(f"col {c}: {[(i, f//32, f%32) for i, f in pts]}", flush=True)
