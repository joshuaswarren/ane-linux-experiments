#!/usr/bin/env python3
"""qmm weight-fetch sensitivity micro v2.3 (protocol: receipts/
2026-09-19-gated-barriers-default-t6001-test-host.md).

STATUS PER MAIN REVIEW: only --pass calibrate is approved to run (small,
after Decoder's verified release). It establishes the ACTUAL profiler
event lifecycle (joins per eval, flush placement) and same-shape routing
on the device. The full W-curve (--pass bracketed/--pass attribute)
remains gated until the parser is validated against that diagnostic.
No performance conclusions are drawn from calibration.

Lifecycle facts from source (encoder.h:214, encoder.cpp:157-172,603,
eval.cpp:135, gpu_profiler.h flush_slot):
  - synchronize() defaults to reason "explicit"; ring-slot-reuse joins
    and mx.sync joins are therefore NOT distinguishable by reason.
  - d events flush only at joins or slot reuse; the destructor emits
    "end" WITHOUT flushing, so pending events are lost at exit.
  - mid-run reads race the C++ stdio buffer.
Hence: same-process layout assumptions are EMPIRICAL claims. The
calibration pass verifies the one property that must hold under any
lifecycle and reports the observed layout descriptively:

  STRICT layout (syncs placed warmup | c1 | c2 | c3):
    j_count == CALIBRATION_CALLS + 1, every d region r in
    1..CALIBRATION_CALLS holds EXACTLY one tick-ful dispatch, and NO
    dispatch exists in any region > CALIBRATION_CALLS (any post-final-
    sync event, or any extra join carrying one, rejects).
    Strict-pass proves one qmm call == one dispatch.
  NON-STRICT (anything else): a descriptive report is emitted for
    parser validation; nothing is attributed, no verdict is claimed.

Calibration uses the SAME (k, cols) shape as the plan with a distinct
weight buffer, so routing (kernel enum, n, gx) is identical by
construction; a different shape would route differently and prove
nothing about plan calls. --k/--cols are operator-supplied, never
guessed. Unbracketed wall pass is labeled plan_wall_s: it spans the
plan only (materialization and warmup excluded from the timer).
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


# ---------- planning / analysis (pure) ----------

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


# ---------- calibration stream verification (pure) ----------

def verify_calibration(d_by_region, j_count, reasons=None):
    """d_by_region: {region: [(has_ticks, dur_us, enum)]}. Flush
    convention (source + empirically proven on t6001-test-host, calib-v23.ndjson):
    the j record is emitted BEFORE flush_slot writes that join's d
    lines, so region r = the flush work of sync r:
      region 1 = warmup straggler (last warmup dispatch(es) whose slot
                 was not reused before the sync; tick-ful, count >= 0),
      regions 2..CALIBRATION_CALLS+1 = ONE calibration call each,
      any region beyond CALIBRATION_CALLS+1, or j_count !=
      CALIBRATION_CALLS + 1, is NON-STRICT.

    Returns (verdict, report). verdict "strict": each calibration
    region has exactly one tick-ful dispatch with a stable enum - one
    qmm call == one dispatch is PROVEN. verdict "non-strict": report
    only; no attribution, no perf claim."""
    expected_j = CALIBRATION_CALLS + 1
    report = {"j_count": j_count, "join_reasons": reasons or {},
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


# ---------- device path ----------

def force_sync(mx):
    """Flush-forcing call: mlx.core exposes `synchronize` on this build
    (verified on t6001-test-host diag wheel); older builds name it `sync`."""
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


def materialize(k, cols, max_w):
    import mlx.core as mx
    x = mx.random.normal((1, k)).astype(mx.float16)
    mx.eval(x)
    weights = []
    for _ in range(max_w):
        w = mx.random.normal((cols, k)).astype(mx.float16)
        wq, scales, biases = mx.quantize(w, group_size=64, bits=4)
        mx.eval(wq), mx.eval(scales), mx.eval(biases)
        weights.append((wq, scales, biases))
    cw = mx.random.normal((cols, k)).astype(mx.float16)  # SAME shape,
    calib = mx.quantize(cw, group_size=64, bits=4)       # distinct buffer
    mx.eval(calib[0]), mx.eval(calib[1]), mx.eval(calib[2])
    return x, weights, calib


def qmm(x, wq, scales, biases):
    import mlx.core as mx
    return mx.quantized_matmul(x, wq, scales, biases, transpose=True,
                               group_size=64, bits=4)


def parse_stream(profile_path):
    """File-ordered (region, has_ticks, dur_us, enum, reason@join)."""
    region, j_count = 0, 0
    d_by_region, reasons, meta = {}, {}, None
    for line in open(profile_path):
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
            reasons[r.get("reason")] = reasons.get(r.get("reason"), 0) + 1
        elif k == "d":
            has = "t0" in r
            d_by_region.setdefault(region, []).append(
                (has,
                 (r["t1"] - r["t0"]) * meta["period_ns"] / 1e3 if has
                 else None,
                 r["e"]))
    if meta is None:
        raise SystemExit(f"{profile_path}: no meta record")
    return d_by_region, j_count, reasons, meta


# ---------- passes ----------

def pass_calibrate(args, k, cols):
    """SMALL approved diagnostic: materialize + warmup + 3 same-shape
    calibration calls, sync after each. Verifies strict layout or emits
    the descriptive report. No performance conclusions."""
    import mlx.core as mx
    require_sync(mx)
    x, weights, calib = materialize(k, cols, 1, )
    for i in range(WARMUP_STEPS):
        mx.eval(qmm(x, *weights[0]))
    force_sync(mx)
    for _ in range(CALIBRATION_CALLS):
        mx.eval(qmm(x, *calib))
        force_sync(mx)
    d_by_region, j_count, reasons, meta = parse_stream(args.profile)
    verdict, report = verify_calibration(d_by_region, j_count, reasons)
    ident = {"pass": "calibrate", "k": k, "cols": cols,
             "warmup": WARMUP_STEPS, "calibration_calls": CALIBRATION_CALLS,
             "shape_note": "calibration uses the SAME (k, cols) as the "
                           "plan with a distinct weight buffer",
             "mlx_version": getattr(mx, "__version__", "unknown")
             if hasattr(mx, "__version__") else "unknown",
             "device": meta.get("device"), "period_ns": meta.get("period_ns"),
             "valid_bits": meta.get("valid_bits"),
             "profile_path": args.profile,
             "conditions": {
                 "label": meta.get("label"),
                 "env_profile": os.environ.get("MLX_OMARCHY_GPU_PROFILE"),
                 "env_label": os.environ.get("MLX_OMARCHY_GPU_PROFILE_LABEL"),
                 "vk_driver_files": os.environ.get("VK_DRIVER_FILES"),
                 "vk_icd_filenames": os.environ.get("VK_ICD_FILENAMES"),
                 "gated_barriers": os.environ.get(
                     "MLX_OMARCHY_GATED_BARRIERS"),
             }}
    for var in ("VK_DRIVER_FILES", "VK_ICD_FILENAMES"):
        v = os.environ.get(var)
        if v and os.path.exists(v.split(":")[0]):
            icd = v.split(":")[0]
            ident["conditions"][f"{var}_sha256"] = hashlib.sha256(
                open(icd, "rb").read()).hexdigest()
    try:
        from importlib import metadata as _md
        ident["wheel_version"] = _md.version("mlx_omarchy")
    except Exception:
        ident["wheel_version"] = "unknown"
    try:
        import mlx
        lib = os.path.join(os.path.dirname(mlx.__file__), "lib",
                           "libmlx.so")
        if os.path.exists(lib):
            ident["libmlx_sha256"] = hashlib.sha256(
                open(lib, "rb").read()).hexdigest()
        ident["mlx_version"] = getattr(mlx, "__version__",
                                       ident["mlx_version"])
    except ImportError:
        pass
    out = {"identity": ident, "calibration": report,
           "raw_profile": args.profile,
           "note": ("lifecycle diagnostic ONLY: establishes event "
                    "layout and routing; durations here are bracketed "
                    "instrument values and support NO performance "
                    "conclusion")}
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"wrote {args.out} - verdict: {report['verdict']}")


def pass_compiled_calibrate(args, k, cols):
    """Same verification as --pass calibrate, but the dispatches come
    from the ACTUAL decode route: an mx.compile'd graph whose tape
    carries a DecodeFusion group (fused_chain.cpp DecodeFusion: 3
    QuantizedMatmul(Affine,4,64,transpose) nodes sharing one x = single
    row, each with a single-consumer Add epilogue) so the fused-chain
    builder records ONE QmmVecQ4Multi dispatch per call - the same
    kernel enum the decode profile shows (412). No new kernel; the
    graph mirrors the decode layer's matmul+add structure."""
    import mlx.core as mx
    require_sync(mx)
    x = mx.random.normal((1, k)).astype(mx.float16)
    mx.eval(x)
    weights, adds = [], []
    for _ in range(3):  # kQmmVecMultiWeights = 3 (compute.h:36)
        w = mx.random.normal((cols, k)).astype(mx.float16)
        wq, scales, biases = mx.quantize(w, group_size=64, bits=4)
        mx.eval(wq), mx.eval(scales), mx.eval(biases)
        weights.append((wq, scales, biases))
        adds.append(mx.random.normal((1, cols)).astype(mx.float16))
    mx.eval(adds[0]), mx.eval(adds[1]), mx.eval(adds[2])

    def group(x):
        outs = [mx.quantized_matmul(x, *wq, transpose=True, group_size=64,
                                    bits=4) for wq in weights]
        return [o + a for o, a in zip(outs, adds)]

    fn = mx.compile(group)
    for i in range(WARMUP_STEPS):
        mx.eval(fn(x))
    mx.synchronize() if hasattr(mx, "synchronize") else mx.sync()
    for _ in range(CALIBRATION_CALLS):
        mx.eval(fn(x))
        (mx.synchronize() if hasattr(mx, "synchronize") else mx.sync())
    d_by_region, j_count, reasons, meta = parse_stream(args.profile)
    verdict, report = verify_calibration(d_by_region, j_count, reasons)
    ident = {"pass": "compiled-calibrate", "k": k, "cols": cols,
             "group_members": 3, "warmup": WARMUP_STEPS,
             "calibration_calls": CALIBRATION_CALLS,
             "route_note": "compiled tape -> DecodeFusion -> "
                           "QmmVecQ4Multi dispatch (actual call site)",
             "mlx_version": getattr(mx, "__version__", "unknown")
             if hasattr(mx, "__version__") else "unknown",
             "device": meta.get("device"), "period_ns": meta.get("period_ns"),
             "valid_bits": meta.get("valid_bits"),
             "profile_path": args.profile}
    try:
        import mlx
        lib = os.path.join(os.path.dirname(mlx.__file__ or ""), "lib",
                           "libmlx.so")
        if os.path.exists(lib):
            ident["libmlx_sha256"] = hashlib.sha256(
                open(lib, "rb").read()).hexdigest()
        ident["mlx_version"] = getattr(mlx, "__version__",
                                       ident["mlx_version"])
    except (ImportError, TypeError):
        pass
    out = {"identity": ident, "calibration": report,
           "raw_profile": args.profile,
           "note": ("route diagnostic ONLY: verifies the compiled graph "
                    "dispatches the fused multi-weight kernel; durations "
                    "support NO performance conclusion")}
    json.dump(out, open(args.out, "w"), indent=1)
    strict = report.get("verdict", "").startswith("strict")
    enums = report.get("region_enums", {})
    route = (strict and all(enums.get(str(r)) == [412]
                            for r in (2, 3, 4)))
    print(f"wrote {args.out} - verdict: {report['verdict']} | "
          f"route={'FUSED MULTI 412 CONFIRMED' if route else 'see report'}")



    import mlx.core as mx
    require_sync(mx)
    x, weights, calib = materialize(k, cols, max(s["w"] for s in plan))
    for i in range(WARMUP_STEPS):
        mx.eval(qmm(x, *weights[0]))
    force_sync(mx)
    wall, total_t0 = {}, time.perf_counter()  # plan only; warmup excluded
    for s in plan:
        t0 = time.perf_counter()
        for i in range(s["steps"]):
            mx.eval(qmm(x, *weights[i % s["w"]]))
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
           "plan_wall_s_note": ("spans plan segments only; "
                                "materialization and warmup excluded; "
                                "includes python + eval-sync round trip"),
           "wall_avg_us_per_block": {str(w): v
                                     for w, v in wall_blocks.items()},
           "wall_avg_paired_delta_vs_W1": paired_deltas(wall_blocks)}
    json.dump(out, open(args.out, "w"), indent=1)
    print("wrote", args.out)


def pass_report(args, plan):
    """Offline: verify a PRESERVED calibration stream and emit the
    report. Flush convention from source (gpu_profiler.h on_join):
    the j record is emitted BEFORE flush_slot writes that join's d
    lines, so the d lines following the r-th j line are the flush work
    of sync r. Region 1 therefore holds the warmup straggler (last
    warmup dispatch whose slot was not reused before the sync);
    regions 2..(CALIBRATION_CALLS+1) must hold exactly one tick-ful
    dispatch each with one stable enum (the calibration calls); ANY
    dispatch after the last join's flush work rejects."""
    ident = {}
    if args.plan_meta and os.path.exists(args.plan_meta):
        ident.update(json.load(open(args.plan_meta)))
    else:
        ident["run_identity"] = ("device-side identity block was not "
                                 "written (v2.3 identity crash after "
                                 "syncs); library sha + wheel version "
                                 "recorded in receipt from prior "
                                 "provenance checks")
    seq, meta = [], None
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
            seq.append(("j", r.get("reason")))
        elif k == "d":
            has = "t0" in r
            seq.append(("d", has,
                        (r["t1"] - r["t0"]) * meta["period_ns"] / 1e3
                        if has else None, r["e"]))
    if meta is None:
        raise SystemExit(f"{args.profile}: no meta record")
    # group d lines by their preceding j line (0 = before first j)
    regions, cur = {}, 0
    for item in seq:
        if item[0] == "j":
            cur += 1
        else:
            regions.setdefault(cur, []).append(item[1:])
    report = {"j_count": cur,
              "reasons": sorted({i[1] for i in seq if i[0] == "j"}),
              "region_counts": {str(r): len(v) for r, v
                                in sorted(regions.items())},
              "region_enums": {str(r): sorted({e for _, _, e in
                                               regions.get(r, [])})
                               for r in sorted(regions)}}
    # strict verdict requires: 4 joins; regions 2,3,4 exactly one
    # tick-ful dispatch each, one enum across them; region 1 = warmup
    # stragglers (>=0, tick-ful); no region beyond 4 with events.
    strict_ok = (cur == CALIBRATION_CALLS + 1
                 and all(len(regions.get(r, [])) == 1 for r in (2, 3, 4))
                 and all(all(h for h, *_ in regions.get(r, []))
                         for r in (2, 3, 4))
                 and len({e for r in (2, 3, 4)
                          for _, _, e in regions[r]}) == 1
                 and all(h for h, *_ in regions.get(1, []))
                 and not any(regions.get(r) for r in regions if r > 4))
    calib_enum = (regions[2][0][2] if strict_ok else None)
    ident["signature_check"] = {
        "calibrated_enum": calib_enum,
        "decode_kernel": DECODE_SIGNATURE["kernel"],
        "decode_route": "fused multi-weight (QmmVecQ4MultiSubgroupF16)",
        "verdict": ("decode-shape kernel" if
                    calib_enum == DECODE_SIGNATURE["kernel"] else
                    "PROXY ROUTE - single-row python route selects a "
                    "different kernel than the decode fused route; full "
                    "curve through this route would measure the wrong "
                    "kernel")}
    out = {"identity": {**ident, "profile_path": args.profile,
                        "device": meta.get("device"),
                        "period_ns": meta.get("period_ns"),
                        "valid_bits": meta.get("valid_bits"),
                        "label": meta.get("label")},
           "calibration": {"verdict": "strict (under source flush "
                                       "convention: j emitted before its "
                                       "flush work)" if strict_ok
                                       else "NON-STRICT",
                           "region_counts": report["region_counts"],
                           "region_enums": report["region_enums"],
                           "join_reasons": report["reasons"],
                           "j_count": cur},
           "note": ("lifecycle diagnostic: establishes event layout and "
                    "routing only; durations are bracketed instrument "
                    "values and support NO performance conclusion")}
    json.dump(out, open(args.out, "w"), indent=1)
    print("wrote", args.out, "- verdict:", out["calibration"]["verdict"],
          "|", ident["signature_check"]["verdict"])


# ---------- entry ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=None)
    ap.add_argument("--cols", type=int, default=None)
    ap.add_argument("--pass_", choices=["calibrate", "compiled-calibrate",
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
        seg = build_plan()
        assert all(s["steps"] % s["w"] == 0 and s["steps"] >= MIN_STEPS
                   for s in seg)
        strict = {0: [(True, 10.0, 55), (False, None, 55)],
                  1: [(True, 10.0, 397)],
                  2: [(True, 30.0, 400)], 3: [(True, 30.0, 400)],
                  4: [(True, 30.0, 400)]}
        v, rep = verify_calibration(strict, 4)
        assert v == "strict" and rep["calibrated_enum"] == 400
        for bad, jc, frag in (
                ({**strict, 5: [(True, 1.0, 55)]}, 5, "post-plan event"),
                (strict, 6, "extra join"),
                ({0: [], 1: [(True, 10.0, 397)], 2: [(True, 30.0, 400),
                                                    (True, 30.0, 400)],
                  3: [(True, 30.0, 400)], 4: [(True, 30.0, 400)]}, 4,
                 "two dispatches in a call"),
                ({0: [], 1: [], 2: [(False, None, 400)], 3: [(True, 30.0,
                                                             400)],
                  4: [(True, 30.0, 400)]}, 4, "tick-less calibration")):
            v, rep = verify_calibration(bad, jc)
            assert v == "non-strict", (frag, rep)
        d = paired_deltas({1: [10.0] * BLOCKS, 16: [16.0] * BLOCKS})
        assert d[16]["delta_us"] > 5.5
        print("PASS: strict layout proof, non-strict downgrade "
              "(post-plan event, extra join, extra dispatch per call, "
              "tick-less), deltas")
        return

    if not args.out:
        ap.error("--out is required")
    if not args.pass_name:
        ap.error("--pass_ {calibrate,unbracketed,bracketed,attribute} is "
                 "required")
    if args.pass_name in ("calibrate", "compiled-calibrate", "unbracketed",
                          "bracketed") and not args.dry_run and \
            args.k is None:
        ap.error("--k and --cols are operator-supplied and required "
                 "(shape is never guessed)")

    plan = build_plan()
    if args.dry_run:
        strict = {0: [(True, 10.0, 55)], 1: [(True, 30.0, 400)],
                  2: [(True, 30.0, 400)], 3: [(True, 30.0, 400)]}
        v, rep = verify_calibration(strict, 4)
        nonstrict = dict(strict)
        nonstrict[7] = [(True, 1.0, 55)]
        v2, rep2 = verify_calibration(nonstrict, 5)
        assert v == "strict" and v2 == "non-strict"
        out = {"dry_run": True, "strict_case": rep,
               "nonstrict_case_verdict": rep2["verdict"],
               "plan_segments": len(plan)}
        json.dump(out, open(args.out, "w"), indent=1)
        print(f"dry-run OK: verification path green; wrote {args.out}")
        return

    if args.pass_name == "calibrate":
        pass_calibrate(args, args.k, args.cols)
    elif args.pass_name == "compiled-calibrate":
        pass_compiled_calibrate(args, args.k, args.cols)
    elif args.pass_name == "unbracketed":
        pass_unbracketed(args, args.k, args.cols, plan)
    elif args.pass_name == "bracketed":
        raise SystemExit(
            "bracketed full-curve pass is GATED: run --pass calibrate "
            "first and validate the parser against the observed event "
            "lifecycle (Main directive; no curve until then)")
    elif args.pass_name == "report":
        pass_report(args, plan)
    else:
        raise SystemExit(
            "attribute pass is GATED with the bracketed curve until the "
            "calibration diagnostic validates the parser")


if __name__ == "__main__":
    main()
