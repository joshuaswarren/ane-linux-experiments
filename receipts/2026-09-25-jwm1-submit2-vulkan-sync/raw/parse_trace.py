import json
import re
import sys

pat = re.compile(
    r"\s*(?P<task>[\w().:/-]+)-(?P<pid>\d+)\s+\[(?P<cpu>\d+)\]\s+"
    r"(?P<flags>.{5})\s+(?P<ts>\d+\.\d+):\s+(?P<ev>[\w_]+):\s+(?P<rest>.*)")


def parse(path):
    jobs = {}  # id -> dict
    events = []
    for line in open(path):
        m = pat.match(line)
        if not m:
            continue
        ts = float(m.group("ts"))
        ev = m.group("ev")
        rest = m.group("rest")
        if ev == "drm_sched_job_queue":
            mid = re.search(r"job=(\S+)", rest)
            jid = mid.group(1) if mid else rest[:40]
            jobs.setdefault(jid, {})["queue"] = ts
            events.append(("queue", ts, jid, rest))
        elif ev == "drm_sched_job_run":
            mid = re.search(r"job=(\S+)", rest)
            jid = mid.group(1) if mid else rest[:40]
            jobs.setdefault(jid, {})["run"] = ts
            events.append(("run", ts, jid, rest))
        elif ev == "drm_sched_job_done":
            mid = re.search(r"job=(\S+)", rest)
            jid = mid.group(1) if mid else rest[:40]
            jobs.setdefault(jid, {})["done"] = ts
            events.append(("done", ts, jid, rest))
        else:
            events.append((ev, ts, "", rest))
    return jobs, events


def main():
    path = sys.argv[1]
    jobs, events = parse(path)
    t0 = events[0][1] if events else 0
    print(f"{len(jobs)} sched jobs")
    rows = []
    for jid, j in sorted(jobs.items(), key=lambda kv: kv[1].get("queue", 0)):
        if all(k in j for k in ("queue", "run", "done")):
            rows.append((jid, (j["queue"] - t0) * 1e3, (j["run"] - j["queue"]) * 1e3,
                         (j["done"] - j["run"]) * 1e3))
    print("job | queue_ms | q2run_ms | run2done_ms")
    for jid, q, q2r, r2d in rows:
        print(f"{jid:>18} {q:10.3f} {q2r:9.3f} {r2d:9.3f}")
    if len(rows) > 1:
        gaps = []
        for a, b in zip(rows, rows[1:]):
            gaps.append(b[1] - (a[1] + a[2] + a[3]))
        print("host gap between job done and next queue (ms):")
        print(" ".join(f"{g:.3f}" for g in gaps))
    # dma_fence wait samples
    waits = []
    pending = {}
    for ev, ts, jid, rest in events:
        if ev == "dma_fence_wait_start":
            pending[rest[:60]] = ts
        elif ev == "dma_fence_wait_end":
            k = rest[:60]
            if k in pending:
                waits.append((ts - pending[k]) * 1e3)
    if waits:
        print("dma_fence wait durations ms:", " ".join(f"{w:.3f}" for w in waits))
    json.dump({"jobs": rows}, open("/tmp/parsed_jobs.json", "w"))


main()
