#!/usr/bin/env python3
"""Diag2: t53 output slot-map search (6 permutations) on one combo."""
import importlib.util
import mmap
import struct
from contextlib import ExitStack
from itertools import permutations

import numpy as np

spec = importlib.util.spec_from_file_location("pv", "/var/tmp/jw16-first-submit/prog002_verify.py")
src = open("/var/tmp/jw16-first-submit/prog002_verify.py").read().split("def main()")[0]
exec(src)

assign = {"t0": 4, "t2": 5, "t7": 6, "t20": 7}
datas = {"t7": t7.reshape(-1).tobytes(), "t2": t2.reshape(-1).tobytes(),
         "t0": t0.reshape(-1).tobytes(), "t20": pack_state(t20)}
binds = {**{bank: datas[name] for name, bank in assign.items()},
         **{b: pb for b, pb in OUT_PREFILL.items()}}

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
        ref = REFS["t53"].reshape(-1)
        raw = np.frombuffer(B[14].read(), dtype=np.float16)
        a = raw[:6144 * 32].reshape(6144, 32)
        for perm in permutations((0, 1, 2)):
            got = a[:, list(perm)].reshape(-1)
            m = int(np.count_nonzero(got.view(np.uint16) == ref.view(np.uint16)))
            print(f"t53 slots {perm}: {m}/18432", flush=True)
        # also: does out t53 equal the packed input state surface verbatim?
        inpack = pack_state(t20)
        print("out t53 surface == packed in-t20 surface:",
              bool((raw[:6144 * 32].view(np.uint16) ==
                    np.frombuffer(inpack, dtype=np.uint16)).all()), flush=True)
