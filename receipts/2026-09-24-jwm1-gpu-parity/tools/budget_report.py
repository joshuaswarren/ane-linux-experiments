#!/usr/bin/env python3
"""Per-token decode budget from the mlx-omarchy diagnostics wheel's
MLX_OMARCHY_GPU_PROFILE NDJSON (schema: k=d dispatch / s=submit / j=join /
end=summary; timestamps are CLOCK_MONOTONIC ns, same domain as the host
markers from prof_decode.py).

Emits the Main-directed budget table: GPU busy vs idle,
launches/submits per token x per-launch overhead, sync/wait,
roofline floor; per-kernel table; largest-bucket lever verdict.
"""
import argparse, json, sys
from collections import defaultdict

M1_BW_READ_GBS = 59.6
MODEL_WEIGHT_BYTES = 1312164224

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--markers", required=True)
    ap.add_argument("--wall-ms", type=float, required=True)
    ap.add_argument("--weights-bytes", type=int, default=MODEL_WEIGHT_BYTES)
    ap.add_argument("--bw-gbs", type=float, default=M1_BW_READ_GBS)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    markers = [json.loads(l) for l in open(a.markers) if l.strip()]
    dm = sorted((m for m in markers if m["p"].startswith("decode_")),
                key=lambda m: int(m["p"].split("_")[1]))
    if len(dm) < 2:
        print("need >=2 decode markers", file=sys.stderr); sys.exit(1)
    t_lo, t_hi = dm[0]["t"], dm[-1]["t"]
    n_tok = len(dm) - 1

    meta, dispatches, submits, joins, end = [], [], [], [], None
    for line in open(a.profile):
        r = json.loads(line)
        k = r.get("k")
        if k == "meta": meta = r
        elif k == "d": dispatches.append(r)
        elif k == "s": submits.append(r)
        elif k == "j": joins.append(r)
        elif k == "end": end = r

    # d-records use the GPU clock epoch; s-records use monotonic.
    # Classify decode dispatches by SUBMISSION: find the s-records whose
    # monotonic t falls inside the decode marker span, collect their
    # submission ids, and take the d-records with those ids.
    decode_sub_ids = set()
    for s in submits:
        tt = s.get("t", 0)
        # a submit touching the decode window: its wall slot intersects
        # [t_lo - margin, t_hi + margin]
        if tt >= t_lo - 5_000_000_000 and tt <= t_hi + 2_000_000_000:
            decode_sub_ids.add(s.get("s"))
    # fall back: if classification failed (0 or all), use s from 2..(2+n_tok-1)
    if not decode_sub_ids or len(decode_sub_ids) == len(submits):
        decode_sub_ids = set(range(2, 2 + n_tok + 1))
    win = [d for d in dispatches if d.get("s") in decode_sub_ids]
    n_disp = len(win)
    kernel_n = defaultdict(int); kernel_us = defaultdict(int); kernel_bar = defaultdict(int)
    spans = []
    for d in win:
        dur = int(d["t1"]) - int(d["t0"])
        name = d.get("p", f"op{d.get('op')}")
        kernel_n[name] += 1
        kernel_us[name] += dur
        kernel_bar[name] += int(d.get("bar", 0))
        spans.append((int(d["t0"]), int(d["t1"])))
    spans.sort()
    busy = 0; cs = ce = None
    for s0, s1 in spans:
        if cs is None: cs, ce = s0, s1
        elif s0 <= ce: ce = max(ce, s1)
        else: busy += ce - cs; cs, ce = s0, s1
    if cs is not None: busy += ce - cs
    span_ns = (t_hi - t_lo)
    idle = span_ns - busy

    n_sub = len([s for s in submits if t_lo <= s.get("t", 0) <= t_hi])
    sub_dur_us = sum(int(s.get("dur", 0)) for s in submits) / max(1, n_sub) / 1000.0
    join_wait_us = sum(int(j.get("wait", 0)) for j in joins) / max(1, n_tok) / 1000.0

    wall = a.wall_ms * 1000.0  # us
    roof_ms = (a.weights_bytes / 1e9) / a.bw_gbs * 1000.0
    profiled_wall_ms = span_ns / 1e6
    inflation = profiled_wall_ms / a.wall_ms

    rows = sorted(kernel_us.items(), key=lambda kv: -kv[1])
    L = []
    w = L.append
    w(f"# Per-token decode budget — jwm1 installed path (diag wheel @ f9d7bb21d)")
    w(f"")
    w(f"meta.device: {meta.get('device')}; records: {len(dispatches)} dispatches / {len(submits)} submits / {len(joins)} joins"
      + (f"; end.dispatches={end['dispatches']} end.submissions={end['submissions']} end.joins={end['joins']} end.barriers={end['barriers']} skipped={end['barriers_skipped']}" if end else ""))
    w(f"decode window: {n_tok} tokens x measured wall {a.wall_ms} ms/tok (unprofiled, receipted)")
    w(f"profiled wall/tok: {profiled_wall_ms:.2f} ms (diag inflation x{inflation:.2f})")
    w(f"")
    w(f"| bucket | profiled | real (/x{inflation:.2f}) | share of real wall |")
    w(f"| --- | ---: | ---: | ---: |")
    real = lambda us: us / inflation / 1000.0
    w(f"| GPU busy (merged spans) | {busy/1e3:.2f} ms | {real(busy/1e3):.2f} ms | {real(busy/1e3)/a.wall_ms*100:.0f}% |")
    w(f"| GPU idle (in-window gaps) | {idle/1e3:.2f} ms | {real(idle/1e3):.2f} ms | {real(idle/1e3)/a.wall_ms*100:.0f}% |")
    w(f"| host submit (avg x n) | {sub_dur_us*n_sub/max(1,n_tok)/1e3:.2f} ms over {n_sub/max(1,n_tok):.2f} subs/tok | {real(sub_dur_us*n_sub/max(1,n_tok)/1e3):.2f} ms | {real(sub_dur_us*n_sub/max(1,n_tok)/1e3)/a.wall_ms*100:.0f}% |")
    w(f"| join/sync wait | {join_wait_us/1e3:.3f} ms/tok | {real(join_wait_us/1e3):.3f} ms | {real(join_wait_us/1e3)/a.wall_ms*100:.1f}% |")
    w(f"")
    w(f"dispatches/token: {n_disp/n_tok:.1f}; barriers/dispatch: {sum(kernel_bar.values())/max(1,n_disp):.1f}; per-launch GPU-dispatch cost (busy/n): {busy/max(1,n_disp)/1e3:.1f} us")
    w(f"roofline floor (q4 weights {a.weights_bytes/1e9:.2f} GB @ {a.bw_gbs} GB/s): {roof_ms:.2f} ms/tok — measured wall {a.wall_ms} ms = {roof_ms/a.wall_ms*100:.0f}% of roofline")
    w(f"")
    w(f"## Per-kernel table (profiled; top 20 by us/tok)")
    w(f"")
    w(f"| kernel | n/tok | us/tok (prof) | us/tok (real) | share of busy | barriers/tok |")
    w(f"| --- | ---: | ---: | ---: | ---: | ---: |")
    for name, us in rows[:20]:
        w(f"| {name} | {kernel_n[name]/n_tok:.1f} | {us/n_tok:.1f} | {real(us/n_tok*1000):.1f} | {us/max(1,busy)*100:.1f}% | {kernel_bar[name]/n_tok:.1f} |")
    w(f"")
    total_us = sum(us for _, us in rows)
    top_name, top_us = rows[0]
    w(f"## Largest bucket -> lever")
    w(f"")
    if real(busy/1e3) > real(idle/1e3):
        w(f"GPU busy dominates ({real(busy/1e3):.2f} vs idle {real(idle/1e3):.2f} ms/tok real). "
          f"Top kernel family: **{top_name}** ({top_us/n_tok:.0f} us/tok profiled, {kernel_n[top_name]/n_tok:.1f} launches/tok). "
          f"If the q4-GEMV family runs near the pattern ceiling, the lever is NOT a microkernel rewrite; "
          f"it is fewer bytes (vocab prune / weight layout) or fewer launches (norm-into-GEMV prologue folds).")
    else:
        w(f"GPU idle dominates ({real(idle/1e3):.2f} ms/tok real vs busy {real(busy/1e3):.2f}). "
          f"Lever: submission batching / command-buffer coalescing / compiled-graph so the {n_sub/max(1,n_tok):.2f} submits/token stop draining the pipeline.")
    w(f"")
    sum_ms = real(busy/1e3) + real(idle/1e3)
    w(f"Sum check: busy+idle = {sum_ms:.2f} ms vs measured wall {a.wall_ms} ms — the residual {a.wall_ms - sum_ms:.2f} ms is host-side record/submit/python time hidden between the GPU windows.")

    open(a.out, "w").write("\n".join(L) + "\n")
    print("\n".join(L[:16]))

if __name__ == "__main__":
    main()
