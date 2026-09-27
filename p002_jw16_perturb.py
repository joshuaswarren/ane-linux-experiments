#!/usr/bin/env python3
"""jw16 mirror of the Apple slot-perturbation probe for prog_002.
Perturbs quarter-groups of the compact inputs at banks 4 (t0), 6 (t7),
15 (t2) + state@7 quarters; saves outputs per config for comparison
against Apple's response patterns."""
import itertools
import mmap
import struct
from contextlib import ExitStack
from pathlib import Path

import fcntl
import numpy as np

src = open("/var/tmp/jw16-first-submit/prog002_verify.py").read().split("def main()")[0]
exec(src)

OUT = Path("/var/tmp/jw16-first-submit/out/perturb")
OUT.mkdir(exist_ok=True)


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


state_win = t20.reshape(-1).astype(np.float16).tobytes()
state_win += b"\x00" * (393216 - len(state_win))
BASE = {4: t0.reshape(-1).astype(np.float16).copy(), 5: t2.reshape(-1).astype(np.float16).copy(),
        6: t7.reshape(-1).astype(np.float16).copy(), 15: t2.reshape(-1).astype(np.float16).copy(),
        7: np.frombuffer(state_win, dtype=np.float16).copy()}

def merge(binds):
    out = {b: pb for b, pb in OUT_PREFILL.items()}
    out.update(binds)
    return out


base_outs = submit_bind(merge({b: a.tobytes() for b, a in BASE.items()}))
base_sig = {b: hashlib.sha256(v).hexdigest()[:8] for b, v in base_outs.items()}
print("base:", base_sig, flush=True)

count = 0
for bank, n_el in ((4, 2048), (6, 2048), (15, 2048)):
    gsz = n_el // 4
    for g in range(4):
        a = BASE[bank].copy()
        a[g * gsz:(g + 1) * gsz] = (a[g * gsz:(g + 1) * gsz].astype(np.float32) + 0.25).astype(np.float16)
        binds = {b: x.tobytes() for b, x in BASE.items()}
        binds[bank] = a.tobytes()
        outs = submit_bind(merge(binds))
        for b, port in zip(OUT_BANKS, OUT_PORTS):
            ref = REFS[port].reshape(-1)
            x = np.frombuffer(outs[b], dtype=np.float16)
            if port in ("t41", "t50"):
                got = x[:16 * 32].reshape(16, 32)[:, 0]
            elif port == "t53":
                got = x[:6144 * 32].reshape(6144, 32)[:, :3].reshape(-1)
            else:
                got = x[:ref.size]
            b0 = np.frombuffer(base_outs[b], dtype=np.float16)
            if port in ("t41", "t50"):
                b0g = b0[:16 * 32].reshape(16, 32)[:, 0]
            elif port == "t53":
                b0g = b0[:6144 * 32].reshape(6144, 32)[:, :3].reshape(-1)
            else:
                b0g = b0[:ref.size]
            nd = int(np.count_nonzero(got.view(np.uint16) != b0g.view(np.uint16)))
            print(f"bank{bank} g{g} -> {port}: diff={nd}/{ref.size}", flush=True)
        count += 1
print(f"jw16 probe done: {count} configs", flush=True)
