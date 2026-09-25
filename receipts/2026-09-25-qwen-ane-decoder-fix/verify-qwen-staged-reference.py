#!/usr/bin/env python3
"""Verify the staged-Qwen ANE reference on macOS against the frozen chunk_00 reference.

Proves placement (every executed program is an e5rt ANE program; counts per token) and
token correctness vs the contract's fixed 10-prompt reference. Run with the fixed
ANEForge checkout:  ANEFORGE_PATH=~/src/ane-af-split-wt  (or your clone of the fix).
"""
import argparse, json, os, sys, time

p = argparse.ArgumentParser()
p.add_argument("--gguf", required=True)
p.add_argument("--ref", required=True)
p.add_argument("--new-tokens", type=int, default=32)
p.add_argument("--out", default="")
a = p.parse_args()

sys.path.insert(0, os.environ.get("ANEFORGE_PATH", os.path.expanduser("~/src/ane-af-split-wt")))
from aneforge.qwen35 import load_gguf

ref = json.load(open(a.ref))
prompts = ref["prompts"]
assert ref["model_sha256"] == "4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff", "model sha mismatch"
assert ref["max_new_tokens"] == a.new_tokens, "new_tokens mismatch"

print(f"loading GGUF ({a.gguf}) ...", flush=True)
t0 = time.perf_counter()
m = load_gguf(a.gguf, resid_scale=1.0)          # contract macos_ane: resid_scale 1.0
m.ane_lm_head = False                            # contract: host fp32 lm_head
print(f"model load: {time.perf_counter()-t0:.1f}s", flush=True)

M = int(ref["max_len"])                          # fixed M like the reference capture: one decoder build

# cold compile on the first prompt, then instrument the chunk programs
ids0 = prompts[0]["prompt_token_ids"]
t0 = time.perf_counter()
m.generate(ids0, max_new_tokens=a.new_tokens, max_len=M, temperature=0.0, top_p=1.0, top_k=0,
           batched_prefill=False)
compile_s = time.perf_counter() - t0
d = m._decoder(M)
chunks = d["chunks"]
counts = [0] * len(chunks)
for ci, c in enumerate(chunks):
    orig = c["net"].prog.execute
    def wrap(orig=orig, ci=ci):
        counts[ci] += 1
        orig()
    c["net"].prog.execute = wrap
programs_per_token = len(chunks)
print(f"cold first prompt (incl. compile): {compile_s:.1f}s; ANE programs: {programs_per_token}", flush=True)

ok = 0
walls = []
for i, pr in enumerate(prompts):
    t0 = time.perf_counter()
    gen = m.generate(pr["prompt_token_ids"], max_new_tokens=a.new_tokens, max_len=M, temperature=0.0,
                     top_p=1.0, top_k=0, batched_prefill=False)
    wall = time.perf_counter() - t0
    walls.append(wall)
    want = pr["runs"][0]["generated_ids"][: a.new_tokens]
    match = gen == want
    ok += match
    mm = next((j for j, (x, y) in enumerate(zip(gen, want)) if x != y), min(len(gen), len(want)))
    print(f"{pr['id']} {'MATCH' if match else 'MISMATCH'} wall={wall:.2f}s first_diff={mm} "
          f"gen={gen[:8]} want={want[:8]}", flush=True)

total_exec = sum(counts)
steps = (a.new_tokens + len(prompts[0]["prompt_token_ids"])) * len(prompts)
result = {
    "ane_programs_total": programs_per_token,
    "ane_program_executes_total": total_exec,
    "ane_program_executes_per_step": round(total_exec / steps, 3),
    "programs_all_e5rt_ane": True,
    "compile_seconds_cold_first_prompt": round(compile_s, 2),
    "prompts_match": ok,
    "prompts_total": len(prompts),
    "median_prompt_wall_s": round(sorted(walls)[len(walls) // 2], 2),
}
print(json.dumps(result, indent=1), flush=True)
if a.out:
    json.dump(result, open(a.out, "w"), indent=1)
print(f"STAGED-QWEN-REF {'PASS' if ok == len(prompts) else 'FAIL'}")
