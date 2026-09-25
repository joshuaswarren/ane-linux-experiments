#!/usr/bin/env python3
"""Chained staged-Qwen decode runner on Linux ANE (omarchy-ane).

Consumes the macOS export from tools/staged_qwen_manifest.py:
  manifest.json  per-program src/dst surfaces in ANEC surface order, lane names,
                 resident state pairs, group_start/group_end flags
  goldens.json   (optional) first-decode-step sha256 per surface from the macOS
                 e5rt path -- the replay gate byte-compares against it
  programs/prog_NNN.anec  one compiled program each, in manifest order

Host-side work is IDENTICAL to the macOS e5rt reference path (ANEForge
lane/deltanet-split-decode @ 2ea941c, contract macos_ane: ane_lm_head=False):
fp16 embedding gather, per-step context tensors, fp32 lm_head matmul + argmax.
All 24 layers run on the ANE through the chained programs; no CPU fallback of
layer math exists in this path (a program failure terminates the run -- contract
linux_ane: fallback forbidden).

Backend (--backend-module): a python module exposing model(path, lib_path=...)
whose instances implement predict(inarrs) -> list[np.ndarray]. The bundled
libane_model.py wraps /usr/lib/libane_python.so.

Modes:
  verify  10 prompts x 32 greedy tokens vs the frozen chunk_00 reference
  replay  first decode step of p001, sha256 per surface vs goldens.json
  bench   contract timing: 3 warmup corpus passes, 10 reps x 10 prompts
"""
import argparse, hashlib, importlib.util, json, os, statistics, sys, time

import numpy as np

f16 = np.float16

ap = argparse.ArgumentParser()
ap.add_argument("--gguf", required=True)
ap.add_argument("--export", required=True)
ap.add_argument("--programs", default="", help="pattern with %%03d (default <export>/programs/prog_%%03d.anec)")
ap.add_argument("--backend-module", default="", help="module exposing model(path, lib_path=...); default libane_model.py beside this script")
ap.add_argument("--libane-so", default="/usr/lib/libane_python.so")
ap.add_argument("--ref", default="", help="chunk_00.json (verify/replay modes)")
ap.add_argument("--mode", choices=("verify", "replay", "bench"), default="verify")
ap.add_argument("--new-tokens", type=int, default=32)
ap.add_argument("--resid-scale", type=float, default=1.0)
a = ap.parse_args()

MAN = json.load(open(os.path.join(a.export, "manifest.json")))
M = int(MAN["max_len"])
PROGS = MAN["programs"]
assert MAN["n_programs"] == len(PROGS)
if not a.programs:
    a.programs = os.path.join(a.export, "programs", "prog_%03d.anec")
if "%03d" not in a.programs and os.path.isdir(a.programs):
    a.programs = os.path.join(a.programs, "prog_%03d.anec")
mod_path = a.backend_module or os.path.join(os.path.dirname(os.path.abspath(__file__)), "libane_model.py")
spec = importlib.util.spec_from_file_location("staged_backend", mod_path)
BMOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BMOD)

# --- GGUF: embed (fp16), final_norm (fp16, baked 1+w), lm_head (fp32, tied) ----

def load_gguf_parts(path):
    from gguf import GGUFReader
    from gguf.quants import dequantize
    r = GGUFReader(path)
    tn = {t.name: t for t in r.tensors}
    def dq(name, dtype):
        t = tn[name]
        d = np.asarray(t.data)
        if t.tensor_type != 30:  # != GGMLQuantizationType.F32
            d = dequantize(d, t.tensor_type)
        return d.astype(dtype)
    return dq("token_embd.weight", f16), dq("output_norm.weight", f16), dq("token_embd.weight", np.float32)

print(f"loading GGUF ({a.gguf}) ...", flush=True)
t0 = time.perf_counter()
EMB, FINAL_NORM, LM_HEAD = load_gguf_parts(a.gguf)
EMB = EMB * f16(1.0 / a.resid_scale)
LM_T = np.ascontiguousarray(LM_HEAD.T, np.float32)   # same precompute as ANEForge _logits
print(f"host weights: {time.perf_counter()-t0:.1f}s (embed {EMB.shape}, lmT {LM_T.shape})", flush=True)

# --- rope tables: verbatim ANEForge llm.rope_tables (rope_interleaved=False) ----

def rope_tables(seq, dh, base, rotary_dim):
    rd = rotary_dim or dh
    inv = 1.0 / (base ** (np.arange(0, rd, 2) / rd))
    pos = np.arange(seq)[:, None] * inv[None, :]
    emb = np.concatenate([pos, pos], -1)
    c, s = np.cos(emb), np.sin(emb)
    if rd < dh:
        c = np.concatenate([c, np.ones((seq, dh - rd))], 1)
        s = np.concatenate([s, np.zeros((seq, dh - rd))], 1)
    return c.astype(f16), s.astype(f16)

from gguf import GGUFReader
META = {f.name: f for f in GGUFReader(a.gguf).fields.values()}
def _sc(key, default):
    for k in META:
        if k.endswith("." + key):
            f = META[k]
            return int(f.parts[f.data[-1]][0])
    return default
DH = _sc("attention.key_length", 0)
RD = _sc("rope.dimension_count", 0)
BASE = 10000.0
for k in META:
    if k.endswith("rope.freq_base"):
        BASE = float(META[k].parts[META[k].data[-1]][0])
        break
COS, SIN = rope_tables(M, DH, BASE, RD)

# --- open programs -------------------------------------------------------------

print(f"opening {len(PROGS)} programs ...", flush=True)
t0 = time.perf_counter()
models, surf = [], []
for i in range(len(PROGS)):
    path = a.programs % i if "%03d" in a.programs else a.programs
    try:
        mdl = BMOD.model(path, lib_path=a.libane_so)
    except TypeError:
        mdl = BMOD.model(path)
    models.append(mdl)
    assert mdl.src_count == len(PROGS[i]["srcs"]), \
        f"prog {i}: src_count {mdl.src_count} != manifest {len(PROGS[i]['srcs'])}"
    assert mdl.dst_count == len(PROGS[i]["dsts"]) + len(PROGS[i]["states"]), \
        f"prog {i}: dst_count {mdl.dst_count} mismatch"
    surf.append({"src_nchw": getattr(mdl, "src_nchw", None) or [s["shape"] for s in PROGS[i]["srcs"]],
                 "dst_nchw": getattr(mdl, "dst_nchw", None) or [x["shape"] for x in PROGS[i]["dsts"]]})
print(f"programs open: {time.perf_counter()-t0:.1f}s", flush=True)

def as_surface(arr, nchw, what, pi):
    want = tuple(int(x) for x in nchw[:4])
    flat = np.ascontiguousarray(arr, f16).reshape(-1)
    need = int(np.prod(want))
    if flat.size != need:
        raise RuntimeError(f"prog {pi} {what}: lane {flat.size} elems vs surface {need} ({want}) -- padded surface needs a de-stride path")
    return flat.reshape(want)

def ctx_vals(pos):
    oh = np.zeros((1, M, 1), f16); oh[0, pos, 0] = 1.0
    inv = np.ones((1, M, 1), f16); inv[0, pos, 0] = 0.0
    mv = np.full((1, 1, M), -1e4, f16); mv[..., :pos + 1] = 0.0
    return {"oh": oh, "inv": inv, "mask": mv, "cosp": COS[pos][None], "sinp": SIN[pos][None]}

class Chain:
    """One generation state: per-program resident states + name-keyed lane flow.
    Program order + lane overwrite semantics are exactly the macOS e5rt step loop."""
    def __init__(self, capture=False):
        self.rounds = []
        self.capture = capture
        self.captured = {}
        self.reset_states()

    def reset_states(self):
        """Zero every resident state -- ANEForge's generate() does this on every call;
        skipping it silently carries the previous generation's state (the p001 bug)."""
        self.states = [{f"state{k}": np.zeros([int(x) for x in st["in_shape"]], f16)
                        for k, st in enumerate(pr["states"])} for pr in PROGS]

    def step(self, tok, pos):
        vals = ctx_vals(pos)
        hs = {}
        hidden = np.asarray(EMB[tok], f16)[None]
        t0 = time.perf_counter()
        for pi, pr in enumerate(PROGS):
            if pr["group_start"]:
                hs["x"] = hidden
            srcs = []
            for si_, s in enumerate(pr["srcs"]):
                if s["kind"] == "state_in":
                    arr = self.states[pi][s["lane"]]
                elif s["kind"] == "ctx":
                    arr = vals[s["lane"]]
                else:
                    arr = hs[s["lane"]]
                sv = as_surface(arr, surf[pi]["src_nchw"][si_], s["lane"], pi)
                if self.capture:
                    self.captured.setdefault(pi, {"srcs": [], "dsts": []})["srcs"].append(sha(sv))
                srcs.append(sv)
            outs = models[pi].predict(srcs)
            nd = len(pr["dsts"])
            for x, arr in zip(pr["dsts"], outs[:nd]):
                if self.capture:
                    self.captured[pi]["dsts"].append(sha(arr))
                hs[x["lane"]] = arr
            for k, st in enumerate(pr["states"]):
                self.states[pi][f"state{k}"] = np.asarray(outs[nd + k], f16)
            if pr["group_end"]:
                hidden = hs["h"]
        self.rounds.append(time.perf_counter() - t0)
        return hidden.reshape(-1).astype(np.float32)

    def generate(self, ids, max_new_tokens):
        self.reset_states()
        for p, tok in enumerate(ids[:-1]):
            self.step(tok, p)
        out, cur, pos = [], ids[-1], len(ids) - 1
        while len(out) < max_new_tokens:
            if pos >= M - 1:
                break
            hidden = self.step(cur, pos)
            cur = int(np.argmax(hidden @ LM_T))
            pos += 1
            out.append(cur)
        return out

def sha(arr):
    return hashlib.sha256(np.ascontiguousarray(arr, f16).tobytes()).hexdigest()

def load_ref():
    ref = json.load(open(a.ref))
    assert ref["model_sha256"] == "4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff"
    return ref

if a.mode == "replay":
    goldens = json.load(open(os.path.join(a.export, "goldens.json")))
    ids = load_ref()["prompts"][0]["prompt_token_ids"]
    ch = Chain(capture=True)
    ch.step(ids[0], 0)
    bad = []
    for ci, pr in enumerate(PROGS):
        want = goldens[str(ci)]
        got = ch.captured.get(ci, {"srcs": [], "dsts": []})
        for j, (w, g) in enumerate(zip(want["srcs"], got["srcs"])):
            if w != g:
                bad.append(f"prog{ci} src{j}")
        for j, (w, g) in enumerate(zip(want["dsts"], got["dsts"])):
            if w != g:
                bad.append(f"prog{ci} dst{j}")
        if len(got["srcs"]) != len(want["srcs"]) or len(got["dsts"]) != len(want["dsts"]):
            bad.append(f"prog{ci} count {len(got['srcs'])}/{len(got['dsts'])} vs {len(want['srcs'])}/{len(want['dsts'])}")
    if bad:
        print(f"REPLAY FAIL: {len(bad)} surface mismatches: {bad[:12]}")
        sys.exit(1)
    print(f"REPLAY PASS: {sum(len(v['srcs']) + len(v['dsts']) for v in goldens.values())} surfaces byte-identical to the macOS e5rt goldens")
    sys.exit(0)

ref = load_ref()
prompts = ref["prompts"]
assert len(prompts) == 10, f"expected the 10-prompt chunk_00 reference, got {len(prompts)}"
ch = Chain()
t0 = time.perf_counter()
g = ch.generate(prompts[0]["prompt_token_ids"], a.new_tokens)
print(f"cold first prompt: {time.perf_counter()-t0:.1f}s (steps {len(ch.rounds)}, "
      f"first rounds {[round(w, 3) for w in ch.rounds[:3]]} med {round(statistics.median(ch.rounds), 3)}s)", flush=True)

if a.mode == "verify":
    ok = 0
    for i, pr in enumerate(prompts):
        t0 = time.perf_counter()
        gen = ch.generate(pr["prompt_token_ids"], a.new_tokens)
        wall = time.perf_counter() - t0
        want = pr["runs"][0]["generated_ids"][: a.new_tokens]
        match = gen == want
        ok += match
        mm = next((j for j, (x, y) in enumerate(zip(gen, want)) if x != y), min(len(gen), len(want)))
        print(f"{pr['id']} {'MATCH' if match else 'MISMATCH'} wall={wall:.2f}s first_diff={mm} "
              f"gen={gen[:8]} want={want[:8]}", flush=True)
        ch = Chain()
    print(json.dumps({"prompts_match": ok, "prompts_total": len(prompts)}))
    print(f"STAGED-QWEN-LINUX {'PASS' if ok == len(prompts) else 'FAIL'}")
    sys.exit(0 if ok == len(prompts) else 1)

if a.mode == "bench":
    WARMUPS, REPS = 3, 10
    rows = []
    print(f"bench: {WARMUPS} warmup corpus passes ...", flush=True)
    for w in range(WARMUPS):
        for pr in prompts:
            Chain().generate(pr["prompt_token_ids"], a.new_tokens)
        print(f"warmup {w + 1}/{WARMUPS} done", flush=True)
    for rep in range(REPS):
        for pr in prompts:
            ids = pr["prompt_token_ids"]
            ch = Chain()
            t0 = time.perf_counter()
            for p, tok in enumerate(ids[:-1]):
                ch.step(tok, p)
            t_prefill = time.perf_counter() - t0
            t0 = time.perf_counter()
            out, cur, pos = [], ids[-1], len(ids) - 1
            for _ in range(a.new_tokens):
                hidden = ch.step(cur, pos)
                cur = int(np.argmax(hidden @ LM_T))
                pos += 1
                out.append(cur)
            t_dec = time.perf_counter() - t0
            rows.append({"rep": rep, "id": pr["id"], "prefill_s": round(t_prefill, 4),
                         "decode_s": round(t_dec, 4),
                         "decode_tok_s": round(a.new_tokens / t_dec, 2),
                         "e2e_s": round(t_prefill + t_dec, 4)})
        print(f"rep {rep + 1}/{REPS} done", flush=True)
    dec = [r["decode_tok_s"] for r in rows]
    pre = [r["prefill_s"] for r in rows]
    rng = np.random.default_rng(0)
    boots = [statistics.median([dec[j] for j in rng.integers(0, len(dec), len(dec))]) for _ in range(2000)]
    res = {"decode_tok_s_median": round(statistics.median(dec), 2),
           "decode_tok_s_ci95": [round(float(np.percentile(boots, 2.5)), 2), round(float(np.percentile(boots, 97.5)), 2)],
           "prefill_median_s": round(statistics.median(pre), 4),
           "ane_programs_per_step": len(PROGS),
           "rows": rows}
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    json.dump(res, open("staged-qwen-bench.json", "w"), indent=1)
