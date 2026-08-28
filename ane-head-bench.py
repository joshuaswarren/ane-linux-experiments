#!/usr/bin/env python3
"""Full tied-head benchmark: 248320x2048 fp16 GEMM via pre-programmed
persistent descriptor tiles on the Apple Neural Engine (Linux).

Every 512x256 tile is a persistent buffer pair (cmd BO with its weight blob
written once, src BO, out BO). Per token only the 512-byte source window is
rewritten per tile and one submit is issued per tile; partials over the 8
column chunks are summed on the CPU (fp32), exactly like the verified
ane-tiled path.

  python3 ane-head-bench.py [--rows 248320] [--cols 2048]

Prints setup time, per-token ANE wall, CPU numpy reference wall, and quality
(max_err, argmax match, top-10 overlap). Exit 0 when the ANE token is faster
than the CPU reference AND max_err <= 0.05 AND argmax matches.
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runpy

os.environ.setdefault("ANE_DESCRIPTOR_ONLY", "1")
_here = os.path.dirname(os.path.abspath(__file__))
NET = runpy.run_path(os.path.join(_here, "ane-network.py"), run_name="head_bench_harvest")

C_GEMM = NET["C_GEMM"]
K_GEMM = NET["K_GEMM"]
N_WEIGHTS = NET["N_WEIGHTS"]
STRIDE = NET["STRIDE"]
_rng = np.random.default_rng(31337)


def to_blob(W):
    blob = np.zeros(N_WEIGHTS, dtype=np.float16)
    padded = np.zeros((C_GEMM, K_GEMM), dtype=np.float16)
    padded[:W.shape[0], :W.shape[1]] = W
    for t in range(16):
        base = t * 16384 + 6
        blob[base:base + K_GEMM * 32] = padded[32 * t:32 * t + 32].T.reshape(-1)
    return blob


class Tile:
    """One persistent 512x256 tile: weights written once at setup."""

    def __init__(self, W):
        btsp = NET["gemm_btsp"]()
        cmd = bytearray(0x274 + NET["WEIGHT_BLOB"])
        cmd[:len(btsp)] = btsp
        blob = to_blob(W)
        cmd[0x274:] = blob.tobytes()
        self.cmd_h, self.cmd_m = NET["allocate_buffer"](len(cmd))
        self.out_h, self.out_m = NET["allocate_buffer"](0x8000)
        self.src_h, self.src_m = NET["allocate_buffer"](0x4000)
        self.btsp_h, self.btsp_m = NET["allocate_buffer"](0x4000)
        self.cmd_m.write(bytes(cmd))
        self.btsp_m.write(bytes(btsp))
        self.handles = [self.cmd_h, 0, 0, 0, self.out_h, self.src_h, 0] + [0] * 25
        self.out_view = np.frombuffer(self.out_m, dtype=np.float16,
                                      count=C_GEMM * STRIDE).reshape(C_GEMM, STRIDE)[:, 0]

    def run(self, x):
        src = np.zeros(0x4000 // 2, dtype=np.float16)
        src[:K_GEMM * STRIDE:STRIDE] = x
        self.src_m.seek(0)
        self.src_m.write(src.tobytes())
        NET["submit_task"](0x274, 1, 0x274, self.handles, self.btsp_h)
        return self.out_view.astype(np.float32)

    def close(self):
        self.out_view = None
        for m in (self.cmd_m, self.out_m, self.src_m, self.btsp_m):
            m.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=485 * C_GEMM)
    ap.add_argument("--cols", type=int, default=8 * K_GEMM)
    args = ap.parse_args()
    M, K = args.rows, args.cols

    print(f"generating weights {M}x{K} fp16 ({M * K * 2 / 2**30:.2f} GiB)")
    W = (_rng.standard_normal((M, K)) * 0.02).astype(np.float16)
    x = (_rng.standard_normal(K) * 0.3).astype(np.float16)

    row_tiles = M // C_GEMM
    col_tiles = K // K_GEMM
    total = row_tiles * col_tiles
    print(f"programming {row_tiles}x{col_tiles} = {total} persistent tiles")
    t0 = time.perf_counter()
    tiles = []
    for r in range(row_tiles):
        for c in range(col_tiles):
            tiles.append(Tile(W[r * C_GEMM:(r + 1) * C_GEMM,
                                c * K_GEMM:(c + 1) * K_GEMM]))
    setup_s = time.perf_counter() - t0
    print(f"setup: {setup_s:.1f} s ({setup_s / total * 1e3:.2f} ms/tile, one-time)")

    def ane_token():
        out = np.empty(M, dtype=np.float32)
        i = 0
        for r in range(row_tiles):
            acc = None
            for c in range(col_tiles):
                part = tiles[i].run(x[c * K_GEMM:(c + 1) * K_GEMM])
                acc = part if acc is None else acc + part
                i += 1
            out[r * C_GEMM:(r + 1) * C_GEMM] = acc
        return out

    ane_token()
    calls = 3
    t0 = time.perf_counter()
    for _ in range(calls):
        got = ane_token()
    ane_s = (time.perf_counter() - t0) / calls

    t0 = time.perf_counter()
    ref = W.astype(np.float32) @ x.astype(np.float32)
    cpu_s = time.perf_counter() - t0

    err = np.abs(got - ref)
    am = int(got.argmax()) == int(ref.argmax())
    top_ane = set(np.argsort(got)[-10:].tolist())
    top_ref = set(np.argsort(ref)[-10:].tolist())
    overlap = len(top_ane & top_ref)
    speedup = cpu_s / ane_s
    print(f"ANE head token: {ane_s * 1e3:.0f} ms ({total} submits)")
    print(f"CPU numpy head: {cpu_s * 1e3:.0f} ms")
    print(f"speedup: {speedup:.2f}x")
    print(f"max_err={err.max():.4f} argmax={'ok' if am else 'FLIP'} "
          f"top10={overlap}/10")
    for t in tiles:
        t.close()
    quality = err.max() <= 0.05 and am and overlap >= 9
    if speedup > 1.0 and quality:
        print("HEAD_CROSSOVER_OK")
        return 0
    print("HEAD_CROSSOVER_NOT_MET")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
