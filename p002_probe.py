#!/usr/bin/env python3
"""p002_probe: per-input consumption map for prog_002 on jw16.
Base binding: t0@4 t2@5 t7@6 state@7 (compact+tail). Each probe perturbs
ONE input (+4.0 on all its elements, or zeros for state) and diffs all
8 outputs bitwise vs base."""
import itertools
import mmap
import struct
from contextlib import ExitStack
from pathlib import Path

import fcntl
import numpy as np

src = open("/var/tmp/jw16-first-submit/prog002_verify.py").read().split("def main()")[0]
exec(src)

OUT = Path("/var/tmp/jw16-first-submit/out")


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
            return {bank: B[bank].read() for bank in OUT_PREFILL}


state_win = t20.reshape(-1).astype(np.float16).tobytes()
state_win += b"\xff" * (393216 - len(state_win))
base_datas = {4: t0.reshape(-1).tobytes(), 5: t2.reshape(-1).tobytes(),
              6: t7.reshape(-1).tobytes(), 7: state_win}


def perturb(x, mode):
    a = np.frombuffer(x, dtype=np.float16).copy()
    if mode == "add4":
        a = (a.astype(np.float32) + 4.0).astype(np.float16)
    elif mode == "zero":
        a[:] = 0
    return a.tobytes()


def run(binds_extra):
    binds = dict(base_datas)
    binds.update(binds_extra)
    for b, pb in OUT_PREFILL.items():
        binds[b] = pb
    return submit_bind(binds)


base = run({})
print("base:", {p: hashlib.sha256(base[b]).hexdigest()[:8]
                for b, p in zip(OUT_BANKS, OUT_PORTS)}, flush=True)
probes = [("t0@4", "add4", {4: perturb(base_datas[4], "add4")}),
          ("t2@5", "add4", {5: perturb(base_datas[5], "add4")}),
          ("t7@6", "add4", {6: perturb(base_datas[6], "add4")}),
          ("dup15=t7", "add4", {15: perturb(base_datas[6], "add4")}),
          ("state@7", "add4", {7: perturb(base_datas[7][:36864], "add4") + b"\xff" * (393216 - 36864)}),
          ("state@7", "zero", {7: perturb(base_datas[7][:36864], "zero") + b"\xff" * (393216 - 36864)}),
          ("t0@4+15", "add4", {4: perturb(base_datas[4], "add4"),
                               15: perturb(base_datas[4], "add4")}),
          ("t2@5+15", "add4", {5: perturb(base_datas[5], "add4"),
                               15: perturb(base_datas[5], "add4")})]
for name, mode, extra in probes:
    outs = run(extra)
    diffs = {}
    for bank, port in zip(OUT_BANKS, OUT_PORTS):
        ref = REFS[port].reshape(-1)
        x = np.frombuffer(outs[bank], dtype=np.float16)
        if port in ("t41", "t50"):
            got = x[:16 * 32].reshape(16, 32)[:, 0]
        elif port == "t53":
            a = x[:6144 * 32].reshape(6144, 32)
            got = a[:, :3].reshape(-1)
        else:
            got = x[:ref.size]
        b0 = np.frombuffer(base[bank], dtype=np.float16)
        if port in ("t41", "t50"):
            b0g = b0[:16 * 32].reshape(16, 32)[:, 0]
        elif port == "t53":
            a0 = b0[:6144 * 32].reshape(6144, 32)
            b0g = a0[:, :3].reshape(-1)
        else:
            b0g = b0[:ref.size]
        nd = int(np.count_nonzero(got.view(np.uint16) != b0g.view(np.uint16)))
        m = int(np.count_nonzero(got.view(np.uint16) == ref.view(np.uint16)))
        diffs[port] = f"diff_vs_base={nd} match_ref={m}/{ref.size}"
    print(f"probe {name}({mode}): " + " ".join(f"{k}:{v}" for k, v in diffs.items()), flush=True)
