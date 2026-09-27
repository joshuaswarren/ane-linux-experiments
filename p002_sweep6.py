#!/usr/bin/env python3
"""prog_002 layout-corrected sweep: state padded [6144,32] (embed-style),
h-pair in tile-column 64-B-row layout ([16,4,32] -> 64 rows), 12 combos."""
import itertools
import mmap
import struct
from contextlib import ExitStack
from pathlib import Path

import fcntl
import numpy as np

src = open("/var/tmp/jw16-first-submit/prog002_verify.py").read().split("def main()")[0]
exec(src)

# embed-style padded state (verified working for prog_032's t5-in)
state_win = np.zeros((6144, 32), dtype=np.float16)
state_win[:, :3] = t20
state_win = state_win.tobytes()  # 393216 B exactly


def pack_tilecol(t):
    """[16,128] -> [16,4,32] -> 64 rows x 64 B (row = head*4+tile, 32 fp16)."""
    a = t.reshape(16, 4, 32).astype(np.float16)
    return a.reshape(64, 32).tobytes()


def pack_dense(t):
    return t.reshape(-1).astype(np.float16).tobytes()


def pack_T(t):
    """column-major: [16,128].T.tobytes() = 4096 B (d-major order)."""
    return t.reshape(16, 128).T.astype(np.float16).tobytes()


H_PACKS = {"tilecol": pack_tilecol, "dense": pack_dense, "T": pack_T}


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
for hpack in ("tilecol", "dense", "T"):
    for perm in itertools.permutations((4, 6, 15)):
        namebank = dict(zip(("t0", "t7", "t2"), perm))
        binds = {7: state_win, 15: t2.reshape(16, 128).tobytes()}  # t2 also at 15 (4th read)
        binds[namebank["t0"]] = H_PACKS[hpack](t0)
        binds[namebank["t7"]] = t7.reshape(-1).astype(np.float16).tobytes()
        binds[namebank["t2"]] = H_PACKS[hpack](t2)
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
        tag = f"[{hpack}] " + " ".join(f"{nm}@{bk}" for bk, nm in namebank.items())
        oh = hashlib.sha256(b"".join(outs[b] for b in OUT_BANKS)).hexdigest()[:12]
        print(("WIN " if allok else "no  ") + tag + f" outsha={oh}" + " | " + " ".join(results), flush=True)
print("combos:", count, flush=True)
