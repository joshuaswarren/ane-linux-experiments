#!/usr/bin/env python3
"""Persistent-buffer descriptor GEMM: same verified 512x256 tile descriptor
as ane-network.py run_gemm, but buffers are allocated once and the kernel
blob is rewritten in place per call.

Modes:
  --verify   identity passthrough + random tile vs numpy (exit 0 on pass)
  --bench    per-call floor over N calls (default 200)
"""
import os
import struct
import sys
import time

import numpy as np

import runpy

os.environ.setdefault("ANE_DESCRIPTOR_ONLY", "1")
_here = os.path.dirname(os.path.abspath(__file__))
NET = runpy.run_path(os.path.join(_here, "ane-network.py"), run_name="gemm_fast_harvest")

C_GEMM = NET["C_GEMM"]
K_GEMM = NET["K_GEMM"]
N_WEIGHTS = NET["N_WEIGHTS"]
STRIDE = NET["STRIDE"]

_rng = np.random.default_rng(7)


def to_blob(W):
    """(<=512, <=256) fp16 -> 512 KB weight blob, zero-padded."""
    blob = np.zeros(N_WEIGHTS, dtype=np.float16)
    padded = np.zeros((C_GEMM, K_GEMM), dtype=np.float16)
    padded[:W.shape[0], :W.shape[1]] = W
    for t in range(16):
        base = t * 16384 + 6
        blob[base:base + K_GEMM * 32] = padded[32 * t:32 * t + 32].T.reshape(-1)
    return blob


class FastGemm:

    def __init__(self):
        btsp = NET["gemm_btsp"]()
        cmd = bytearray(0x274 + NET["WEIGHT_BLOB"])
        cmd[:len(btsp)] = btsp
        self.alloc_len = len(cmd)
        self.cmd_h, self.cmd_m = NET["allocate_buffer"](self.alloc_len)
        self.out_h, self.out_m = NET["allocate_buffer"](0x8000)
        self.src_h, self.src_m = NET["allocate_buffer"](0x4000)
        self.btsp_h, self.btsp_m = NET["allocate_buffer"](0x4000)
        self.cmd = np.frombuffer(bytes(cmd), dtype=np.uint8).copy()
        self.btsp_m.write(bytes(btsp))
        self.handles = [self.cmd_h, 0, 0, 0, self.out_h, self.src_h, 0] + [0] * 25

    def run(self, blob, x):
        """blob: N_WEIGHTS fp16 array. x: K_GEMM fp16 vector. Returns C_GEMM fp32."""
        self.cmd[0x274:0x274 + NET["WEIGHT_BLOB"]] = blob.view(np.uint8)
        self.cmd_m.seek(0)
        self.cmd_m.write(self.cmd)  # full rewrite; mmap write is ~512 KB
        src = np.zeros(0x4000 // 2, dtype=np.float16)
        src[:K_GEMM * STRIDE:STRIDE] = x
        self.src_m.seek(0)
        self.src_m.write(src.tobytes())
        NET["submit_task"](0x274, 1, 0x274, self.handles, self.btsp_h)
        out = np.frombuffer(self.out_m, dtype=np.float16,
                            count=C_GEMM * STRIDE).reshape(C_GEMM, STRIDE)[:, 0].copy()
        return out.astype(np.float32)

    def close(self):
        for m in (self.cmd_m, self.out_m, self.src_m, self.btsp_m):
            m.close()



# ------------------------------------------------------------------ chaining
# Geometry mirrored from the retained 2-TD concat.ane (verified running):
# TDs live inside the cmd BO at content 0x28 + k*0x300, tsk_size spans them,
# and the kernel bar (bar[KRN] = cmd iova + round_up(tsk_size, 16)) addresses
# weight blobs placed at round_up(tsk_size, 16) + k*0x80000. The TD's kernel
# DMA address field is bank-relative: 0x81000000 == bar[KRN] + 0.

TD_STRIDE = 0x300
TD_SIZE = 0x274
KERNEL_FIELD_BASE = 0x81000000
CONTENT_HEADER = bytes.fromhex(
    "0000000000009c000004000000000000680000000000000000980030000300002640820500000000"
)


def to_blob_aligned(W):
    """(<=512, <=256) fp16 -> 512 KB blob for a bar-relative kernel base."""
    blob = np.zeros(N_WEIGHTS, dtype=np.float16)
    padded = np.zeros((C_GEMM, K_GEMM), dtype=np.float16)
    padded[:W.shape[0], :W.shape[1]] = W
    for t in range(16):
        base = t * 16384
        blob[base:base + K_GEMM * 32] = padded[32 * t:32 * t + 32].T.reshape(-1)
    return blob


def patch_td(td, k, n):
    """Patch TD copy k: kernel table, source base, destination base."""
    buf = bytearray(td)
    be = NET["_be32"]
    for i in range(16):
        addr = KERNEL_FIELD_BASE + k * 0x80000 + i * 0x8000
        struct.pack_into(">I", buf, 0x2C + 8 + 4 * i, be(addr))
    struct.pack_into("<I", buf, 0x174, k * 0x4000)          # SrcBaseAddr
    struct.pack_into("<I", buf, 0x25C, k * 0x8000)          # DstBaseAddr
    return bytes(buf)


def chain_bench(n=8, calls=20):
    """N GEMM tiles in one submit: distinct weights per tile, one exec.

    TD placement covers both plausible fetch rules: the task manager reads
    td_count consecutive TDs of td_size either from the BTSP buffer at
    offset 0 or from the cmd BO task region; both carry the same patched
    TDs. Kernel blobs sit at bar[KRN] + k*0x80000 with bar[KRN] =
    cmd iova + round_up(tsk_size, 16), matching the retained concat graph.
    """
    td = bytes(NET["gemm_btsp"]())[:TD_SIZE]
    tsk = (n - 1) * TD_STRIDE + TD_SIZE
    krn_start = (tsk + 15) & ~15
    cmd_len = krn_start + n * 0x80000
    cmd = bytearray(cmd_len)
    for k in range(n):
        cmd[k * TD_STRIDE:k * TD_STRIDE + TD_SIZE] = patch_td(td, k, n)

    btsp = bytearray(0x4000)
    for k in range(n):
        btsp[k * TD_STRIDE:k * TD_STRIDE + TD_SIZE] = patch_td(td, k, n)
        off28 = 0x28 + k * TD_STRIDE
        if off28 + TD_SIZE <= 0x4000:
            btsp[off28:off28 + TD_SIZE] = patch_td(td, k, n)

    cmd_h, cmd_m = NET["allocate_buffer"](cmd_len)
    out_h, out_m = NET["allocate_buffer"](n * 0x8000)
    src_h, src_m = NET["allocate_buffer"](n * 0x4000)
    btsp_h, btsp_m = NET["allocate_buffer"](0x4000)
    handles = [cmd_h, 0, 0, 0, out_h, src_h, 0] + [0] * 25

    mats = [(_rng.standard_normal((C_GEMM, K_GEMM)) * 0.05).astype(np.float16)
            for _ in range(n)]
    blobs = [to_blob_aligned(W) for W in mats]
    xs = [(_rng.standard_normal(K_GEMM) * 0.3).astype(np.float16) for _ in range(n)]

    def program():
        for k in range(n):
            off = krn_start + k * 0x80000
            cmd[off:off + 0x80000] = blobs[k].tobytes()
        cmd_m.seek(0)
        cmd_m.write(cmd)

    def run_once():
        src = np.zeros(n * 0x4000 // 2, dtype=np.float16)
        for k in range(n):
            base = k * 0x2000
            src[base:base + K_GEMM * STRIDE:STRIDE] = xs[k]
        src_m.seek(0)
        src_m.write(src.tobytes())
        btsp_m.seek(0)
        btsp_m.write(bytes(btsp))
        NET["submit_task"](tsk, n, TD_SIZE, handles, btsp_h)
        out = np.frombuffer(out_m, dtype=np.float16, count=n * 0x8000 // 2)
        return [out[k * 0x4000:k * 0x4000 + C_GEMM * STRIDE].reshape(C_GEMM, STRIDE)[:, 0].copy().astype(np.float32)
                for k in range(n)]

    program()
    got = run_once()
    ok = True
    for k in range(n):
        ref = mats[k].astype(np.float32) @ xs[k].astype(np.float32)
        err = float(np.abs(got[k] - ref).max())
        am = int(got[k].argmax()) == int(ref.argmax())
        print(f"tile {k}: max_err={err:.4f} argmax={'ok' if am else 'FLIP'}")
        ok = ok and err < 0.01 and am
    t0 = time.perf_counter()
    for _ in range(calls):
        run_once()
    wall = time.perf_counter() - t0
    print(f"chain n={n}: {wall / calls * 1e3:.3f} ms/submit, {wall / calls / n * 1e3:.3f} ms/tile over {calls} submits")
    for m in (cmd_m, out_m, src_m, btsp_m):
        m.close()
    return 0 if ok else 1



def verify():
    gemm = FastGemm()
    x = (_rng.standard_normal(K_GEMM) * 0.3).astype(np.float16)

    ident = to_blob(np.eye(C_GEMM, K_GEMM, dtype=np.float16))
    got = gemm.run(ident, x)
    passthrough = np.allclose(got[:K_GEMM], x.astype(np.float32), atol=1e-2)
    print(f"identity passthrough: {'ok' if passthrough else 'FAIL'}")

    W = (_rng.standard_normal((C_GEMM, K_GEMM)) * 0.05).astype(np.float16)
    got = gemm.run(to_blob(W), x)
    ref = W.astype(np.float32) @ x.astype(np.float32)
    err = float(np.abs(got - ref).max())
    argmax = int(got.argmax()) == int(ref.argmax())
    print(f"random 512x256: max_err={err:.4f} argmax={'ok' if argmax else 'FLIP'}")
    gemm.close()
    if passthrough and err < 0.01 and argmax:
        print("PERSISTENT_GEMM_VERIFY_OK")
        return 0
    return 1


def bench(calls=200):
    gemm = FastGemm()
    blob = to_blob((_rng.standard_normal((C_GEMM, K_GEMM)) * 0.05).astype(np.float16))
    x = (_rng.standard_normal(K_GEMM) * 0.3).astype(np.float16)
    gemm.run(blob, x)  # warm
    t0 = time.perf_counter()
    for _ in range(calls):
        gemm.run(blob, x)
    wall = time.perf_counter() - t0
    print(f"persistent tile floor: {wall / calls * 1e3:.3f} ms/call over {calls} calls")
    gemm.close()
    return wall / calls


def floor_bench(calls=300):
    """Submit-only floor: program once, then rewrite only the src vector."""
    gemm = FastGemm()
    blob = to_blob((_rng.standard_normal((C_GEMM, K_GEMM)) * 0.05).astype(np.float16))
    x = (_rng.standard_normal(K_GEMM) * 0.3).astype(np.float16)
    gemm.run(blob, x)
    t0 = time.perf_counter()
    for _ in range(calls):
        src = np.zeros(0x4000 // 2, dtype=np.float16)
        src[:K_GEMM * STRIDE:STRIDE] = x
        gemm.src_m.seek(0)
        gemm.src_m.write(src.tobytes())
        NET["submit_task"](0x274, 1, 0x274, gemm.handles, gemm.btsp_h)
        out = np.frombuffer(gemm.out_m, dtype=np.float16,
                            count=C_GEMM * STRIDE).reshape(C_GEMM, STRIDE)[:, 0].copy()
    wall = time.perf_counter() - t0
    print(f"submit-only floor: {wall / calls * 1e3:.3f} ms/call over {calls} calls")
    gemm.close()
    return wall / calls


if __name__ == "__main__":
    if "--verify" in sys.argv:
        raise SystemExit(verify())
    if "--floor" in sys.argv:
        n = 300
        if "--calls" in sys.argv:
            n = int(sys.argv[sys.argv.index("--calls") + 1])
        floor_bench(n)
        raise SystemExit(0)
    if "--chain" in sys.argv:
        n = 8
        if "--n" in sys.argv:
            n = int(sys.argv[sys.argv.index("--n") + 1])
        raise SystemExit(chain_bench(n))
    if "--bench" in sys.argv:
        n = 200
        if "--calls" in sys.argv:
            n = int(sys.argv[sys.argv.index("--calls") + 1])
        floor = bench(n)
        raise SystemExit(0 if floor < 0.0010 else 2)
    print(__doc__)
