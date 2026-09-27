#!/usr/bin/env python3
"""prog_002 sweep v3: P(4,3) input combos; 8x8 bank-vs-ref match matrix."""
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


def match_counts(raw, port):
    ref = REFS[port].reshape(-1)
    x = np.frombuffer(raw, dtype=np.float16)
    need = {"t53": 6144 * 32, "t41": 16 * 32, "t50": 16 * 32}.get(port, ref.size)
    if x.size < need:
        return 0, ref.size
    if port in ("t41", "t50"):
        got = x[:16 * 32].reshape(16, 32)[:, 0]
        return int(np.count_nonzero(got.view(np.uint16) == ref.view(np.uint16))), ref.size
    if port == "t53":
        a = x[:6144 * 32].reshape(6144, 32)
        best = 0
        for perm in itertools.permutations((0, 1, 2)):
            got = a[:, list(perm)].reshape(-1)
            best = max(best, int(np.count_nonzero(got.view(np.uint16) == ref.view(np.uint16))))
        return best, ref.size
    got = x[:ref.size]
    return int(np.count_nonzero(got.view(np.uint16) == ref.view(np.uint16))), ref.size


datas = {"t7": t7.reshape(-1).tobytes(), "t2": t2.reshape(-1).tobytes(),
         "t0": t0.reshape(-1).tobytes(), "t20": pack_state(t20)}
names = ("t0", "t2", "t7")
count = 0
for combo in itertools.permutations((4, 5, 6, 15), 3):
    assign = dict(zip(names, combo))
    assign["t20"] = 7
    binds = {b: pb for b, pb in OUT_PREFILL.items()}
    for name, bank in assign.items():
        binds[bank] = datas[name]
    count += 1
    outs = submit_bind(binds)
    M = np.zeros((8, 8), dtype=int)
    for i, bank in enumerate(OUT_BANKS):
        for j, port in enumerate(OUT_PORTS):
            try:
                M[i, j], _ = match_counts(outs[bank], port)
            except ValueError:
                print(f"CRASH i={i} bank={bank} port={port} bytes={len(outs[bank])}")
                raise
    best_assign = 0
    best_perm = None
    for perm in itertools.permutations(range(8)):
        s = sum(M[i, perm[i]] for i in range(8))
        if s > best_assign:
            best_assign = s
            best_perm = perm
    ports_hit = [OUT_PORTS[j] for j in best_perm]
    full = best_assign == sum(REFS[p].size for p in OUT_PORTS)
    tag = " ".join(f"{k}@{v}" for k, v in sorted(assign.items(), key=lambda kv: kv[1]))
    print(f"{tag}: best={best_assign}/266280 via {ports_hit} banks {list(OUT_BANKS)}",
          flush=True)
    if full:
        print("FULL BITWISE ASSIGNMENT FOUND", flush=True)
        for i, bank in enumerate(OUT_BANKS):
            (OUT / f"prog002-b{bank}-{ports_hit[i]}.bin").write_bytes(outs[bank])
        break
print(f"combos: {count}", flush=True)
