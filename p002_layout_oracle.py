#!/usr/bin/env python3
"""State layout pass-through oracle: which window layout makes the engine's
t53 output carry the input's columns."""
import mmap
import struct
from contextlib import ExitStack
from pathlib import Path

import fcntl
import numpy as np

src = open("/var/tmp/jw16-first-submit/prog002_verify.py").read().split("def main()")[0]
exec(src)

compact = t20.reshape(-1).astype(np.float16).tobytes()
padded = np.zeros((6144, 32), dtype=np.float16)
padded[:, :3] = t20
padded = padded.tobytes()
planes = t20.T.reshape(-1).astype(np.float16).tobytes()
LAYOUTS = {"compact": compact, "padded": padded, "planes": planes}


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


OUT_PREFILL[7] = bytes(393216)  # read back the state window too
for nm, sw in LAYOUTS.items():
    binds = {4: t0.reshape(-1).tobytes(), 5: t2.reshape(-1).tobytes(),
             6: t7.reshape(-1).tobytes(), 15: t0.reshape(-1).tobytes(), 7: sw}
    for b, pb in OUT_PREFILL.items():
        binds[b] = pb
    outs = submit_bind(binds)
    wv = np.frombuffer(outs[7], dtype=np.float16)
    inm = t20.reshape(6144, 3)
    gotA = wv[:18432].reshape(6144, 3)
    mA = int(np.count_nonzero(gotA.view(np.uint16) == inm.view(np.uint16)))
    gotB = wv[:6144 * 32].reshape(6144, 32)[:, :3].reshape(-1)
    refB = inm.reshape(-1)
    gotB = gotB[:refB.size]
    mB = int(np.count_nonzero(gotB.view(np.uint16) == refB.view(np.uint16)))
    ref_flat = inm.reshape(-1)
    gotC = wv[:18432].reshape(3, 6144).T.reshape(-1)[:ref_flat.size]
    mC = int(np.count_nonzero(gotC.view(np.uint16) == ref_flat.view(np.uint16)))
    print(f"state[{nm:8s}]: out-as-compact={mA}/18432 out-as-padded={mB}/18432 out-as-planes={mC}/18432",
          flush=True)
