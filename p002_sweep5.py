#!/usr/bin/env python3
"""prog_002 final: compact state@7 (dense ch7 read), 6 input permutations
over consumed banks {4,6,15}; t53 extracted COMPACT [6144,3]."""
import itertools
import mmap
import struct
from contextlib import ExitStack
from pathlib import Path

import fcntl
import numpy as np

src = open("/var/tmp/jw16-first-submit/prog002_verify.py").read().split("def main()")[0]
exec(src)

state_win = t20.reshape(-1).astype(np.float16).tobytes()
state_win += b"\x00" * (393216 - len(state_win))
NAME_DATA = {"t0": t0.reshape(-1).tobytes(), "t7": t7.reshape(-1).tobytes(),
             "t2": t2.reshape(-1).tobytes()}


def submit_bind(binds):
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
            return {bank: B[bank].read() for bank in OUT_PREFILL}


count = 0
for perm in itertools.permutations((4, 6, 15)):
    namebank = dict(zip(("t0", "t7", "t2"), perm))
    binds = {7: state_win}
    for name, bank in namebank.items():
        binds[bank] = NAME_DATA[name]
    for b, pb in OUT_PREFILL.items():
        binds[b] = pb
    count += 1
    outs = submit_bind(binds)
    results = []
    allok = True
    for bank, port in zip(OUT_BANKS, OUT_PORTS):
        ref = REFS[port].reshape(-1)
        x = np.frombuffer(outs[bank], dtype=np.float16)
        if port in ("t41", "t50"):
            got = x[:16 * 32].reshape(16, 32)[:, 0]
        elif port == "t53":
            got = x[:18432]
        else:
            got = x[:ref.size]
        m = int(np.count_nonzero(got.view(np.uint16) == ref.view(np.uint16)))
        results.append(f"{port}:{m}/{ref.size}")
        if m != ref.size:
            allok = False
    tag = " ".join(f"{nm}@{bk}" for bk, nm in namebank.items())
    print(("WIN " if allok else "no  ") + tag + " | " + " ".join(results), flush=True)
print("combos:", count, flush=True)
