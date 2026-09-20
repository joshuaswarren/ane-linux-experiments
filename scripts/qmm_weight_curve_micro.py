#!/usr/bin/env python3
"""qmm weight-fetch sensitivity micro (pre-registered, protocol in
receipts/2026-09-19-gated-barriers-default-t6001-test-host.md "Hardened qmm
weight-fetch micro protocol").

Measures per-dispatch duration of the decode-shape quantized single-row
GEMV as the weight working set grows W ∈ {1,2,4,16,64,256} buffers,
randomized and counterbalanced in paired blocks, once under the GPU
profiler (bracketed) and once unprofiled (wall-clock), reporting
absolute deltas with distributions - no ratio thresholds, no residency
claims from sizes. Requires: mlx with the omarchy backend on the target
device, MLX_OMARCHY_GPU_PROFILE set for the bracketed pass.

Identity check: the micro's captured dispatches are compared against
the decode signature table (kernel enum family, n, gx tuples); a
mismatch downgrades the run to "proxy shape" - recorded, never silent.

--selftest runs the pure-python analysis path (no mlx, no GPU).

Usage (slot time):
  python3 scripts/qmm_weight_curve_micro.py --bracketed \
      --profile /tmp/qmm_micro.ndjson --out /tmp/qmm_micro_b.json
  python3 scripts/qmm_weight_curve_micro.py --out /tmp/qmm_micro_u.json
"""
import argparse
import json
import random
import statistics
import sys
import time

# Decode dispatch signature recovered from the dprof captures
# (kernel enum 412, QmmVecQ4MultiSubgroupF16; see receipt table).
DECODE_SIGNATURE = {"kernel": 412, "shapes": [(112, 112), (144, 144), (608, 608)]}
WEIGHT_BYTES = {112: 458752, 144: 458752, 608: 2469888}
W_SERIES = [1, 2, 4, 16, 64, 256]
BLOCKS = 6
STEPS = 200
SEED = 20260919


def qmm_step(x, wq, scales, biases):
    """One decode-shape quantized GEMV dispatch (single row)."""
    import mlx.core as mx
    return mx.quantized_matmul(x, wq, scales, biases, transpose=True,
                               group_size=64, bits=4)


def build_weights(k, cols, n_buffers):
    import mlx.core as mx
    ws = []
    for _ in range(n_buffers):
        w = mx.random.normal((cols, k)).astype(mx.float16)
        wq, scales, biases = mx.quantize(w, group_size=64, bits=4)
        ws.append((wq, scales, biases))
    return ws


def capture_signature(profile_path):
    """Kernel enum + (n, gx) pairs seen in a profile stream."""
    sig = set()
    for line in open(profile_path):
        if not line.strip().startswith("{"):
            continue
        r = json.loads(line)
        if r.get("k") == "d":
            sig.add((r["e"], r["n"], r["gx"]))
    return sorted(sig)


def quantiles(vals):
    s = sorted(vals)
    return {"n": len(s), "p05": s[int(0.05 * len(s))],
            "p50": s[len(s) // 2], "p90": s[int(0.90 * len(s))],
            "mean": statistics.mean(s)}


def paired_deltas(block_medians):
    """block_medians: {W: [per-block median us]}. Returns absolute
    deltas vs W=1 with a bootstrap CI over blocks."""
    base = block_medians[1]
    out = {}
    rng = random.Random(SEED)
    for w, vals in sorted(block_medians.items()):
        if w == 1:
            out[w] = {"delta_us": 0.0, "ci95": [0.0, 0.0]}
            continue
        diffs = [b - a for a, b in zip(base, vals)]
        boots = sorted(
            statistics.median(rng.choice(diffs) for _ in diffs)
            for _ in range(10000))
        out[w] = {"delta_us": statistics.median(diffs),
                  "ci95": [boots[249], boots[9749]]}
    return out


def run_pass(bracketed, args):
    import mlx.core as mx
    k, cols = args.k, args.cols
    x = mx.random.normal((1, k)).astype(mx.float16)
    weights = build_weights(k, cols, max(W_SERIES))
    blocks = {}
    for b in range(BLOCKS):
        order = W_SERIES[:]
        random.Random(SEED + b).shuffle(order)
        for w in order:
            t0 = time.perf_counter()
            for i in range(STEPS):
                y = qmm_step(x, *weights[i % w])
                mx.eval(y)
            dt = (time.perf_counter() - t0) / STEPS * 1e6
            blocks.setdefault(w, []).append(dt)
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=2048,
                    help="GEMV k dim (defaults approximate the recovered "
                         "0.46 MB shape; the signature check validates)")
    ap.add_argument("--cols", type=int, default=400)
    ap.add_argument("--bracketed", action="store_true",
                    help="run under MLX_OMARCHY_GPU_PROFILE (env must be "
                         "set before process start)")
    ap.add_argument("--profile", default="/tmp/qmm_micro.ndjson")
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if not args.out and not args.selftest:
        ap.error("--out is required unless --selftest")

    if args.selftest:
        bm = {1: [10.0, 10.2, 10.1, 10.0, 10.1, 10.0],
              16: [16.0, 16.4, 16.2, 16.1, 16.3, 16.2],
              256: [17.0, 17.1, 17.2, 16.9, 17.0, 17.1]}
        d = paired_deltas(bm)
        assert d[16]["delta_us"] > 5.5 and d[256]["delta_us"] > d[16]["delta_us"]
        assert d[1] == {"delta_us": 0.0, "ci95": [0.0, 0.0]}
        q = quantiles([1.0, 2.0, 3.0, 4.0, 100.0])
        assert q["p50"] == 3.0 and q["n"] == 5
        print("PASS: analysis path (paired deltas, bootstrap, quantiles)")
        return

    import mlx.core as mx  # noqa: F401 - fail fast if mlx missing

    import hashlib, os
    import mlx
    lib = os.path.join(os.path.dirname(mlx.__file__), "lib", "libmlx.so")
    if os.path.exists(lib):
        ident["libmlx_sha256"] = hashlib.sha256(open(lib, "rb").read()).hexdigest()
    ident["mlx_version"] = getattr(mlx, "__version__", "unknown")
    ident["bracketed"] = args.bracketed
    ident["k"] = args.k
    ident["cols"] = args.cols
    ident["weight_series"] = W_SERIES
    ident["blocks"] = BLOCKS
    ident["steps"] = STEPS
    ident["seed"] = SEED

    t0 = time.perf_counter()
    blocks = run_pass(args.bracketed, args)
    wall_s = time.perf_counter() - t0

    sig = None
    if args.bracketed:
        sig = capture_signature(args.profile)
        matched = [t for t in sig
                   if t[0] == DECODE_SIGNATURE["kernel"]
                   and t[1:] in DECODE_SIGNATURE["shapes"]]
        ident["signature_check"] = {
            "seen": sig, "decode_match": matched,
            "verdict": "decode-shape match" if matched else
                       "PROXY SHAPE - dispatch signature differs from decode"}

    out = {"identity": ident, "wall_s": wall_s,
           "per_w_us": {str(w): quantiles(v) for w, v in blocks.items()},
           "block_medians_us": {str(w): v for w, v in blocks.items()},
           "paired_delta_vs_W1": paired_deltas(blocks)}
    if args.bracketed:
        out["note"] = ("bracketed pass: durations include the profiler's "
                       "per-dispatch overhead; compare against the "
                       "unbracketed pass before any conclusion")
    json.dump(out, open(args.out, "w"), indent=1)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
