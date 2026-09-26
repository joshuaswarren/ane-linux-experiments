import re
import sys

pat = re.compile(
    r"\s*(?P<task>[\w().:/-]+)-(?P<pid>\d+)\s+\[(?P<cpu>\d+)\]\s+"
    r"(?P<flags>.{5})\s+(?P<ts>\d+\.\d+):\s+(?P<ev>[\w_]+):\s+(?P<rest>.*)")
jobs = {}
order = []
for line in open(sys.argv[1]):
    m = pat.match(line)
    if not m:
        continue
    ev, ts, rest = m.group("ev"), float(m.group("ts")), m.group("rest")
    if ev in ("drm_sched_job_queue", "drm_sched_job_run", "drm_sched_job_done"):
        fid = re.search(r"fence=([0-9:]+)", rest)
        fid = fid.group(1) if fid else "?"
        j = jobs.setdefault(fid, {})
        j[ev.split("_")[-1]] = ts
        if ev == "drm_sched_job_queue":
            order.append(fid)
t0 = jobs[order[0]]["queue"]
prev_done = None
print("fence      queue_ms   q->run_us  run->done_ms  gap_from_prev_done_ms")
gaps = []
for fid in order:
    j = jobs[fid]
    if not all(k in j for k in ("queue", "run", "done")):
        continue
    gap = (j["queue"] - prev_done) * 1e3 if prev_done is not None else float("nan")
    gaps.append(gap)
    print(f"{fid:>9} {1e3*(j['queue']-t0):9.3f} {1e6*(j['run']-j['queue']):10.1f} "
          f"{1e3*(j['done']-j['run']):13.3f} {gap:20.3f}")
    prev_done = j["done"]
