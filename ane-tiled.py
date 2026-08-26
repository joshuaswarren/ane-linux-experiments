#!/usr/bin/env python3
"""Arbitrary-size matmul on the Apple Neural Engine by tiling the fixed gemm.

The engine's gemm is one shape: 512 output channels by 256 live input channels,
weights read from a 512 KB DMA blob. Every earlier result fit that single
shape, which is why the honest limit in docs/jw-m1.md read "weight tiling does
not scale past one 512x256 gemm per call".

This lifts it. For W of shape (M, K) and activation x of length K:

    row blocks   = ceil(M / 512)
    col blocks   = ceil(K / 256)
    out[r-block] = sum over c-blocks of gemm(W[r-block, c-block], x[c-block])

Two honest notes on what runs where:

1. The multiply-accumulate is entirely on the engine. Every partial product
   comes from a real gemm.
2. Summing partials across column blocks is a length-M reduction per block,
   against M*K multiply-accumulates inside the blocks. With --accum ane that
   reduction runs on the engine too, through elementwise add 64 channels at a
   time. With --accum cpu it is a numpy add. Default is cpu: the engine path
   costs ceil(512/64)=8 extra ioctls per accumulation and buys nothing
   numerically. --accum ane exists to prove it can be done; both are verified.

  usage: ane-tiled.py                 # correctness at several shapes
         ane-tiled.py --bench         # per-call cost + model projection
         ane-tiled.py --accum ane     # accumulate on the engine too
"""
import os
import runpy
import sys
import time

import numpy as np

_bench = "--bench" in sys.argv
_accum = "cpu"
if "--accum" in sys.argv:
    _accum = sys.argv[sys.argv.index("--accum") + 1]
_saved_argv, sys.argv = sys.argv, [sys.argv[0]]

_here = os.path.dirname(os.path.abspath(__file__))


def _find(name):
    for cand in (os.path.join(_here, name),
                 os.path.expanduser(f"~/ane-boot/{name}"),
                 os.path.expanduser(f"~/src/ane-linux-experiments/{name}")):
        if os.path.exists(cand):
            return cand
    sys.exit(f"{name} not found")


NET = runpy.run_path(_find("ane-network.py"), run_name="net_harvest")
SM = runpy.run_path(_find("ane-softmax.py"), run_name="sm_harvest")
sys.argv = _saved_argv

run_gemm = NET["run_gemm"]
C_GEMM = NET["C_GEMM"]          # 512 output channels per call
K_GEMM = NET["K_GEMM"]          # 256 live input channels per call
N_WEIGHTS = NET["N_WEIGHTS"]

run_ew = SM["run_ew"]
C_EW = SM["C_EW"]               # 64 channels per elementwise call


def to_blob(W):
    """(<=512, <=256) fp16 -> 512 KB weight blob, zero-padded."""
    blob = np.zeros(N_WEIGHTS, dtype=np.float16)
    padded = np.zeros((C_GEMM, K_GEMM), dtype=np.float16)
    padded[:W.shape[0], :W.shape[1]] = W
    for t in range(16):
        base = t * 16384 + 6
        blob[base:base + K_GEMM * 32] = padded[32 * t:32 * t + 32].T.reshape(-1)
    return blob


def add_ane(a, b):
    """Elementwise add of two length-512 vectors, on the engine.

    run_ew is 64 channels wide, so a 512-wide add is 8 calls. Shows the
    reduction need not leave the engine; not the fast path."""
    out = np.empty_like(a)
    for i in range(0, len(a), C_EW):
        ca = a[i:i + C_EW].astype(np.float16)
        cb = b[i:i + C_EW].astype(np.float16)
        out[i:i + C_EW] = run_ew("add", ca, cb)[:len(ca)]
    return out


def matmul_ane(W, x, accum="cpu", stats=None):
    """out = W @ x for W of any (M, K), on the engine in 512x256 tiles."""
    M, K = W.shape
    assert x.shape[0] == K, f"shape mismatch {W.shape} @ {x.shape}"
    out = np.zeros(M, dtype=np.float32)

    for r0 in range(0, M, C_GEMM):
        r1 = min(r0 + C_GEMM, M)
        acc = None
        for c0 in range(0, K, K_GEMM):
            c1 = min(c0 + K_GEMM, K)

            t0 = time.perf_counter()
            blob = to_blob(W[r0:r1, c0:c1])
            t1 = time.perf_counter()

            xv = np.zeros(K_GEMM, dtype=np.float16)
            xv[:c1 - c0] = x[c0:c1]
            part = run_gemm(blob, xv).astype(np.float32)
            t2 = time.perf_counter()

            if stats is not None:
                stats["blob_s"] += t1 - t0
                stats["gemm_s"] += t2 - t1
                stats["calls"] += 1

            if acc is None:
                acc = part
            else:
                t3 = time.perf_counter()
                acc = add_ane(acc, part) if accum == "ane" else acc + part
                if stats is not None:
                    stats["accum_s"] += time.perf_counter() - t3
                    if accum == "ane":
                        stats["ew_calls"] += C_GEMM // C_EW

        out[r0:r1] = acc[:r1 - r0]
    return out


def check(M, K, accum, rng):
    W = (rng.standard_normal((M, K)) * 0.05).astype(np.float16)
    x = (rng.standard_normal(K) * 0.3).astype(np.float16)

    stats = {"blob_s": 0.0, "gemm_s": 0.0, "accum_s": 0.0, "calls": 0, "ew_calls": 0}
    t0 = time.perf_counter()
    got = matmul_ane(W, x, accum=accum, stats=stats)
    wall = time.perf_counter() - t0

    ref = W.astype(np.float32) @ x.astype(np.float32)
    err = np.abs(got - ref)
    denom = max(1e-9, float(np.abs(ref).max()))
    tiles = ((M + C_GEMM - 1) // C_GEMM) * ((K + K_GEMM - 1) // K_GEMM)

    print(f"({M:>5},{K:>5}) tiles={tiles:>3} accum={accum:<3} "
          f"max_err={err.max():.4f} rel={err.max() / denom:.5f} "
          f"argmax={'ok' if got.argmax() == ref.argmax() else 'FLIP'} "
          f"wall={wall:.2f}s gemm={stats['gemm_s']:.2f}s "
          f"blob={stats['blob_s']:.2f}s accum={stats['accum_s']:.2f}s")
    return stats, wall


def main():
    rng = np.random.default_rng(11)

    print("=== correctness: tiled vs numpy ===")
    for M, K in [(512, 256), (512, 512), (1024, 256), (1024, 512),
                 (1536, 768), (2048, 1024)]:
        check(M, K, _accum, rng)

    if _accum == "cpu":
        print()
        print("=== same shape, reduction on the engine instead of the CPU ===")
        check(1024, 512, "ane", rng)

    if not _bench:
        return

    print()
    print("=== per-call cost ===")
    stats, _ = check(2048, 1024, "cpu", rng)
    per_gemm = stats["gemm_s"] / max(1, stats["calls"])
    per_blob = stats["blob_s"] / max(1, stats["calls"])
    print(f"calls={stats['calls']} "
          f"per_gemm={per_gemm * 1e3:.2f}ms per_blob={per_blob * 1e3:.2f}ms "
          f"per_tile_total={(per_gemm + per_blob) * 1e3:.2f}ms")

    # Llama-3.2-3B: hidden 3072, 28 layers, GQA (8 kv heads -> 1024-wide k/v).
    per_layer = (3072 * 3072 * 2) + (1024 * 3072 * 2) + (8192 * 3072 * 3)
    params = per_layer * 28
    tiles = params / (C_GEMM * K_GEMM)
    secs = tiles * (per_gemm + per_blob)
    print()
    print("=== projection, Llama-3.2-3B forward pass ===")
    print(f"weights in matmuls    {params / 1e9:.2f} B")
    print(f"512x256 tiles/token   {tiles:,.0f}")
    print(f"seconds/token         {secs:,.1f}")
    print(f"tokens/second         {1 / secs:.5f}")
    print("GPU measured          17.96 tok/s (llama.cpp Vulkan)")
    print(f"engine slower by      {17.96 * secs:,.0f}x at this call granularity")


if __name__ == "__main__":
    main()
