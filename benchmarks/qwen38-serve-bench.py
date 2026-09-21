#!/usr/bin/env python3
"""Benchmark an OpenAI-compatible streaming server with fixed greedy protocol.

Token accounting: when the server reports usage.completion_tokens, decode rate
is labelled token_rate_completion (usage-verified). Otherwise only a
chunk_rate is recorded and decode_tok_s stays null. Usage-only SSE events
(choices == []) are tolerated.
"""
import argparse, hashlib, json, os, statistics, time, urllib.request

p = argparse.ArgumentParser()
p.add_argument("--base", default="http://127.0.0.1:8955")
p.add_argument("--model", required=True)
p.add_argument("--prompts", required=True)
p.add_argument("--limit", type=int, default=10)
p.add_argument("--new-tokens", type=int, default=32)
p.add_argument("--warmup", type=int, default=2)
p.add_argument("--passes", type=int, default=3)
p.add_argument("--label", default="")
p.add_argument("--out", default="")
a = p.parse_args()

corpus_sha = hashlib.sha256(open(a.prompts, "rb").read()).hexdigest()
corpus_name = os.path.basename(a.prompts)
prompts = [json.loads(l)["text"] for l in open(a.prompts) if l.strip()][: a.limit]

key = os.environ.get("LLM_API_KEY")
hdrs = {"Content-Type": "application/json"}
if key:
    hdrs["Authorization"] = "Bearer " + key

if a.model == "auto":
    req0 = urllib.request.Request(a.base + "/v1/models", headers=hdrs)
    with urllib.request.urlopen(req0, timeout=10) as r:
        a.model = json.load(r)["data"][0]["id"]
    print("served model id:", a.model, flush=True)


def gen(text):
    body = json.dumps({
        "model": a.model, "messages": [{"role": "user", "content": text}],
        "max_tokens": a.new_tokens, "temperature": 0, "stream": True,
        "stream_options": {"include_usage": True},
    }).encode()
    req = urllib.request.Request(a.base + "/v1/chat/completions", data=body, headers=hdrs)
    t0 = time.perf_counter()
    ttft = None
    completion_tokens = None
    n_content_chunks = 0
    parts = []
    with urllib.request.urlopen(req, timeout=600) as r:
        for line in r:
            if not line.startswith(b"data: "):
                continue
            payload = line[6:].strip()
            if payload == b"[DONE]":
                break
            d = json.loads(payload)
            if d.get("usage"):
                completion_tokens = d["usage"].get("completion_tokens")
            choices = d.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            piece = delta.get("content") or delta.get("reasoning_content") or ""
            if piece:
                n_content_chunks += 1
                if ttft is None:
                    ttft = time.perf_counter() - t0
                parts.append(piece)
    total = time.perf_counter() - t0
    return ttft, total, "".join(parts), completion_tokens, n_content_chunks


def rate(n, dt):
    return round(n / dt, 2) if n and n > 0 and dt and dt > 0 else None


def summarize(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {"median": round(statistics.median(values), 2),
            "mean": round(statistics.fmean(values), 2),
            "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
            "min": round(min(values), 2), "max": round(max(values), 2),
            "n": len(values)}


for _ in range(a.warmup):
    gen(prompts[0])

recs = []
for ps in range(a.passes):
    for i, text in enumerate(prompts):
        ttft, total, out, ctok, nch = gen(text)
        rec = {"pass": ps, "prompt_idx": i,
               "ttft_s": round(ttft, 4) if ttft is not None else None,
               "total_s": round(total, 3),
               "completion_tokens": ctok,
               "content_chunks": nch,
               "token_basis": ("usage.completion_tokens" if ctok else
                               "none: chunk fallback, rate reported separately"),
               "token_rate_completion": rate((ctok - 1) if ctok else None,
                                             (total - ttft) if ttft is not None else None)
               if ctok else None,
               "chunk_rate": rate(nch - 1, (total - ttft) if ttft is not None else None)
               if nch else None,
               "out_text_sha": hashlib.sha256(out.encode()).hexdigest()[:16]}
        recs.append(rec)
    print(f"pass {ps} done", flush=True)

result = {
    "meta": {"label": a.label, "endpoint": a.base, "model": a.model,
             "os": __import__("platform").platform(),
             "key_source": "LLM_API_KEY env (not logged)"},
    "protocol": {"new_tokens": a.new_tokens, "temperature": 0.0, "greedy": True,
                 "prompts_file": corpus_name, "prompts_corpus_sha256": corpus_sha,
                 "prompts_per_pass": len(prompts), "warmup": a.warmup,
                 "passes": a.passes,
                 "rate_definition": ("token_rate_completion = (usage.completion_tokens - 1) / "
                                     "(total - ttft), an end-to-end estimate whose first chunk "
                                     "may contain multiple tokens; boundaries are server-reported "
                                     "only via usage")},
    "ttft_s": summarize([r["ttft_s"] for r in recs]),
    "token_rate_completion": summarize([r["token_rate_completion"] for r in recs]),
    "chunk_rate_fallback": summarize([r["chunk_rate"] for r in recs])
    if not any(r["token_rate_completion"] for r in recs) else None,
    "per_prompt": recs,
}
js = json.dumps(result, indent=1)
if a.out:
    open(a.out, "w").write(js)
else:
    print(js)
print("usage_verified:", any(r["token_rate_completion"] for r in recs), flush=True)
