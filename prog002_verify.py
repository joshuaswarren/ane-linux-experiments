#!/usr/bin/env python3
"""prog_002 (token-2+ embed variant) binding verification on jw16.

Reference: macstudio capture_all sig0002 (first execute of the prog_002
class: in [t7 x-tokens, t2 h, t0 h', t20 state], out 8 ports), pre-execute
input snapshots, mutated={}.

TD-decoded channels (grammar: shift0=src, shift12=dst; counts at
0x13810/14, 0x1780C/10):
  reads  ch6 0x1000, ch4 0x1000, ch15 0x1000, ch5 0x1000 (three 4096-B
         inputs + one extra read), ch1 0x100 (kernel microcode header —
         bank 1 is the KMD-computed kernel buffer), ch7 0x60000 (state),
         ch3 0x20000 (ws staging)
  writes ch3 (ws), ch5/8/9/10/13 0x1000, ch11/12 0x400, ch14 0x60000
Output channel<->tensor map by size + Apple port-name order:
  5=t15[1,2048] 8=t31[16,128] 9=t35[16,128] 10=t37[16,128] 11=t41[16,1,1]
  12=t50[16,1,1] 13=t52[16,128] 14=t53[6144,3]
Sweep: assign {t0,t2,t7} to three of {4,5,6,15} (24 combos), state t20@7.
"""
import fcntl
import hashlib
import itertools
import mmap
import struct
import sys
from contextlib import ExitStack
from pathlib import Path

import importlib.util
import numpy as np

ROOT = Path("/var/tmp/m1max-embed-recovery")
REF = Path("/var/tmp/jw16-first-submit/ref4")
ANEC = Path("/var/tmp/jw16-first-submit/prog002.anec")

runtime = importlib.util.module_from_spec(importlib.util.spec_from_file_location(
    "ane_runtime", str(ROOT / "tools/ane-runtime.py")))
importlib.util.module_from_spec  # noqa
spec = importlib.util.spec_from_file_location("ane_runtime", str(ROOT / "tools/ane-runtime.py"))
runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
spec2 = importlib.util.spec_from_file_location("probe", str(ROOT / "tools/production-anec-probe.py"))
probe = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(probe)

stage = probe.stage_geometry(probe.load_anec_header(ANEC))
z = np.load(str(REF / "sig0002.npz"))
t7, t2, t0, t20 = z["in__t7"], z["in__t2"], z["in__t0"], z["in__t20"]
OUT_PORTS = ("t15", "t31", "t35", "t37", "t41", "t50", "t52", "t53")
OUT_BANKS = (5, 8, 9, 10, 11, 12, 13, 14)

OUT_PREFILL = {
    5: np.full(2048, np.inf, dtype=np.float16).tobytes(),
    8: np.full(2048, np.inf, dtype=np.float16).tobytes(),
    9: np.full(2048, np.inf, dtype=np.float16).tobytes(),
    10: np.full(2048, np.inf, dtype=np.float16).tobytes(),
    11: np.full(16, np.inf, dtype=np.float16).tobytes(),
    12: np.full(16, np.inf, dtype=np.float16).tobytes(),
    13: np.full(2048, np.inf, dtype=np.float16).tobytes(),
    14: np.full(196608, np.inf, dtype=np.float16).tobytes(),
}

REFS = {p: z[f"out__{p}"] for p in OUT_PORTS}


def tile(n):
    return ((n + 16383) // 16384) * 16384


def pack_state(mat):
    packed = np.zeros((6144, 32), dtype=np.float16)
    packed[:, :3] = mat
    return packed.tobytes()


def run(assign):
    """assign: {input_name: bank}. Returns {bank: bytes}."""
    datas = {"t7": t7.reshape(-1).tobytes(), "t2": t2.reshape(-1).tobytes(),
             "t0": t0.reshape(-1).tobytes(), "t20": pack_state(t20)}
    binds = {}
    for name, bank in assign.items():
        binds[bank] = datas[name]
    for bank, pb in OUT_PREFILL.items():
        binds[bank] = pb
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


def main():
    wins = []
    count = 0
    for combo in itertools.permutations((4, 5, 6, 15), 3):
        assign = dict(zip(("t0", "t2", "t7"), combo))
        assign["t20"] = 7
        count += 1
        outs = run(assign)
        ok_all = True
        for bank, port in zip(OUT_BANKS, OUT_PORTS):
            ref = REFS[port].reshape(-1)
            raw = np.frombuffer(outs[bank], dtype=np.float16)
            if port in ("t41", "t50"):
                got = raw[:16 * 32].reshape(16, 32)[:, 0]
            elif port == "t53":
                a = raw[:6144 * 32].reshape(6144, 32)
                got = a[:, :3].reshape(-1)
            else:
                got = raw[:ref.size]
            m = int(np.count_nonzero(got.view(np.uint16) == ref.view(np.uint16)))
            if m != ref.size:
                ok_all = False
        tag = " ".join(f"{k}@{v}" for k, v in sorted(assign.items()))
        if ok_all:
            wins.append(tag)
            print(f"WIN {tag}", flush=True)
            for bank, port in zip(OUT_BANKS, OUT_PORTS):
                (Path("/var/tmp/jw16-first-submit/out") / f"prog002-{port}.bin").write_bytes(
                    outs[bank])
        else:
            print(f"no {tag}", flush=True)
    print(f"PROG002: {count} combos, WINS: {wins if wins else 'NONE'}", flush=True)


if __name__ == "__main__":
    main()
