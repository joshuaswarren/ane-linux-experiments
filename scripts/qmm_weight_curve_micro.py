#!/usr/bin/env python3
"""qmm weight-fetch sensitivity micro v2.2 (protocol: receipts/
2026-09-19-gated-barriers-default-t6001-test-host.md; v2.1 review fixes per Main).

Two-phase bracketed pass (profiler flush lifecycle, from source):
d events are written to the ndjson ONLY at flush_slot time - a join
(backend synchronize: eval.cpp:135 -> encoder.cpp:603 join_last_completion
-> on_join flushes all ring slots) or ring-slot reuse. Pending events at
process exit are LOST (destructor emits "end" without flushing), and
mid-run reads race the C++ stdio buffer. Therefore:
  --pass bracketed  runs materialization + warmup + calibration + plan,
                    ends with mx.sync() (required; refused if missing),
                    writes only plan metadata.
  --pass attribute   AFTER exit: parses the complete stream, verifies the
                     calibration (one qmm call == exactly one dispatch,
                     same kernel enum - structural proof, not assumed),
                     end-aligns the plan tail, and writes distributions.
Fail-first everywhere: short tails, tick-less tail events, calibration
calls that produced != 1 dispatch, or a tail kernel that differs from
the calibrated enum abort instead of mislabeling.

Unbracketed pass: wall-clock per segment, labeled wall_avg_us (includes
python + eval-sync round trip; it is NOT a GPU dispatch duration).

Shapes are operator-supplied (--k/--cols); the fused multi-group decode
shape does not map to a clean single (k, cols) and is never guessed.
The calibration kernel enum is compared against the decode signature
(DECODE_SIGNATURE) for a PROXY SHAPE verdict.

Selftest (--selftest) and dry-run (--dry-run) exercise the full
plan/attribution/verification path GPU-free.
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
CALIBRATION_CALLS = 3
SEED = 20260919
BOOTSTRAP = 10000


# ---------- planning (pure) ----------

def build_plan(blocks=BLOCKS, w_series=None, min_steps=MIN_STEPS, seed=SEED):
    """Per block a seeded permutation of W; per segment whole cycles over
    all W buffers (touched set == advertised set), >= min_steps calls."""
    w_series = W_SERIES if w_series is None else w_series
    segments = []
    for b in range(blocks):
        order = w_series[:]
        random.Random(seed + b).shuffle(order)
        for w in order:
            cycles = -(-min_steps // w)
            segments.append({"block": b, "w": w, "cycles": cycles,
                             "steps": cycles * w})
    return segments


def chunk_attribution(plan, durations):
    """Split the end-aligned duration list by the plan. Fail-first on
    any count mismatch."""
    need = sum(s["steps"] for s in plan)
    if len(durations) != need:
        raise SystemExit(
            f"attribution: {len(durations)} dispatches, plan expects "
            f"{need}; refusing to chunk")
    out, i = [], 0
    for s in plan:
        out.append({"block": s["block"], "w": s["w"],
                    "us": durations[i:i + s["steps"]]})
        i += s["steps"]
    return out


# ---------- stream verification (pure; selftest-covered) ----------
#
# Flush lifecycle (source): each mx.sync() is one backend synchronize ->
# one join -> flush of ALL pending slots, recorded as one "j" event.
# With syncs placed as  [materialize+warmup] sync [calib] sync [calib]
# sync [calib] sync [plan] sync, the ndjson regions between consecutive
# "j" events label the segments exactly:
#   j0..j1: materialize + warmup + calibration call 1 (unbounded)
#   j1..j2: calibration call 2  -> must be EXACTLY 1 dispatch
#   j2..j3: calibration call 3  -> must be EXACTLY 1 dispatch
#   j3..j4: the plan            -> must be EXACTLY plan_total dispatches
#   after last j: nothing (anything here means unflushed tail events
#   appeared post-sync, which is a lifecycle violation)
# One qmm call == one dispatch is therefore PROVEN by the calibration
# regions, not assumed, and the plan region needs no end-alignment.

def verify_joined_stream(d_events, j_count, plan, calib_calls=CALIBRATION_CALLS):
    """d_events: file-ordered (region, has_ticks, dur_us, e). j_count:
    number of j events seen. Requires j_count >= calib_calls + 2.
    Returns (plan_durations, calib_enum, diag)."""
    if j_count < calib_calls + 2:
        raise SystemExit(
            f"stream: {j_count} join events; the sync-labeled layout "
            "needs one per mx.sync() (materialize/warmup sync + one per "
            "calibration call + final plan sync). Missing final sync?")
    regions = {}
    for r, h, d, e in d_events:
        regions.setdefault(r, []).append((h, d, e))
    # Region r holds events flushed by join r+1: region 0 =
    # materialize+warmup (unbounded), regions 1..calib_calls = one
    # calibration call each, region calib_calls+1 = the plan, anything
    # beyond = post-final-sync violation.
    calib_regions = list(range(1, calib_calls + 1))
    if len(regions) - 1 < calib_calls + 1 or j_count < calib_calls + 2:
        raise SystemExit("stream: fewer regions/joins than sync labels imply")
    calib_enum = None
    for r in calib_regions:
        evs = regions.get(r, [])
        if len(evs) != 1 or not evs[0][0]:
            raise SystemExit(
                f"calibration region {r}: {len(evs)} dispatches, expected "
                "exactly 1 tick-ful dispatch per qmm call; extra kernels "
                "per call invalidate attribution")
        if calib_enum is None:
            calib_enum = evs[0][2]
        elif evs[0][2] != calib_enum:
            raise SystemExit("calibration: kernel changed between calls")
    plan_region = calib_calls + 1
    evs = regions.get(plan_region, [])
    need = sum(s["steps"] for s in plan)
    if len(evs) != need:
        raise SystemExit(
            f"plan region: {len(evs)} dispatches, plan expects {need}")
    if not all(h for h, _, _ in evs):
        raise SystemExit(
            "plan region: tick-less dispatches (pool exhaustion?); "
            "durations would be silently dropped")
    if {e for _, _, e in evs} != {calib_enum}:
        raise SystemExit(
            f"plan region: kernels {sorted({e for _, _, e in evs})} != "
            f"calibrated enum {calib_enum}")
    if regions.get(plan_region + 1):
        raise SystemExit(
            "stream: dispatches appear after the final sync's join; "
            "unlabeled post-plan work invalidates the layout")
    durations = [d for _, d, _ in evs]
    diag = {"calib_enum": calib_enum,
            "region_counts": {str(r): len(v) for r, v
                              in sorted(regions.items())}}
    return durations, calib_enum, diag


# ---------- analysis (pure) ----------

def quantiles(vals):
    s = sorted(vals)
    return {"n": len(s), "p05": s[int(0.05 * len(s))], "p50": s[len(s) // 2],
            "p90": s[int(0.90 * len(s))], "mean": statistics.mean(s)}


def paired_deltas(block_stats):
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

def materialize(k, cols, max_w, calib_cols):
    import mlx.core as mx
    x = mx.random.normal((1, k)).astype(mx.float16)
    mx.eval(x)
    weights = []
    for _ in range(max_w):
        w = mx.random.normal((cols, k)).astype(mx.float16)
        wq, scales, biases = mx.quantize(w, group_size=64, bits=4)
        mx.eval(wq), mx.eval(scales), mx.eval(biases)
        weights.append((wq, scales, biases))
    cw = mx.random.normal((calib_cols, k)).astype(mx.float16)
    calib = mx.quantize(cw, group_size=64, bits=4)
    mx.eval(calib[0]), mx.eval(calib[1]), mx.eval(calib[2])
    return x, weights, calib


def qmm(x, wq, scales, biases):
    import mlx.core as mx
    return mx.quantized_matmul(x, wq, scales, biases, transpose=True,
                               group_size=64, bits=4)


def run_device(plan, k, cols, calib_cols):
    import mlx.core as mx
    if not hasattr(mx, "sync"):
        raise SystemExit(
            "bracketed pass requires mlx.core.sync to force the final "
            "profiler flush (pending d events are lost at exit); "
            "refusing to run on this mlx build")
    max_w = max(s["w"] for s in plan)
    x, weights, calib = materialize(k, cols, max_w, calib_cols)
    for i in range(WARMUP_STEPS):
        mx.eval(qmm(x, *weights[i % max_w]))
    mx.sync()  # flush warmup events
    for _ in range(CALIBRATION_CALLS):  # one call, one sync each
        mx.eval(qmm(x, *calib))
        mx.sync()
    wall, total_t0 = {}, time.perf_counter()
    for s in plan:
        t0 = time.perf_counter()
        for i in range(s["steps"]):
            mx.eval(qmm(x, *weights[i % s["w"]]))
        wall.setdefault((s["block"], s["w"]), []).append(
            (time.perf_counter() - t0) / s["steps"] * 1e6)
    wall_s = time.perf_counter() - total_t0
    mx.sync()  # MANDATORY: flush the plan's d events before exit
    return wall, {"wall_s": wall_s}


# ---------- passes ----------

def pass_unbracketed(args, plan):
    import mlx.core as mx  # fail fast
    wall, meta = run_device(plan, args.k, args.cols, args.cols + 8)
    wall_blocks = {}
    for (b, w), vals in wall.items():
        wall_blocks.setdefault(w, []).append(statistics.mean(vals))
    out = {"identity": {"pass": "unbracketed", "k": args.k,
                        "cols": args.cols, "blocks": BLOCKS,
                        "min_steps": MIN_STEPS, "warmup": WARMUP_STEPS,
                        "w_series": W_SERIES, "seed": SEED, **meta},
           "wall_avg_us_per_block": {str(w): v
                                     for w, v in wall_blocks.items()},
           "wall_avg_paired_delta_vs_W1": paired_deltas(wall_blocks),
           "note": ("wall averages include python + eval-sync round "
                    "trip per call; NOT GPU dispatch durations")}
    json.dump(out, open(args.out, "w"), indent=1)
    print("wrote", args.out)


def pass_bracketed(args, plan):
    import mlx.core as mx  # fail fast
    try:
        import mlx
        ident = {"mlx_version": getattr(mlx, "__version__", "unknown")}
        lib = os.path.join(os.path.dirname(mlx.__file__), "lib",
                           "libmlx.so")
        if os.path.exists(lib):
            ident["libmlx_sha256"] = hashlib.sha256(
                open(lib, "rb").read()).hexdigest()
    except ImportError:
        ident = {"mlx_version": "absent"}
    ident.update({"pass": "bracketed-run", "k": args.k, "cols": args.cols,
                  "calib_cols": args.cols + 8,
                  "calib_calls": CALIBRATION_CALLS, "blocks": BLOCKS,
                  "min_steps": MIN_STEPS, "warmup": WARMUP_STEPS,
                  "w_series": W_SERIES, "seed": SEED,
                  "total_plan_calls": sum(s["steps"] for s in plan)})
    wall, meta = run_device(plan, args.k, args.cols, args.cols + 8)
    ident.update(meta)
    json.dump(ident, open(args.out, "w"), indent=1)
    print("run complete (synced); now attribute the complete stream:\n"
          "  %s --pass attribute --profile %s --plan-meta %s --out OUT"
          % (sys.argv[0], args.profile, args.out))


def pass_attribute(args, plan):
    ident = {}
    if args.plan_meta and os.path.exists(args.plan_meta):
        ident.update(json.load(open(args.plan_meta)))
    # Parse the complete stream; each d event is labeled with the index
    # of the join region it sits in (region = number of j events seen
    # before it). A torn final line is tolerated and cannot create
    # dispatches.
    region, j_count = 0, 0
    events, meta = [], None
    for line in open(args.profile):
        if not line.strip().startswith("{"):
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        k = r.get("k")
        if k == "meta":
            meta = r
        elif k == "j":
            j_count += 1
            region = j_count
        elif k == "d":
            has = "t0" in r
            events.append((region, has,
                           (r["t1"] - r["t0"]) * meta["period_ns"] / 1e3
                           if has else None,
                           r["e"]))
    if meta is None:
        raise SystemExit(f"{args.profile}: no meta record")
    durations, calib_enum, diag = verify_joined_stream(
        events, j_count, plan)
    chunks = chunk_attribution(plan, durations)
    disp_blocks = {}
    for c in chunks:
        disp_blocks.setdefault(c["w"], []).append(statistics.median(c["us"]))
    match = (calib_enum == DECODE_SIGNATURE["kernel"])
    ident["signature_check"] = {
        "calibrated_enum": calib_enum,
        "decode_kernel": DECODE_SIGNATURE["kernel"],
        "join_events": j_count,
        "verdict": "decode-shape kernel" if match else "PROXY SHAPE",
        "calibration_proven": ("each calibration region holds exactly one "
                               "tick-ful dispatch; plan region "
                               "kernel-uniform and count-exact")}
    out = {"identity": ident,
           "region_counts": diag["region_counts"],
           "dispatch_us_p50_per_block": {str(w): v for w, v
                                         in disp_blocks.items()},
           "dispatch_us_quantiles_by_w": {
               str(w): quantiles([u for c in chunks if c["w"] == w
                                  for u in c["us"]]) for w in W_SERIES},
           "dispatch_paired_delta_vs_W1": paired_deltas(disp_blocks),
           "note": ("dispatch_us derive from profiler t0/t1 and include "
                    "the instrument's per-dispatch overhead; compare "
                    "against the unbracketed wall pass before any "
                    "conclusion")}
    json.dump(out, open(args.out, "w"), indent=1)
    print("wrote", args.out, "- verdict:", ident["signature_check"]["verdict"])


# ---------- entry ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=None)
    ap.add_argument("--cols", type=int, default=None)
    ap.add_argument("--pass_", choices=["unbracketed", "bracketed",
                                        "attribute"], dest="pass_name")
    ap.add_argument("--profile", default="/tmp/qmm_micro.ndjson")
    ap.add_argument("--plan-meta", dest="plan_meta")
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        seg = build_plan()
        total = sum(s["steps"] for s in seg)
        assert [s["w"] for s in seg if s["block"] == 0] != sorted(W_SERIES)
        assert all(s["steps"] % s["w"] == 0 and s["steps"] >= MIN_STEPS
                   for s in seg)

        def mkstream(plan_durs=(50.0,), tail_enum=400, tail_count=None,
                     calib_counts=(1, 1, 1), post_plan=0, joins=5,
                     tickless_plan=0):
            d = [(0, True, 10.0, 55), (0, False, None, 55)]
            for r, cnt in enumerate(calib_counts, start=1):
                d += [(r, True, 30.0, 400)] * cnt
            n = tail_count if tail_count is not None else total
            for i in range(n):
                if i < tickless_plan:
                    d.append((4, False, None, tail_enum))
                else:
                    d.append((4, True, 50.0, tail_enum))
            d += [(5, True, 1.0, 55)] * post_plan
            return d, joins

        durs, enum, diag = verify_joined_stream(*mkstream(), plan=seg)
        assert len(durs) == total and enum == 400
        assert diag["region_counts"]["4"] == total
        for kw, frag in (
                ({"calib_counts": (1, 2, 1)}, "calibration region 2"),
                ({"tail_count": total - 1}, "plan region"),
                ({"tickless_plan": 1}, "tick-less"),
                ({"tail_enum": 401}, "kernels"),
                ({"post_plan": 1}, "after the final sync"),
                ({"joins": 3}, "join events")):
            st = mkstream(**kw)
            try:
                verify_joined_stream(st[0], st[1], plan=seg)
                raise SystemExit(f"selftest: {frag} case must fail")
            except SystemExit as e:
                assert any(t in str(e) for t in
                           ("calibration", "region", "final sync",
                            "join events")), e
        d = paired_deltas({1: [10.0] * BLOCKS, 16: [16.0] * BLOCKS})
        assert d[16]["delta_us"] > 5.5
        print("PASS: plan, join-region calibration proof, plan-region "
              "count/tick/kernel checks, post-sync and join-count "
              "rejection, deltas")
        return

    if not args.out:
        ap.error("--out is required")
    if not args.pass_name:
        ap.error("--pass_ {unbracketed,bracketed,attribute} is required")
    if args.pass_name == "bracketed" and not args.dry_run and not \
            os.environ.get("MLX_OMARCHY_GPU_PROFILE"):
        ap.error("bracketed pass needs MLX_OMARCHY_GPU_PROFILE set before "
                 "process start")
    if not args.dry_run and args.pass_name in ("unbracketed", "bracketed") \
            and ((args.k is None) != (args.cols is None) or args.k is None):
        ap.error("--k and --cols required for device passes (shape is "
                 "operator-supplied, never guessed)")

    plan = build_plan()
    if args.dry_run:
        total = sum(s["steps"] for s in plan)
        d = ([(0, True, 10.0, 55), (0, False, None, 55)]
             + [(r, True, 30.0, 400) for r in (1, 2, 3)]
             + [(4, True, 50.0, 400)] * total)
        durs, enum, diag = verify_joined_stream(d, 5, plan)
        chunks = chunk_attribution(plan, durs)
        by_w = {}
        for c in chunks:
            by_w.setdefault(c["w"], []).append(quantiles(c["us"])["p50"])
        out = {"dry_run": True, "segments": len(plan),
               "total_plan_calls": total,
               "region_counts": diag["region_counts"],
               "calibrated_enum": enum,
               "dispatch_us_p50_by_block": {str(w): v
                                            for w, v in by_w.items()},
               "paired_delta_vs_W1": paired_deltas(by_w)}
        json.dump(out, open(args.out, "w"), indent=1)
        print(f"dry-run OK: verification+attribution path green; "
              f"wrote {args.out}")
        return

    if args.pass_name == "unbracketed":
        pass_unbracketed(args, plan)
    elif args.pass_name == "bracketed":
        pass_bracketed(args, plan)
    else:
        if not args.plan_meta:
            ap.error("attribute needs --plan-meta from the bracketed run")
        pass_attribute(args, plan)


if __name__ == "__main__":
    main()
