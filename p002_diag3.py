#!/usr/bin/env python3
"""Diag3: probe prog_002's state surface slot map via the pass-through.

Feed identity-packed state (logical cols 0,1,2 at slots 0,1,2 of each
64-B row), read the t53 output surface, and locate each row's input
values among the output row's 32 slots."""
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
        surf = raw[:6144 * 32].reshape(6144, 32)
        # For a sample of rows: locate each of the 3 in-values in the out row
        votes = {}
        for i in list(range(0, 6144, 384)) + [6143]:
            invals = inmat[i]
            row = surf[i]
            slots = []
            for c in range(3):
                hits = [s for s in range(32) if row[s].view(np.uint16) == invals[c].view(np.uint16)]
                slots.append(hits)
            print(f"row {i}: in-cols found at slots {slots}", flush=True)
        # global vote over GLOBALLY-UNIQUE values only
        flat = inmat.reshape(-1).view(np.uint16)
        uniq, cnts = np.unique(flat, return_counts=True)
        uniqset = set(int(u) for u, c in zip(uniq, cnts) if c == 1)
        slotvotes = np.zeros((3, 32), dtype=int)
        used = 0
        for i in range(6144):
            rowu = surf[i].view(np.uint16)
            rowmap = {}
            for c in range(3):
                v = int(inmat[i, c].view(np.uint16))
                if v not in uniqset:
                    continue
                hits = np.flatnonzero(rowu == np.uint16(v & 0xFFFF))
                if len(hits) == 1:
                    slotvotes[c, hits[0]] += 1
                    used += 1
        print("unique values used:", used, flush=True)
        for c in range(3):
            top = np.argsort(slotvotes[c])[::-1][:4]
            print(f"col {c}: top slots {[(int(t), int(slotvotes[c][t])) for t in top if slotvotes[c][t]]}",
                  flush=True)
