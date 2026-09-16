#!/usr/bin/env python3
"""TermA per-submission host/GPU phase split from an omarchy GPU profile.

Groups d events by submission id, pairs with s/q/j events, prints the last
few submissions (decode tokens come in 2 submissions each):
  per sub: dispatches, host_record_us, gpu_busy_us (inflated), gpu_span_us
  per sub: submit_us, close_us, queue_us
  per join: wait_us, inval_us, reason
Wrap-safe tick deltas (timestamps wrap at 2^valid_bits).
"""
import json, sys, collections

def tick_delta(a, b, valid_bits):
    d = b - a
    if d < 0 and valid_bits:
        d += 1 << valid_bits
    return d

def main():
    path = sys.argv[1]
    nsubs = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    ev = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("{"):
                ev.append(json.loads(line))
    meta = next(e for e in ev if e["k"] == "meta")
    period = meta.get("period_ns", 1.0)
    vb = meta.get("valid_bits", 0)
    subs = collections.defaultdict(list)
    for e in ev:
        if e["k"] == "d":
            subs[e["s"]].append(e)
    sevents = {e["s"]: e for e in ev if e["k"] == "s"}
    qevents = {e["s"]: e for e in ev if e["k"] == "q"}
    joins = [e for e in ev if e["k"] == "j"]
    end = next((e for e in ev if e["k"] == "end"), None)
    print(f"meta: period_ns={period} valid_bits={vb}")
    if end:
        print(f"end: dispatches={end['dispatches']} submissions={end['submissions']} "
              f"joins={end['joins']} barriers={end['barriers']} "
              f"skipped={end['barriers_skipped']} dropped={end['dropped']}")
    ids = sorted(subs)[-nsubs:]
    for sid in ids:
        ds = subs[sid]
        rec = sum(d.get("h", 0) for d in ds) / 1e3
        witht = [d for d in ds if "t0" in d]
        busy = span = 0.0
        if witht:
            busy = sum(tick_delta(d["t0"], d["t1"], vb) for d in witht) * period / 1e3
            t0 = min(d["t0"] for d in witht)
            t1 = max(d["t1"] for d in witht)
            span = tick_delta(t0, t1, vb) * period / 1e3
        s = sevents.get(sid, {})
        q = qevents.get(sid, {})
        submit_us = s.get("dur", 0) / 1e3
        close_us = q.get("close", 0) / 1e3
        queue_us = (q.get("queue_t1", 0) - q.get("queue_t0", 0)) / 1e3
        print(f"\n== sub {sid} == dispatches={len(ds)} host_record_us={rec:.1f} "
              f"gpu_busy_us={busy:.1f} gpu_span_us={span:.1f}")
        print(f"    submit_us={submit_us:.1f} close_us={close_us:.1f} queue_us={queue_us:.1f}")
        kernels = collections.Counter(d["e"] for d in ds)
        print(f"    kernels={dict(kernels)}")
    print("\n== joins ==")
    for j in joins[-6:]:
        print(f"  sub={j['s']} wait_us={j['wait']/1e3:.1f} inval_us={j['inval']/1e3:.1f} "
              f"reason={j.get('reason')}")

if __name__ == "__main__":
    main()
