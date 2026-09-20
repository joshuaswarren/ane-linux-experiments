#!/usr/bin/env python3
"""qmm weight-fetch sensitivity micro v2 (protocol: receipts/2026-09-19-
gated-barriers-default-t6001-test-host.md "Hardened qmm weight-fetch micro
protocol"; v1 defects fixed per Main review 2026-09-20).

Measures per-dispatch duration of the decode-shape quantized single-row
GEMV as the weight working set grows, W ∈ {1,2,4,16,64,256} buffers,
randomized counterbalanced blocks. Two passes per slot:

  unbracketed  wall-clock only -> per-block WALL AVERAGES (labeled
               "wall_avg_us"; NOT per-dispatch durations).
  bracketed    same driver under MLX_OMARCHY_GPU_PROFILE -> per-dispatch
               durations parsed from the profiler ndjson in submission
               order (labeled "dispatch_us"), plus the wall averages as
               a cross-check. The ndjson dispatch count is asserted
               against the plan; a mismatch disqualifies the pass.

Timing hygiene: all inputs (x, every weight buffer) are mx.eval()'d
before timing; a warmup segment runs before any measured block; every
segment performs COMPLETE cycles over all W buffers (a W=256 segment
visits all 256 buffers), so the advertised working set is the touched
working set.

Identity/shapes: --k and --cols are REQUIRED for device runs - the
fused multi-group shape recovered from the dprof bindings does not map
to a clean single (k, cols) and is not guessed here. The signature
check compares the micro's captured dispatches against the decode
(n, gx) table; a mismatch records verdict "PROXY SHAPE".

Fail-first without GPU: --dry-run executes the real main path (plan,
segment/chunk arithmetic, attribution chunking, analysis) with device
calls stubbed; --selftest checks the pure analysis functions.

Usage (slot time):
  python3 scripts/qmm_weight_curve_micro.py --k K --cols C \
      --pass unbracketed --out /tmp/qmm_u.json
  MLX_OMARCHY_GPU_PROFILE=/tmp/qmm.ndjson \
      python3 scripts/qmm_weight_curve_micro.py --k K --cols C \
      --pass bracketed --profile /tmp/qmm.ndjson --out /tmp/qmm_b.json
"""
import argparse
import hashlib
import json
import os
import random
import statistics
import sys
import time

DECODE_SIGNATURE = {"kernel": 412, "shapes": [(112, 112), (144, 144), (608, 608)]}
W_SERIES = [1, 2, 4, 16, 64, 256]
BLOCKS = 6
MIN_STEPS = 200
WARMUP_STEPS = 32
SEED = 20260919
BOOTSTRAP = 10000


# ---------- pure planning (exercised by --dry-run, no device) ----------

def build_plan(blocks=BLOCKS, w_series=None, min_steps=MIN_STEPS, seed=SEED):
    """Segment plan: per block a seeded permutation of W; per segment
    enough steps for whole cycles over all W buffers (working set ==
    touched set) and >= min_steps total dispatches."""
    w_series = W_SERIES if w_series is None else w_series
    segments = []
    for b in range(blocks):
        order = w_series[:]
        random.Random(seed + b).shuffle(order)
        for w in order:
            cycles = -(-min_steps // w)  # ceil
            segments.append({"block": b, "w": w, "cycles": cycles,
                             "steps": cycles * w})
    return segments


def chunk_attribution(plan, durations, expected_kernels=None):
    """Split the in-order profiler dispatch-duration list into segments
    per the plan. Fail-first: wrong count or a non-uniform kernel
    stream raises rather than mislabeling."""
    if expected_kernels is not None:
        bad = len(durations) - sum(1 for d in durations if expected_kernels(d))
        if bad:
            raise SystemExit(
                f"attribution: {bad} dispatches outside the expected kernel "
                "stream; refusing to chunk by order")
    need = sum(s["steps"] for s in plan)
    if len(durations) != need:
        raise SystemExit(
            f"attribution: captured {len(durations)} dispatches, plan "
            f"expects {need}; refusing to chunk by order")
    out, i = [], 0
    for s in plan:
        out.append({"block": s["block"], "w": s["w"],
                    "us": durations[i:i + s["steps"]]})
        i += s["steps"]
    return out


# ---------- analysis (pure) ----------

def quantiles(vals):
    s = sorted(vals)
    return {"n": len(s), "p05": s[int(0.05 * len(s))], "p50": s[len(s) // 2],
            "p90": s[int(0.90 * len(s))], "mean": statistics.mean(s)}


def paired_deltas(block_stats):
    """block_stats: {W: [per-block stat]}. Absolute deltas vs W=1 with
    a bootstrap CI over blocks."""
    base = block_stats[1]
    rng = random.Random(SEED)
    out = {}
    for w, vals in sorted(block_stats.items()):
        if w == 1:
            out[w] = {"delta_us": 0.0, "ci95": [0.0, 0.0]}
            continue
        diffs = [b - a for a, b in zip(base, vals)]
        boots = sorted(statistics.median(
            rng.choice(diffs) for _ in diffs) for _ in range(BOOTSTRAP))
        out[w] = {"delta_us": statistics.median(diffs),
                  "ci95": [boots[BOOTSTRAP // 40], boots[-BOOTSTRAP // 40 - 1]]}
    return out


# ---------- device path ----------

def materialize_weights(k, cols, max_w):
    import mlx.core as mx
    x = mx.random.normal((1, k)).astype(mx.float16)
    mx.eval(x)
    weights = []
    for _ in range(max_w):
        w = mx.random.normal((cols, k)).astype(mx.float16)
        wq, scales, biases = mx.quantize(w, group_size=64, bits=4)
        mx.eval(wq), mx.eval(scales), mx.eval(biases)  # lazy -> real
        weights.append((wq, scales, biases))
    return x, weights


def run_device_pass(plan, k, cols, profile_path):
    """Returns (wall_blocks {(block,w): [wall avg per visit]}, meta)."""
    import mlx.core as mx
    max_w = max(s["w"] for s in plan)
    x, weights = materialize_weights(k, cols, max_w)

    def step(i, w):
        return mx.quantized_matmul(x, *weights[i % w], transpose=True,
                                   group_size=64, bits=4)

    t0 = time.perf_counter()
    for i in range(WARMUP_STEPS):  # shader compile, pool setup, caches
        mx.eval(step(i, max_w))
    wall = {}
    for s in plan:
        t0 = time.perf_counter()
        for i in range(s["steps"]):
            mx.eval(step(i, s["w"]))
        wall.setdefault((s["block"], s["w"]), []).append(
            (time.perf_counter() - t0) / s["steps"] * 1e6)
    wall_s = time.perf_counter() - t0
    return wall, {"wall_s": wall_s}


def read_dispatch_us(profile_path, plan_total):
    """Per-dispatch durations (us) for the LAST plan_total dispatch
    events, end-aligned: materialization and warmup dispatch kernels
    precede the measured plan in file order, so leading events are
    excluded by construction. Fail-first: fewer captured events than
    planned, or any tick-less dispatch inside the tail (pool exhaustion
    would silently shrink durations), aborts attribution."""
    meta, tail_start = None, None
    events = []  # (has_ticks, dur_us) in file order
    for line in open(profile_path):
        if not line.strip().startswith("{"):
            continue
        r = json.loads(line)
        if r.get("k") == "meta":
            meta = r
        elif r.get("k") == "d":
            if "t0" in r:
                events.append((True, (r["t1"] - r["t0"]) * meta["period_ns"] / 1e3,
                               r["e"]))
            else:
                events.append((False, None, r["e"]))
    if meta is None or len(events) < plan_total:
        raise SystemExit(
            f"{profile_path}: {len(events)} dispatch events, plan needs "
            f"{plan_total}; refusing end-alignment")
    tail = events[-plan_total:]
    lead_noticks = sum(1 for h, _, _ in events[:-plan_total] if not h)
    tail_noticks = sum(1 for h, _, _ in tail if not h)
    if tail_noticks:
        raise SystemExit(
            f"{profile_path}: {tail_noticks} dispatches in the measured "
            "tail recorded no timestamps (pool exhaustion?); durations "
            "would be silently dropped")
    kernels = {e for _, _, e in tail}
    return ([d for _, d, _ in tail], kernels, lead_noticks)


# ---------- driver ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=None,
                    help="REQUIRED for device passes; fused decode shape "
                         "does not map to a clean default and is not guessed")
    ap.add_argument("--cols", type=int, default=None, help="required with --k")
    ap.add_argument("--pass_", choices=["unbracketed", "bracketed"],
                    dest="pass_name")
    ap.add_argument("--profile", default="/tmp/qmm_micro.ndjson")
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true",
                    help="execute the real plan/attribution/analysis path "
                         "with device calls stubbed; no mlx, no GPU")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        pass
    elif not args.out:
        ap.error("--out is required")
    elif not args.pass_name:
        ap.error("--pass_ {unbracketed,bracketed} is required")

    if args.selftest:
        seg = build_plan()
        assert sum(s["steps"] for s in seg) >= BLOCKS * MIN_STEPS * len(W_SERIES)
        for s in seg:
            assert s["steps"] % s["w"] == 0 and s["steps"] >= MIN_STEPS, s
            assert s["steps"] >= s["w"]  # complete coverage of the set
        assert [s["w"] for s in seg if s["block"] == 0] != sorted(W_SERIES), \
            "permutation collapsed"
        fake = [1.0] * sum(s["steps"] for s in seg)
        chunks = chunk_attribution(seg, fake)
        assert len(chunks) == len(seg) and all(
            len(c["us"]) == s["steps"] for c, s in zip(chunks, seg))
        try:
            chunk_attribution(seg, fake[:-1])
            raise SystemExit("selftest: short stream must fail")
        except SystemExit as e:
            assert "refusing" in str(e)
        d = paired_deltas({1: [10.0] * BLOCKS, 16: [16.0] * BLOCKS})
        assert d[16]["delta_us"] > 5.5
        # End-alignment: leading materialization/warmup events (incl. a
        # tick-less one) are excluded; the plan-sized tail is returned.
        import tempfile, os
        total = sum(s["steps"] for s in seg)
        lines = ['{"k":"meta","period_ns":1.0,"valid_bits":64}']
        lines.append(json.dumps({"k": "d", "s": 1, "e": 55, "n": 1, "gx": 1,
                                 "gy": 1, "gz": 1, "h": 1, "tp": 0, "bar": 0,
                                 "t0": 0, "t1": 10}))
        lines.append(json.dumps({"k": "d", "s": 1, "e": 55, "n": 1, "gx": 1,
                                 "gy": 1, "gz": 1, "h": 1, "tp": 0, "bar": 0}))
        for i in range(total):
            lines.append(json.dumps({"k": "d", "s": 2, "e": 412, "n": 112,
                                     "gx": 112, "gy": 1, "gz": 1, "h": 1,
                                     "tp": 0, "bar": 1, "t0": i * 100000,
                                     "t1": i * 100000 + 50000}))
        with tempfile.NamedTemporaryFile("w", suffix=".ndjson",
                                         delete=False) as tf:
            tf.write("\n".join(lines) + "\n")
            path = tf.name
        try:
            durs, kernels, lead = read_dispatch_us(path, total)
            assert len(durs) == total and kernels == {412} and lead == 1
            assert all(d == 50.0 for d in durs)
            # Tick-less event inside the tail must abort, not shrink.
            bad = lines[:-1]
            bad.append(json.dumps({"k": "d", "s": 2, "e": 412, "n": 112,
                                   "gx": 112, "gy": 1, "gz": 1, "h": 1,
                                   "tp": 0, "bar": 1}))
            with open(path, "w") as f:
                f.write("\n".join(bad) + "\n")
            try:
                read_dispatch_us(path, total)
                raise SystemExit("selftest: tick-less tail must fail")
            except SystemExit as e:
                assert "no timestamps" in str(e)
        finally:
            os.unlink(path)
        print("PASS: plan, attribution chunking (incl. fail-short), "
              "end-alignment, tick-less tail guard, deltas")
        return

    if (args.pass_name == "bracketed" and not args.dry_run
            and not os.environ.get("MLX_OMARCHY_GPU_PROFILE")):
        ap.error("bracketed pass needs MLX_OMARCHY_GPU_PROFILE set before "
                 "process start")
    if (args.k is None) != (args.cols is None):
        ap.error("--k and --cols go together")
    if args.k is None:
        if not args.dry_run:
            ap.error("--k/--cols required for device passes (shape is not "
                     "guessed; see receipt table)")
        k = cols = 0
    else:
        k, cols = args.k, args.cols

    plan = build_plan()
    ident = {
        "k": k, "cols": cols, "pass": args.pass_name,
        "blocks": BLOCKS, "min_steps": MIN_STEPS, "warmup": WARMUP_STEPS,
        "w_series": W_SERIES, "seed": SEED,
        "total_dispatches": sum(s["steps"] for s in plan),
    }
    try:
        import mlx
        ident["mlx_version"] = getattr(mlx, "__version__", "unknown")
        lib = os.path.join(os.path.dirname(mlx.__file__), "lib", "libmlx.so")
        if os.path.exists(lib):
            ident["libmlx_sha256"] = hashlib.sha256(
                open(lib, "rb").read()).hexdigest()
    except ImportError:
        ident["mlx_version"] = "absent"

    if args.dry_run:
        fake_durs = [40.0] * ident["total_dispatches"]
        chunks = chunk_attribution(plan, fake_durs)
        by_w = {}
        for c in chunks:
            by_w.setdefault(c["w"], []).append(quantiles(c["us"])["p50"])
        ident["dry_run"] = True
        out = {"identity": ident, "plan": plan,
               "dispatch_us_p50_by_block": {str(w): v for w, v in by_w.items()},
               "paired_delta_vs_W1": paired_deltas(by_w)}
        json.dump(out, open(args.out, "w"), indent=1)
        print(f"dry-run OK: {len(plan)} segments, "
              f"{ident['total_dispatches']} dispatches planned; wrote {args.out}")
        return

    wall, meta = run_device_pass(plan, k, cols, args.profile)
    ident.update(meta)

    wall_blocks = {}
    for (b, w), vals in wall.items():
        wall_blocks.setdefault(w, []).append(statistics.mean(vals))

    out = {"identity": ident,
           "wall_avg_us_per_block": {str(w): v for w, v in wall_blocks.items()},
           "wall_avg_paired_delta_vs_W1": paired_deltas(wall_blocks)}

    if args.pass_name == "bracketed":
        durs, kernels, lead_noticks = read_dispatch_us(
            args.profile, ident["total_dispatches"])
        chunks = chunk_attribution(plan, durs)  # fail-first on count
        ident["signature_check"] = {
            "tail_kernels": sorted(kernels),
            "leading_events_excluded": lead_noticks,
            "decode_match": kernels == {DECODE_SIGNATURE["kernel"]},
            "verdict": "decode-shape kernel" if
                       kernels == {DECODE_SIGNATURE["kernel"]} else "PROXY SHAPE"}
        disp_blocks = {}
        for c in chunks:
            disp_blocks.setdefault(c["w"], []).append(
                statistics.median(c["us"]))
        out["dispatch_us_p50_per_block"] = {
            str(w): v for w, v in disp_blocks.items()}
        out["dispatch_us_quantiles_by_w"] = {
            str(w): quantiles([u for c in chunks if c["w"] == w
                               for u in c["us"]]) for w in W_SERIES}
        out["dispatch_paired_delta_vs_W1"] = paired_deltas(disp_blocks)
        out["note"] = ("dispatch_us derive from profiler t0/t1 and include "
                       "the instrument's per-dispatch overhead; compare "
                       "against the unbracketed wall averages before any "
                       "conclusion")

    json.dump(out, open(args.out, "w"), indent=1)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
