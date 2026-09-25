import json, os, resource, runpy, statistics, sys

bench_path = sys.argv[4]
out = sys.argv[1]
model = sys.argv[2]
corpus = sys.argv[3]
sys.path.insert(0, os.path.dirname(bench_path))
sys.argv = ["qwen38-mlx-bench.py",
            "--model", model,
            "--prompts", corpus,
            "--limit", "10", "--new-tokens", "32",
            "--prefill-tokens", "512",
            "--warmup", "3", "--passes", "10",
            "--label", "linux-reference-b4757ac",
            "--out", out]
runpy.run_path(bench_path, run_name="__main__")
peak_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
res = json.load(open(out))
recs = res["per_prompt"]
e2e = [round(r["ttft_s"] + r["decode_s"], 4) for r in recs]
res["e2e_s"] = {"median": round(statistics.median(e2e), 4),
                "min": min(e2e), "max": max(e2e), "n": len(e2e)}
res["peak_rss_bytes"] = peak_kib * 1024
json.dump(res, open(out, "w"), indent=1)
print("e2e_s:", res["e2e_s"], "peak_rss_bytes:", res["peak_rss_bytes"], file=sys.stderr)
