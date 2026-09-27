#!/usr/bin/env python3
"""Check: with compact state@7, is out-t53 surface[:36864] == compact input?"""
import itertools
import mmap
import struct
from contextlib import ExitStack

import fcntl
import numpy as np

src = open("/var/tmp/jw16-first-submit/prog002_verify.py").read().split("def main()")[0]
exec(src)

state_win = t20.reshape(-1).astype(np.float16).tobytes()
state_win += b"\x00" * (393216 - len(state_win))
binds = {4: t0.reshape(-1).tobytes(), 6: t7.reshape(-1).tobytes(), 7: state_win}
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
            b.write(b"\x00" * b.size)
            b.write(db)
            B[bank] = b
        req = runtime.Submit(tsk_size=stage["task_stream_size"], td_count=stage["td_count"],
                             td_size=stage["td_size"], btsp_handle=btsp.bo.handle, pad=0)
        req.handles[0] = command.bo.handle
        req.handles[3] = ws.bo.handle
        for bank, b in B.items():
            req.handles[bank] = b.bo.handle
        fcntl.ioctl(device.fd, runtime.IOCTL_SUBMIT, req)
        out14 = B[14].read()
        out15 = B[5].read()
        out8 = B[8].read()
        out9 = B[9].read()
        out10 = B[10].read()
        out13 = B[13].read()
        inwin = state_win
        n = len(t20.reshape(-1).tobytes())
        same = out14[:n] == inwin[:n]
        print(f"out14[:{n}] == compact in-state: {same}")
        nd = int(np.count_nonzero(np.frombuffer(out14[:n], dtype=np.uint16) !=
                                  np.frombuffer(inwin[:n], dtype=np.uint16)))
        print(f"differing elements: {nd}/{n // 2}")
        # ref comparison at logical level
        ref53 = REFS["t53"].reshape(-1)
        got = np.frombuffer(out14, dtype=np.float16)[:6144 * 32].reshape(6144, 32)[:, :3].reshape(-1)
        print("t53 logical matches:", int(np.count_nonzero(got.view(np.uint16) == ref53.view(np.uint16))), "/18432")
        for bank, port in ((5, "t15"), (8, "t31"), (9, "t35"), (10, "t37"), (13, "t52")):
            x = np.frombuffer(locals()[f"out{bank}" if False else {5:"out15",8:"out8",9:"out9",10:"out10",13:"out13"}[bank]], dtype=np.float16)
            ref = REFS[port].reshape(-1)
            m = int(np.count_nonzero(x[:ref.size].view(np.uint16) == ref.view(np.uint16)))
            print(f"{port} (bank {bank}): {m}/{ref.size}")
