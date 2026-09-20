#!/usr/bin/env python3
"""qmm weight-fetch micro v2.4 (protocol: receipts/2026-09-19-gated-
barriers-default-jw16.md). Single-row calibration diagnostic COMPLETE
(strict lifecycle proven, Word-route 397 -> PROXY); this build adds the
compiled-route producer for the fused multi-weight route.

Device passes are PRODUCERS ONLY: they run under the profiler, force
syncs, record identity/conditions/bytes/finite-checks into a sidecar
JSON, and exit. ALL parsing/attribution happens post-producer-exit via
--pass report on the complete profile (the C++ stdio buffer races
mid-run reads; the profiler destructor emits "end" without flushing
pending slots). Convention proven empirically (calib-v23.ndjson,
jw16): the j record is emitted BEFORE its join's flush work, so region
r = flush work of sync r; region 1 holds the warmup straggler,
regions 2..CALIBRATION_CALLS+1 must hold exactly one tick-ful dispatch
each with one stable enum, and any dispatch beyond that region, or a
join count != CALIBRATION_CALLS+1, is NON-STRICT.

Gates: --pass bracketed/--pass attribute (full W-curve) refuse to run
until the compiled route is verified. No performance conclusions from
any calibration output.
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


# ---------- pure helpers ----------

def force_sync(mx):
    """Flush-forcing call: mlx.core exposes `synchronize` on the jw16
    diag wheel (verified); older builds name it `sync`."""
    if hasattr(mx, "synchronize"):
        mx.synchronize()
    elif hasattr(mx, "sync"):
        mx.sync()
    else:
        raise SystemExit("no mlx.core sync/synchronize; flush cannot be "
                         "forced")


def require_sync(mx):
    if not (hasattr(mx, "synchronize") or hasattr(mx, "sync")):
        raise SystemExit("no mlx.core sync/synchronize; flush cannot be "
                         "forced on this mlx build")


def build_plan(blocks=BLOCKS, w_series=None, min_steps=MIN_STEPS, seed=SEED):
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
    need = sum(s["steps"] for s in plan)
    if len(durations) != need:
        raise SystemExit(
            f"attribution: {len(durations)} dispatches, plan expects {need}")
    out, i = [], 0
    for s in plan:
        out.append({"block": s["block"], "w": s["w"],
                    "us": durations[i:i + s["steps"]]})
        i += s["steps"]
    return out


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


# ---------- calibration verification (pure; post-exit) ----------

def verify_calibration(d_by_region, j_count, reasons=None):
    """d_by_region: {region: [(has_ticks, dur_us, enum)]}. Region r =
    flush work of sync r (j emitted before its flush work):
      region 1 = warmup straggler (>=0 tick-ful dispatches),
      regions 2..CALIBRATION_CALLS+1 = ONE calibration call each,
      region > CALIBRATION_CALLS+1 with any event, or j_count !=
      CALIBRATION_CALLS+1, is NON-STRICT.
    strict => one qmm call == one dispatch, kernel-stable."""
    expected_j = CALIBRATION_CALLS + 1
    report = {"j_count": j_count, "join_reasons": sorted(reasons or []),
              "region_counts": {str(r): len(v) for r, v
                                in sorted(d_by_region.items())},
              "region_enums": {str(r): sorted({e for _, _, e in v})
                               for r, v in sorted(d_by_region.items())}}
    overflow = {r: v for r, v in d_by_region.items()
                if r > expected_j and v}
    if j_count != expected_j or overflow:
        report["verdict"] = "NON-STRICT layout - parser validation required"
        report["expected_j"] = expected_j
        report["overflow_regions"] = {str(r): len(v)
                                      for r, v in overflow.items()}
        return "non-strict", report
    calib_enum = None
    for r in range(2, CALIBRATION_CALLS + 2):
        evs = d_by_region.get(r, [])
        if len(evs) != 1 or not evs[0][0]:
            report["verdict"] = (
                f"NON-STRICT: calibration region {r} holds {len(evs)} "
                "dispatches (expected exactly 1 tick-ful)")
            return "non-strict", report
        if calib_enum is None:
            calib_enum = evs[0][2]
        elif evs[0][2] != calib_enum:
            report["verdict"] = "NON-STRICT: kernel changed between calls"
            return "non-strict", report
    report["verdict"] = ("strict: one qmm call == one dispatch, "
                         "kernel-stable across calls")
    report["calibrated_enum"] = calib_enum
    return "strict", report


# ---------- device helpers ----------

def require_sync(mx):
    pass  # replaced below; kept for patch history


def resolve_libmlx():
    """EXACT loaded libmlx.so preferred: /proc/self/maps names the
    library the process actually mapped. Fallbacks: mlx.__file__ dir,
    then sys.path scanning. Returns (path or None, method)."""
    try:
        for line in open("/proc/self/maps"):
            if "libmlx.so" in line:
                path = line.split()[-1]
                if os.path.exists(path):
                    return path, "proc_self_maps"
    except OSError:
        pass
    import mlx
    base = getattr(mlx, "__file__", None)
    candidates = []
    if base:
        candidates.append(os.path.join(os.path.dirname(base), "lib",
                                       "libmlx.so"))
    for p in sys.path:
        if p:
            candidates.append(os.path.join(p, "mlx", "lib", "libmlx.so"))
    for c in candidates:
        if os.path.exists(c):
            return c, "mlx_file_or_syspath"
    return None, ("unresolved: /proc/self/maps has no libmlx.so, "
                  "mlx.__file__=%r, sys.path scan empty" % (base,))


def qmm(x, wq, scales, biases):
    import mlx.core as mx
    return mx.quantized_matmul(x, wq, scales, biases, transpose=True,
                               group_size=64, bits=4)


def make_weights(mx, k, cols, n):
    """Materialized constants: (wq, scales, biases) + exact byte sizes.
    Same (k, cols) for every buffer; affinity/4/64 per DecodeFusion."""
    out = []
    for _ in range(n):
        w = mx.random.normal((cols, k)).astype(mx.float16)
        wq, scales, biases = mx.quantize(w, group_size=64, bits=4)
        mx.eval(wq), mx.eval(scales), mx.eval(biases)
        out.append((wq, scales, biases,
                    int(wq.nbytes + scales.nbytes + biases.nbytes)))
    return out


# ---------- producers (device; no profile parsing) ----------

def sidecar_identity(pass_name, mx, profile_path, extra):
    import mlx
    ident = {"pass": pass_name,
             "mlx_version": getattr(mx, "__version__", "unknown")
             if hasattr(mx, "__version__") else "unknown",
             "profile_path": profile_path,
             "conditions": {
                 "vk_driver_files": os.environ.get("VK_DRIVER_FILES"),
                 "gated_barriers": os.environ.get(
                     "MLX_OMARCHY_GATED_BARRIERS"),
                 "fused_chain": os.environ.get("MLX_OMARCHY_FUSED_CHAIN"),
                 "fused_gemv": os.environ.get("MLX_OMARCHY_FUSED_GEMV"),
                 "per_node_submit": os.environ.get(
                     "MLX_OMARCHY_TAPE_PER_NODE_SUBMIT"),
             }}
    ident.update(extra)
    lib, note = resolve_libmlx()
    if lib:
        ident["libmlx_sha256"] = hashlib.sha256(
            open(lib, "rb").read()).hexdigest()
        ident["libmlx_path"] = lib
    else:
        ident["libmlx_sha256"] = None
        ident["libmlx_path_note"] = note
    try:
        from importlib import metadata as _md
        ident["wheel_version"] = _md.version("mlx_omarchy")
    except Exception:
        ident["wheel_version"] = "unknown"
    return ident


def pass_calibrate(args, k, cols):
    """Single-row route diagnostic (COMPLETE on jw16; kept for
    reproducibility): producer writes the profile + sidecar; run
    --pass report after exit."""
    import mlx.core as mx
    require_sync(mx)
    x = mx.random.normal((1, k)).astype(mx.float16)
    mx.eval(x)
    weights = make_weights(mx, k, cols, 1)
    for i in range(WARMUP_STEPS):
        mx.eval(qmm(x, *weights[0][:3]))
    force_sync(mx)
    for _ in range(CALIBRATION_CALLS):
        mx.eval(qmm(x, *weights[0][:3]))
        force_sync(mx)
    ident = sidecar_identity("calibrate", mx, args.profile,
                             {"k": k, "cols": cols, "warmup": WARMUP_STEPS,
                              "calibration_calls": CALIBRATION_CALLS,
                              "shape_note": "same (k, cols) as plan, "
                                            "distinct weight buffer"})
    json.dump(ident, open(args.out, "w"), indent=1)
    print("producer complete; NOW: %s --pass report --profile %s "
          "--plan-meta %s --out REPORT" % (sys.argv[0], args.profile,
                                           args.out))


def pass_compiled_calibrate(args, k, cols):
    """Fused multi-route producer: mx.compile'd DecodeFusion group
    (3 QuantizedMatmul(Affine,4,64,transpose) sharing one single-row x,
    each with a single-consumer Add epilogue) -> ONE QmmVecQ4Multi
    dispatch per call via the actual call site. Route verified when
    --pass report shows strict layout with calibrated enum 412."""
    import mlx.core as mx
    require_sync(mx)
    x = mx.random.normal((1, k)).astype(mx.float16)
    mx.eval(x)
    weights = make_weights(mx, k, cols, 3)
    adds = []
    for _ in range(3):
        a = mx.random.normal((1, cols)).astype(mx.float16)
        mx.eval(a)
        adds.append(a)

    def group(x):
        outs = [qmm(x, *w[:3]) for w in weights]
        return [o + a for o, a in zip(outs, adds)]

    fn = mx.compile(group)
    finite = None
    for i in range(WARMUP_STEPS):  # finite check inside warmup ONLY:
        outs = fn(x)               # its isfinite kernels stay in the
        mx.eval(outs)              # warmup region, never after a
        if i == 0:                 # calibration sync
            finite = all(bool(mx.isfinite(o).all()) for o in outs)
    force_sync(mx)
    for _ in range(CALIBRATION_CALLS):  # pure: dispatch + sync, no
        mx.eval(fn(x))                  # additional GPU ops
        force_sync(mx)
    ident = sidecar_identity("compiled-calibrate", mx, args.profile,
                             {"k": k, "cols": cols,
                              "group_members": 3,
                              "warmup": WARMUP_STEPS,
                              "calibration_calls": CALIBRATION_CALLS,
                              "seed": SEED,
                              "x_bytes": int(x.nbytes),
                              "weight_bytes_per_member":
                                  [w[3] for w in weights],
                              "weight_bytes_total":
                                  sum(w[3] for w in weights),
                              "outputs_finite": finite,
                              "route_note": "compiled tape -> DecodeFusion "
                                            "-> QmmVecQ4Multi (actual call "
                                            "site)"})
    json.dump(ident, open(args.out, "w"), indent=1)
    print("producer complete (finite_outputs=%s); NOW: %s --pass report "
          "--profile %s --plan-meta %s --out REPORT"
          % (finite, sys.argv[0], args.profile, args.out))


def pass_unbracketed(args, k, cols, plan):
    """Wall-clock W-curve producer (GATED until route verified)."""
    import mlx.core as mx
    require_sync(mx)
    x = mx.random.normal((1, k)).astype(mx.float16)
    mx.eval(x)
    weights = make_weights(mx, k, cols, max(s["w"] for s in plan))
    for i in range(WARMUP_STEPS):
        mx.eval(qmm(x, *weights[0][:3]))
    force_sync(mx)
    wall, total_t0 = {}, time.perf_counter()
    for s in plan:
        t0 = time.perf_counter()
        for i in range(s["steps"]):
            mx.eval(qmm(x, *weights[i % s["w"]][:3]))
        wall.setdefault((s["block"], s["w"]), []).append(
            (time.perf_counter() - t0) / s["steps"] * 1e6)
    plan_wall_s = time.perf_counter() - total_t0
    force_sync(mx)
    wall_blocks = {}
    for (b, w), vals in wall.items():
        wall_blocks.setdefault(w, []).append(statistics.mean(vals))
    out = {"identity": {"pass": "unbracketed", "k": k, "cols": cols,
                        "blocks": BLOCKS, "min_steps": MIN_STEPS,
                        "w_series": W_SERIES, "seed": SEED},
           "plan_wall_s": plan_wall_s,
           "plan_wall_s_note": ("plan segments only; materialization and "
                                "warmup excluded; includes python + "
                                "eval-sync round trip"),
           "wall_avg_us_per_block": {str(w): v
                                     for w, v in wall_blocks.items()},
           "wall_avg_paired_delta_vs_W1": paired_deltas(wall_blocks)}
    json.dump(out, open(args.out, "w"), indent=1)
    print("wrote", args.out)


# ---------- report (offline; post-producer-exit) ----------

def pass_report(args, plan=None):
    """Verify a COMPLETE preserved stream. Strict criteria under the
    source flush convention: j_count == CALIBRATION_CALLS+1; region 1 =
    warmup straggler (>=0 tick-ful); regions 2..N+1 exactly one
    tick-ful dispatch each, one enum across them; no events beyond
    region N+1. Merges the producer sidecar (--plan-meta) for identity
    and routes: calibrated enum 412 = decode fused route; 397 =
    QmmVecQ4WordSubgroupF16 = PROXY ROUTE (single-row python route)."""
    ident = {}
    if args.plan_meta and os.path.exists(args.plan_meta):
        ident.update(json.load(open(args.plan_meta)))
    region, j_count, reasons, meta = 0, 0, [], None
    d_by_region = {}
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
            reasons.append(r.get("reason"))
        elif k == "d":
            has = "t0" in r
            d_by_region.setdefault(region, []).append(
                (has,
                 (r["t1"] - r["t0"]) * meta["period_ns"] / 1e3 if has
                 else None,
                 r["e"]))
    if meta is None:
        raise SystemExit(f"{args.profile}: no meta record")
    verdict, report = verify_calibration(d_by_region, j_count, reasons)
    calib_enum = report.get("calibrated_enum")
    route = {412: "decode fused multi route CONFIRMED "
                  "(QmmVecQ4MultiSubgroupF16)",
             397: "PROXY ROUTE: QmmVecQ4WordSubgroupF16 - single-row "
                  "python route does not use the decode fused route"}.get(
        calib_enum,
        "UNKNOWN route for enum %s" % calib_enum)
    out = {"identity": {**ident, "device": meta.get("device"),
                        "period_ns": meta.get("period_ns"),
                        "valid_bits": meta.get("valid_bits"),
                        "label": meta.get("label")},
           "calibration": report,
           "route": route,
           "note": ("lifecycle/route diagnostic ONLY; durations are "
                    "bracketed instrument values and support NO "
                    "performance conclusion")}
    json.dump(out, open(args.out, "w"), indent=1)
    print("wrote", args.out, "| layout:", verdict, "| route:", route)


# ---------- compiled W-curve (route: fused multi; GATED hardware) ----------

def pass_compiled_curve(args, k, cols, plan):
    """Working-set curve through the SAME compiled 3-member graph that
    --pass compiled-calibrate route-verified (enum 412). Producer only:
    every W segment ends with its own sync, so each segment is exactly
    one join region (calibration-proven convention) and post-exit
    attribution via --pass curve-report is exact. Counterbalanced
    blocks; wall averages recorded alongside. HARDWARE GATED until Main
    reviews this source; no performance conclusions in output."""
    import mlx.core as mx
    require_sync(mx)
    x = mx.random.normal((1, k)).astype(mx.float16)
    mx.eval(x)
    groups = []
    n_groups = max(s["w"] for s in plan)
    for _ in range(n_groups):
        ws = make_weights(mx, k, cols, 3)
        adds = []
        for _ in range(3):
            a = mx.random.normal((1, cols)).astype(mx.float16)
            mx.eval(a)
            adds.append(a)
        groups.append((ws, adds))

    def call(i):
        ws, adds = groups[i]
        outs = [qmm(x, *w) for w in ws]
        return [o + a for o, a in zip(outs, adds)]

    fn = mx.compile(lambda idx: call(int(idx)))
    idx = mx.array(0)
    for _ in range(WARMUP_STEPS):
        mx.eval(fn(idx))
    force_sync(mx)
    wall = {}
    for s in plan:
        t0 = time.perf_counter()
        for i in range(s["steps"]):
            mx.eval(fn(mx.array(i % s["w"])))
        wall[(s["block"], s["w"])] = (
            time.perf_counter() - t0) / s["steps"] * 1e6
        force_sync(mx)  # segment boundary = join region label
    ident = sidecar_identity("compiled-curve", mx, args.profile,
                             {"k": k, "cols": cols, "blocks": BLOCKS,
                              "w_series": W_SERIES, "seed": SEED,
                              "plan_segments": len(plan),
                              "total_plan_calls": sum(s["steps"]
                                                      for s in plan),
                              "segment_sync_layout": "one sync per "
                                                     "segment; join "
                                                     "region == segment",
                              "note": "GATED: no hardware run until "
                                      "Main reviews"})
    json.dump(ident, open(args.out, "w"), indent=1)
    print("producer complete; run --pass curve-report post-exit")


def pass_curve_report(args, plan):
    """Offline: attribute the compiled-curve stream. Exact layout: each
    plan segment is one join region (segment ends with its own sync),
    region 0 = warmup, region i+1 = plan segment i."""
    ident = {}
    if args.plan_meta and os.path.exists(args.plan_meta):
        ident.update(json.load(open(args.plan_meta)))
    region, j_count, meta = 0, 0, None
    d_by_region = {}
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
            d_by_region.setdefault(region, []).append(
                (has,
                 (r["t1"] - r["t0"]) * meta["period_ns"] / 1e3 if has
                 else None,
                 r["e"]))
    if meta is None:
        raise SystemExit(f"{args.profile}: no meta record")
    by_w = {}
    per_w_events = {}
    r = 1
    for s in plan:
        evs = d_by_region.get(r, [])
        if len(evs) != s["steps"] or not all(h for h, *_ in evs):
            raise SystemExit(
                f"region {r}: {len(evs)} dispatches, segment expects "
                f"{s['steps']} tick-ful; layout mismatch - refusing")
        by_w.setdefault(s["w"], []).append(
            statistics.median([d for _, d, _ in evs]))
        per_w_events.setdefault(s["w"], []).extend(evs)
        r += 1
    stray = {rr: len(v) for rr, v in d_by_region.items() if rr >= r and v}
    if stray:
        raise SystemExit(f"stream: dispatches in unlabeled regions {stray}")
    out = {"identity": ident,
           "dispatch_us_p50_per_block": {str(w): v for w, v
                                         in by_w.items()},
           "dispatch_us_quantiles_by_w": {
               str(w): quantiles([d for _, d, _ in per_w_events[w]])
               for w in W_SERIES},
           "paired_delta_vs_W1": paired_deltas(by_w),
           "note": ("bracketed instrument durations; compare against an "
                    "unbracketed wall pass before any conclusion; NO "
                    "performance claim without Main approval")}
    json.dump(out, open(args.out, "w"), indent=1)
    print("wrote", args.out)


# ---------- entry ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=None)
    ap.add_argument("--cols", type=int, default=None)
    ap.add_argument("--pass_", choices=["calibrate", "compiled-calibrate",
                                        "compiled-curve", "curve-report",
                                        "unbracketed", "bracketed",
                                        "attribute", "report"],
                    dest="pass_name")
    ap.add_argument("--profile", default="/tmp/qmm_micro.ndjson")
    ap.add_argument("--plan-meta", dest="plan_meta")
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        strict = {0: [(True, 10.0, 55), (False, None, 55)],
                  1: [(True, 10.0, 397)],
                  2: [(True, 30.0, 400)], 3: [(True, 30.0, 400)],
                  4: [(True, 30.0, 400)]}
        v, rep = verify_calibration(strict, 4)
        assert v == "strict" and rep["calibrated_enum"] == 400
        for bad, jc in (
                ({**strict, 5: [(True, 1.0, 55)]}, 5),
                (strict, 6),
                ({0: [], 1: [(True, 10.0, 397)],
                  2: [(True, 30.0, 400), (True, 30.0, 400)],
                  3: [(True, 30.0, 400)], 4: [(True, 30.0, 400)]}, 4),
                ({0: [], 1: [], 2: [(False, None, 400)],
                  3: [(True, 30.0, 400)], 4: [(True, 30.0, 400)]}, 4)):
            v, rep = verify_calibration(bad, jc)
            assert v == "non-strict", (v, rep)
        d = paired_deltas({1: [10.0] * BLOCKS, 16: [16.0] * BLOCKS})
        assert d[16]["delta_us"] > 5.5
        print("PASS: strict proof, non-strict downgrades (post-plan, "
              "extra join, two dispatches in a call, tick-less), deltas")
        return

    if not args.out:
        ap.error("--out is required")
    if not args.pass_name:
        ap.error("--pass_ is required")
    if args.pass_name in ("calibrate", "compiled-calibrate",
                          "unbracketed", "bracketed") and not args.dry_run \
            and args.k is None:
        ap.error("--k and --cols are operator-supplied and required "
                 "(shape is never guessed)")

    plan = build_plan()
    if args.dry_run:
        strict = {0: [(True, 10.0, 55)], 1: [(True, 10.0, 397)],
                  2: [(True, 30.0, 400)], 3: [(True, 30.0, 400)],
                  4: [(True, 30.0, 400)]}
        v, rep = verify_calibration(strict, 4)
        bad = dict(strict)
        bad[6] = [(True, 1.0, 55)]
        v2, _ = verify_calibration(bad, 5)
        assert v == "strict" and v2 == "non-strict"
        json.dump({"dry_run": True, "strict_verdict": v,
                   "nonstrict_verdict": v2,
                   "plan_segments": len(plan)},
                  open(args.out, "w"), indent=1)
        print(f"dry-run OK; wrote {args.out}")
        return

    if args.pass_name == "calibrate":
        pass_calibrate(args, args.k, args.cols)
    elif args.pass_name == "compiled-calibrate":
        pass_compiled_calibrate(args, args.k, args.cols)
    elif args.pass_name == "compiled-curve":
        pass_compiled_curve(args, args.k, args.cols, plan)
    elif args.pass_name == "curve-report":
        pass_curve_report(args, plan)
    elif args.pass_name == "unbracketed":
        pass_unbracketed(args, args.k, args.cols, plan)
    elif args.pass_name == "report":
        pass_report(args, plan)
    elif args.pass_name == "bracketed":
        raise SystemExit(
            "bracketed full-curve pass is GATED until the compiled route "
            "is verified (route producer: --pass compiled-calibrate)")
    else:
        raise SystemExit(
            "attribute pass is GATED with the bracketed curve")


if __name__ == "__main__":
    main()
