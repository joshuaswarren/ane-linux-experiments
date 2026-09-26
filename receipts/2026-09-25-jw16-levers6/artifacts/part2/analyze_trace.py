#!/usr/bin/env python3
"""Exec-vs-wait split per Parakeet stage from an ftrace capture.

Parses PARAKEET_BEGIN/END markers + drm_sched_job_queue/run/done and
dma_fence_signaled events (mono clock). For each stage window: GPU-busy =
union of [run, done] intervals of jobs whose run fell inside the window
(clipped to it); host-wait = wall - busy. Also reports queue->run submit
latency and per-job run->done stats.

Usage: analyze_trace.py trace.txt [out.json]
"""
import json
import re
import statistics
import sys

LINE = re.compile(
    r"^\s*(?P<comm>.+?)-(?P<pid>\d+)\s+\[(?P<cpu>\d+)\]\s+(?P<flags>\S+)"
    r"\s+(?P<ts>\d+\.\d+):\s+(?P<rest>.*)$")
FENCE = re.compile(r"fence=(?P<c>\d+):(?P<s>\d+)")
SIG = re.compile(
    r"dma_fence_signaled: driver=(?P<driver>\S+) timeline=(?P<tl>\S+) "
    r"context=(?P<c>\d+) seqno=(?P<s>\d+)")


def main() -> int:
    path = sys.argv[1]
    windows = []          # (name, t0, t1)
    jobs = {}             # (ctx, seq) -> dict(queue, run, done)
    order = []
    drivers = {}
    with open(path, errors="replace") as fh:
        for line in fh:
            m = LINE.match(line)
            if not m:
                continue
            ts = float(m.group("ts"))
            rest = m.group("rest")
            if rest.startswith("PARAKEET_BEGIN "):
                windows.append([rest.split(" ", 1)[1], ts, None])
                continue
            if rest.startswith("PARAKEET_END "):
                for w in reversed(windows):
                    if w[0] == rest.split(" ", 1)[1] and w[2] is None:
                        w[2] = ts
                        break
                continue
            if ": " not in rest:
                continue
            ev, body = rest.split(": ", 1)
            if ev == "tracing_mark_write":
                if body.startswith("PARAKEET_BEGIN "):
                    windows.append([body.split(" ", 1)[1], ts, None])
                elif body.startswith("PARAKEET_END "):
                    for w in reversed(windows):
                        if w[0] == body.split(" ", 1)[1] and w[2] is None:
                            w[2] = ts
                            break
                continue
            if ev == "drm_sched_job_queue":
                f = FENCE.search(body)
                if f:
                    key = (int(f.group("c")), int(f.group("s")))
                    jobs.setdefault(key, {})["queue"] = ts
            elif ev == "drm_sched_job_run":
                f = FENCE.search(body)
                if f:
                    key = (int(f.group("c")), int(f.group("s")))
                    jobs.setdefault(key, {})["run"] = ts
                    order.append(key)
            elif ev == "drm_sched_job_done":
                f = FENCE.search(body)
                if f:
                    key = (int(f.group("c")), int(f.group("s")))
                    jobs.setdefault(key, {})["done"] = ts
            elif ev == "dma_fence_signaled":
                s = SIG.match(rest)
                if s:
                    drivers.setdefault(s.group("driver"), 0)
                    drivers[s.group("driver")] += 1

    print(f"jobs seen: {len(jobs)}, fence signaled by driver:",
          dict(drivers))
    rows = []
    for name, t0, t1 in windows:
        if t1 is None:
            print(f"UNPAIRED window {name}")
            continue
        wall = t1 - t0
        ivals = []
        rd = []
        qsub = []
        n = 0
        for key, j in jobs.items():
            run = j.get("run")
            done = j.get("done")
            if run is None or not (t0 <= run <= t1):
                continue
            n += 1
            end = done if done is not None else run
            ivals.append((max(run, t0), min(end, t1)))
            if done is not None:
                rd.append(done - run)
            if j.get("queue") is not None:
                qsub.append(run - j["queue"])
        # union of intervals
        ivals.sort()
        busy = 0.0
        cs, ce = None, None
        for s, e in ivals:
            if cs is None:
                cs, ce = s, e
            elif s <= ce:
                ce = max(ce, e)
            else:
                busy += ce - cs
                cs, ce = s, e
        if cs is not None:
            busy += ce - cs
        wait = wall - busy
        rows.append({
            "stage": name, "wall_ms": wall * 1e3, "busy_ms": busy * 1e3,
            "wait_ms": wait * 1e3, "jobs": n,
            "busy_pct": round(100 * busy / wall, 1) if wall else None,
            "run_done_p50_ms": round(statistics.median(rd) * 1e3, 4) if rd else None,
            "run_done_max_ms": round(max(rd) * 1e3, 3) if rd else None,
            "queue_run_p50_ms": round(statistics.median(qsub) * 1e3, 4) if qsub else None,
        })
    hdr = (f"{'stage':<14}{'wall_ms':>10}{'busy_ms':>10}{'wait_ms':>10}"
           f"{'busy%':>8}{'jobs':>7}{'rd_p50':>10}{'rd_max':>9}{'q_run_p50':>11}")
    print(hdr)
    for r in rows:
        print(f"{r['stage']:<14}{r['wall_ms']:>10.1f}{r['busy_ms']:>10.1f}"
              f"{r['wait_ms']:>10.1f}{r['busy_pct']:>8}{r['jobs']:>7}"
              f"{str(r['run_done_p50_ms']):>10}{str(r['run_done_max_ms']):>9}"
              f"{str(r['queue_run_p50_ms']):>11}")
    if len(sys.argv) > 2:
        json.dump({"rows": rows, "jobs_total": len(jobs)},
                  open(sys.argv[2], "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
