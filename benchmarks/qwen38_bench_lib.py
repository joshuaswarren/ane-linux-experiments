"""Shared helpers for the qwen38 bench scripts."""
import hashlib, json, statistics


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def ordered_records_hash(records):
    """Order-sensitive canonical hash over (pass, prompt_idx, input_ids, output_ids)."""
    canon = [
        [r["pass"], r["prompt_idx"], r["input_ids"], r["output_ids"]]
        for r in sorted(records, key=lambda r: (r["pass"], r["prompt_idx"]))
    ]
    return hashlib.sha256(json.dumps(canon, sort_keys=False).encode()).hexdigest()


def summarize(values):
    return {"median": round(statistics.median(values), 2),
            "mean": round(statistics.fmean(values), 2),
            "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
            "min": round(min(values), 2), "max": round(max(values), 2),
            "n": len(values)}
