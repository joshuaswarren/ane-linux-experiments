#!/usr/bin/env python3
"""Micro-benchmark for ane_resident.submit() request-line allocation.

This is a LOCAL micro-bench that does NOT touch /dev/accel — it only exercises
the bytearray construction that L1 changes. Real m1-test-host runs (with hash gates)
are the actual proof; this bench gives a deterministic per-round floor.

Usage:
  python3 micro_bench.py
"""

from __future__ import annotations

import statistics
import time
from typing import Sequence


def build_request_orig(job: Sequence[str], ordered: Sequence[tuple[str, bytes]]) -> bytes:
    """Original implementation: bytearray + repeated += per input."""
    request = bytearray(" ".join(job).encode() + b"\n")
    for _, payload in ordered:
        request += payload
    return bytes(request)


def build_request_l1(job: Sequence[str], ordered: Sequence[tuple[str, bytes]]) -> bytes:
    """L1: pre-sized bytearray + slice assignment per input."""
    line_bytes = " ".join(job).encode() + b"\n"
    total = len(line_bytes) + sum(len(p) for _, p in ordered)
    request = bytearray(total)
    request[:len(line_bytes)] = line_bytes
    offset = len(line_bytes)
    for _, payload in ordered:
        request[offset:offset + len(payload)] = payload
        offset += len(payload)
    return bytes(request)


# Simulated AC placement encoder pass: 24 A-rounds × 4 inputs + 24 C-rounds × 2 inputs.
# Per-round input sizes (bytes, fp16) match island-attn-a-kt and island-pv.
A_INPUT_SIZES = {
    "q_v": 1 * 8 * 375 * 128 * 2,        # 768_000 B
    "pos_kT": 1 * 8 * 128 * 375 * 2,     # 768_000 B
    "q_scaled": 1 * 8 * 128 * 375 * 2,   # 768_000 B  (same shape as pos_kT)
    "k_headsT": 1 * 8 * 128 * 375 * 2,  # 768_000 B
}
C_INPUT_SIZES = {
    "probs": 1 * 8 * 375 * 375 * 2,     # 2_250_000 B
    "v_heads": 1 * 8 * 375 * 128 * 2,    # 768_000 B
}


def synth_round(round_idx: int, is_a: bool) -> tuple[list[str], list[tuple[str, bytes]]]:
    sizes = A_INPUT_SIZES if is_a else C_INPUT_SIZES
    bundle = "island-attn-a-kt" if is_a else "island-pv"
    job = ["submit", bundle]
    inputs = []
    for name, n_bytes in sizes.items():
        job += ["--inline", f"{name}={n_bytes}"]
        # Fill with a deterministic pattern; byte size matters, content does not.
        inputs.append((name, bytes(((round_idx + i) & 0xFF) for i in range(n_bytes))))
    outputs = ["attention_scores_1", "matmul_0"] if is_a else ["attn_output_1"]
    for name in outputs:
        job += ["--emit", name]
    return job, inputs


def main() -> None:
    rounds = []
    for i in range(24):
        rounds.append(synth_round(i, is_a=True))
    for i in range(24):
        rounds.append(synth_round(i, is_a=False))

    # Warmup
    for job, ordered in rounds:
        a = build_request_orig(job, ordered)
        b = build_request_l1(job, ordered)
        assert a == b, "L1 is NOT byte-equivalent to original"
        assert hash(a) == hash(b), "hash mismatch"

    # Bench
    N = 5
    orig_ms, l1_ms = [], []
    for _ in range(N):
        t0 = time.monotonic_ns()
        for job, ordered in rounds:
            build_request_orig(job, ordered)
        orig_ms.append((time.monotonic_ns() - t0) / 1e6)

        t0 = time.monotonic_ns()
        for job, ordered in rounds:
            build_request_l1(job, ordered)
        l1_ms.append((time.monotonic_ns() - t0) / 1e6)

    print(f"per-pass total ms (orig): median={statistics.median(orig_ms):.2f} "
          f"min={min(orig_ms):.2f} max={max(orig_ms):.2f} (N={N})")
    print(f"per-pass total ms (L1):   median={statistics.median(l1_ms):.2f} "
          f"min={min(l1_ms):.2f} max={max(l1_ms):.2f} (N={N})")
    delta = statistics.median(orig_ms) - statistics.median(l1_ms)
    print(f"median delta: {delta:.2f} ms / pass (orig - L1)")
    print("byte-equivalence: PASS (all 48 rounds)")


if __name__ == "__main__":
    main()
