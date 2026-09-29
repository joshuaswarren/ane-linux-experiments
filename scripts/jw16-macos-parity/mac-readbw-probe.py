#!/usr/bin/env python3
"""macOS DRAM streaming-read ceiling probe (Jw16MacParity window supplement).

Runs with the macOS venv: ~/jw16-macos-window/venv-gpu python, mlx 0.32.2.
Why: the T6001 whole-encoder ANE gap (441 ms Linux vs 138 ms macOS) is either
the ANE clock (firmware perf mode) or the memory side (fabric/DCS stuck low
under Linux where the PMP never runs). GPU decode GB/s + prefill TFLOP/s are
already planned for this window; this adds the raw streaming-read ceiling at
multi-GB sizes (the ANE streams 458 MB/submit, so small-buffer numbers that
fit in SLC are not the comparable quantity). One GB/s-per-size figure out.

Success: prints READ_GBs lines; larger is closer to the hardware ceiling.
"""
import time
import mlx.core as mx


def bench_read(n_elem, reps):
    a = mx.ones([n_elem], dtype=mx.float32)
    mx.eval(a)
    mx.synchronize()
    t0 = time.perf_counter()
    for _ in range(reps):
        s = mx.sum(a)
        mx.eval(s)
    mx.synchronize()
    dt = time.perf_counter() - t0
    return n_elem * 4 * reps / dt / 1e9


def bench_copy(n_elem, reps):
    a = mx.ones([n_elem], dtype=mx.float32)
    mx.eval(a)
    mx.synchronize()
    t0 = time.perf_counter()
    for _ in range(reps):
        b = a + 1.0
        mx.eval(b)
    mx.synchronize()
    dt = time.perf_counter() - t0
    return n_elem * 4 * 2 * reps / dt / 1e9  # read + write


if __name__ == "__main__":
    print("mlx=%s device=%s" % (mx.__version__ if hasattr(mx, "__version__") else "?",
                                mx.default_device()))
    for mb, reps in [(256, 20), (1024, 8), (2048, 4)]:
        n = mb * 1024 * 1024 // 4
        print("READ_GBs size_mb=%d reps=%d gbs=%.1f" % (mb, reps, bench_read(n, reps)))
    for mb, reps in [(256, 20), (1024, 8)]:
        n = mb * 1024 * 1024 // 4
        print("COPY_GBs size_mb=%d reps=%d gbs=%.1f" % (mb, reps, bench_copy(n, reps)))
