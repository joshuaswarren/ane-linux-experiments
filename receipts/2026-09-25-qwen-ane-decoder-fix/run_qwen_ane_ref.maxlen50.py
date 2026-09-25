#!/usr/bin/env python3
"""Qwen3.8-2B ANE reference on macOS via ANEForge.

Contract: benchmarks/qwen38-2b-contract.json backends.macos_ane —
ANEForge qwen35.load_gguf, resid_scale 1.0, host fp32 lm_head, greedy
(temp 0), fixed corpus, 3 warmups + 10 reps, 32 new tokens, per-record
ordered hash comparable with the GPU bench (qwen38_bench_lib).
Tokenizer: llama-tokenize -m GGUF -p PROMPT --ids (contract tokenizer block).
"""
import argparse, hashlib, json, os, platform, resource, statistics, subprocess, sys, time

p = argparse.ArgumentParser()
p.add_argument("--gguf", required=True)
p.add_argument("--prompts", required=True)
p.add_argument("--limit", type=int, default=10)
p.add_argument("--new-tokens", type=int, default=32)
p.add_argument("--warmups", type=int, default=3)
p.add_argument("--reps", type=int, default=10)
p.add_argument("--prefill-tokens", type=int, default=512)
p.add_argument("--out", default="")
a = p.parse_args()

sys.path.insert(0, os.environ.get("ANEFORGE_PATH", os.path.expanduser("~/src/ANEForge")))
from aneforge import __version__ as aneforge_version
from aneforge.qwen35 import load_gguf


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def ordered_records_hash(records):
    canon = [[r["pass"], r["prompt_idx"], r["input_ids"], r["output_ids"]]
             for r in sorted(records, key=lambda r: (r["pass"], r["prompt_idx"]))]
    return hashlib.sha256(json.dumps(canon, sort_keys=False).encode()).hexdigest()


def summarize(values):
    return {"median": round(statistics.median(values), 2),
            "mean": round(statistics.fmean(values), 2),
            "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
            "min": round(min(values), 2), "max": round(max(values), 2),
            "n": len(values)}


def encode(prompt):
    r = subprocess.run(["llama-tokenize", "-m", a.gguf, "-p", prompt, "--ids"],
                       capture_output=True, text=True, check=True)
    return [int(x) for x in r.stdout.split()]


prompts = [json.loads(l)["text"] for l in open(a.prompts) if l.strip()][: a.limit]
corpus_sha = sha256_file(a.prompts)
gguf_sha = sha256_file(a.gguf)

print(f"loading GGUF ({a.gguf}) ...", flush=True)
t0 = time.perf_counter()
m = load_gguf(a.gguf, resid_scale=1.0)     # contract macos_ane: resid_scale 1.0
load_s = time.perf_counter() - t0
m.ane_lm_head = False                      # contract: host fp32 lm_head
print(f"model load: {load_s:.1f}s", flush=True)


def run_gen(ids):
    stages, t_first = {}, [None]
    t_start = time.perf_counter()

    def on_stage(name, el):
        stages[name] = stages.get(name, 0.0) + el

    def on_token(_tok):
        if t_first[0] is None:
            t_first[0] = time.perf_counter() - t_start
    out = m.generate(ids, max_new_tokens=a.new_tokens, max_len=50, temperature=0.0,
                     top_p=1.0, top_k=0, eos_id=None,
                     on_token=on_token, on_stage=on_stage)  # max_len pinned like the frozen reference capture (one decoder build)
    wall = time.perf_counter() - t_start
    return [int(t) for t in out], t_first[0], wall, stages


# cold: model load reported above; this is the first generate (compile included)
ids0 = encode(prompts[0])
cold_out, cold_ttft, cold_wall, _ = run_gen(ids0)
print(f"cold decode wall {cold_wall:.2f}s ttft {cold_ttft:.2f}s", flush=True)

# warmups: whole corpus
for w in range(a.warmups):
    for t in prompts:
        run_gen(encode(t))
print(f"{a.warmups} warmup corpus passes done", flush=True)

records = []
for rep in range(a.reps):
    for i, text in enumerate(prompts):
        ids = encode(text)
        out, ttft, wall, stages = run_gen(ids)
        records.append({
            "pass": rep, "prompt_idx": i, "input_ids": ids, "output_ids": out,
            "prompt_tokens": len(ids), "generated_tokens": len(out),
            "ttft_s": round(ttft, 4),
            "ttft_tok_rate": round(len(ids) / ttft, 2) if ttft > 0 else 0.0,
            "decode_s": round(wall - ttft, 4),
            "decode_tok_rate": round((len(out) - 1) / (wall - ttft), 2)
            if len(out) >= 2 and wall > ttft else 0.0,
            "e2e_s": round(wall, 4),
            "stage_s": {k: round(v, 4) for k, v in sorted(stages.items())},
        })
    print(f"rep {rep} done", flush=True)

peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # macOS: bytes

# pure prefill leg: 512 tokens, no generation (same construction as the GPU bench)
pure_prefill = None
if a.prefill_tokens:
    text = " ".join(prompts)
    ids = encode(text)
    while len(ids) < a.prefill_tokens:
        ids = ids + encode(" " + text)
    ids = ids[: a.prefill_tokens]
    # the GDN hybrid has no batched-prefill mixer (recurrence/scan wall): the prefill
    # leg runs the SAME staged decode path token-by-token, 512 forwards per wall
    Mpre = len(ids) + 1
    m.generate(ids, max_new_tokens=1, max_len=Mpre, temperature=0.0, top_p=1.0,
               top_k=0, batched_prefill=False)  # compile this length (untimed)
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        m.generate(ids, max_new_tokens=1, max_len=Mpre, temperature=0.0, top_p=1.0,
                   top_k=0, batched_prefill=False)
        times.append(time.perf_counter() - t0)
    pure_prefill = {"prompt_tokens": len(ids),
                    "median_tok_rate": round(len(ids) / statistics.median(times), 2),
                    "walls_s": [round(t, 4) for t in times]}

result = {
    "meta": {
        "os": platform.platform(), "machine": platform.machine(),
        "python": platform.python_version(), "runtime": "ANEForge qwen35.load_gguf",
        "aneforge_version": str(aneforge_version), "compute": "ANE",
        "resid_scale": 1.0, "lm_head": "host fp32", "ane_lm_head": False,
        "gguf_path": os.path.basename(a.gguf), "gguf_sha256": gguf_sha,
        "prompts_corpus_sha256": corpus_sha, "label": "macos-ane-reference",
    },
    "protocol": {
        "new_tokens": a.new_tokens, "temperature": 0.0, "greedy": True,
        "prompts_per_pass": len(prompts), "warmup": a.warmups, "passes": a.reps,
        "model_load_s": round(load_s, 2),
    },
    "cold_start": {"decode_wall_s": round(cold_wall, 4), "ttft_s": round(cold_ttft, 4),
                   "output_ids": cold_out},
    "ttft_tok_rate": summarize([r["ttft_tok_rate"] for r in records]),
    "decode_tok_rate": summarize([r["decode_tok_rate"] for r in records]),
    "e2e_s": summarize([r["e2e_s"] for r in records]),
    "pure_prefill": pure_prefill,
    "peak_rss_bytes": peak_rss,
    "ordered_records_sha256": ordered_records_hash(records),
    "per_prompt": records,
}
js = json.dumps(result, indent=1)
print("ordered_records_sha256:", result["ordered_records_sha256"], file=sys.stderr)
print("peak_rss_bytes:", peak_rss, file=sys.stderr)
if a.out:
    open(a.out, "w").write(js)
else:
    print(js)
