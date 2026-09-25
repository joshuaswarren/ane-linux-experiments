#!/usr/bin/env python3
"""One-line summary of a qwen38-mlx-bench contract JSON."""
import json, statistics, sys
for path in sys.argv[1:]:
    j = json.load(open(path))
    dec = j["decode_tok_rate"]
    e2e = [r["ttft_s"] + r["decode_s"] for r in j["per_prompt"]]
    pp = j.get("pure_prefill") or {}
    print(
        f"{j['meta'].get('label','?'):28s} decode={dec['median']:.2f} tok/s "
        f"({1000.0/dec['median']:.2f} ms/tok) prefill={pp.get('pure_prefill_tok_rate','?')} "
        f"ttft={j['ttft_tok_rate']['median']:.2f} e2e_med={statistics.median(e2e):.4f}s "
        f"digest={j['ordered_records_sha256'][:8]} n={len(j['per_prompt'])} "
        f"wheel={j['meta'].get('mlx_dist_version','?')}"
    )
