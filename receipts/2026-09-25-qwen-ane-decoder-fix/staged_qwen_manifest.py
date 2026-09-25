#!/usr/bin/env python3
"""Export the staged-Qwen decoder manifest (+ golden I/O checksums) from ANEForge.

Run on macOS with the fixed ANEForge (lane/deltanet-split-decode, 2ea941c):
  ANEFORGE_PATH=~/src/ane-af-split-wt python3 tools/staged_qwen_manifest.py \
    --gguf Qwen3.8-2B-Q4_K_M.gguf --max-len 50 --goldens \
    --prompts qwen38-2b-prompts.jsonl --out qwen38-staged-manifest

Emits <out>/manifest.json: per-program src/dst surfaces in ANEC header order
(input_ports/output_ports order), lane names, ctx roles, resident state pairs,
group_start/group_end flags; plus GGUF-derived host-side constants the Linux
runner needs (dim, final-norm baking note, resid_scale, lm_head source).

With --goldens also emits <out>/goldens.json: sha256 per src/dst buffer for the
FIRST decode step of prompt p001, as executed by the macOS e5rt path. The Linux
runner's --replay gate byte-compares its first step against these.
"""
import argparse, hashlib, json, os, sys

p = argparse.ArgumentParser()
p.add_argument("--gguf", required=True)
p.add_argument("--max-len", type=int, default=50)
p.add_argument("--goldens", action="store_true")
p.add_argument("--prompts", default="")
p.add_argument("--new-tokens", type=int, default=1)
p.add_argument("--out", required=True)
a = p.parse_args()

sys.path.insert(0, os.environ.get("ANEFORGE_PATH", os.path.expanduser("~/src/ane-af-split-wt")))
import numpy as np
from aneforge.qwen35 import load_gguf

CTX = ["oh", "inv", "mask", "cosp", "sinp"]

print(f"loading GGUF ({a.gguf}) ...", flush=True)
m = load_gguf(a.gguf, resid_scale=1.0)          # contract macos_ane: resid_scale 1.0
m.ane_lm_head = False                            # contract: host fp32 lm_head

# pin each program's build dir (model.mil + weights.bin + cache/) in compile order so the
# HWX export + ANEC conversion pair deterministically with the manifest
os.makedirs(a.out, exist_ok=True)
import aneforge._compile as _compile
_orig_compile_multi = _compile.compile_multi
_seq = {"i": 0}
def _seq_compile_multi(*args, **kw):
    d = os.path.join(a.out, "prog_%03d" % _seq["i"])
    _seq["i"] += 1
    kw["build_dir"] = d
    return _orig_compile_multi(*args, **kw)
_compile.compile_multi = _seq_compile_multi

d = m._decoder(int(a.max_len))
_compile.compile_multi = _orig_compile_multi
print(f"compiler wrote {_seq['i']} program dirs under {a.out}")

chunks = []
for ci, c in enumerate(d["chunks"]):
    net, pd = c["net"], c["p"]
    role = {}
    for name, port in pd["x"].items():
        role[port] = {"kind": "lane", "lane": name}
    for name, port in pd["h"].items():
        role[port] = {"kind": "lane", "lane": name}
    for k in CTX:
        if k in pd:
            role[pd[k]] = {"kind": "ctx", "lane": k}
    if "wpe_pos" in pd:
        role[pd["wpe_pos"]] = {"kind": "ctx", "lane": "wpe_pos"}
    inv_h = {port: name for name, port in pd["h"].items()}
    srcs, seen_state = [], set()
    for t, port in net.input_ports:
        if port in pd["states"]:
            seen_state.add(port)
            srcs.append({"port": port, "kind": "state_in", "lane": f"state{len(seen_state)-1}",
                         "shape": list(pd["states"][port])})
        else:
            r = dict(role[port]); r["shape"] = [int(x) for x in t.shape]; r["port"] = port
            srcs.append(r)
    h_ports = set(pd["h"].values())
    dsts, state_outs = [], []
    for t, port in net.output_ports:
        if port in h_ports:
            dsts.append({"port": port, "kind": "lane", "lane": inv_h[port], "shape": [int(x) for x in t.shape]})
        else:
            state_outs.append({"port": port, "shape": list(t.shape)})
    states = [(ip, sh) for ip, sh in pd["states"].items()]           # pair order
    assert len(states) == len(state_outs), f"chunk {ci}: {len(states)} state ins vs {len(state_outs)} outs"
    chunks.append({
        "srcs": srcs, "dsts": dsts,
        "states": [{"in_port": ip, "in_shape": list(sh), "out_port": so["port"],
                    "out_shape": [int(x) for x in so["shape"]]} for (ip, sh), so in zip(states, state_outs)],
        "group_start": bool(pd.get("group_start")), "group_end": bool(pd.get("group_end")),
    })

manifest = {
    "max_len": int(a.max_len),
    "n_programs": len(chunks),
    "programs": chunks,
    "host_head": {"source": "GGUF token_embd dequantized fp32 (tied lm_head, resid_scale 1.0)",
                  "final_norm": "GGUF output_norm.weight, used as-is (baked 1+w)"},
    "aneforge_tip": os.popen("git -C %s log --oneline -1" % os.environ.get("ANEFORGE_PATH", "~/src/ane-af-split-wt")).read().strip(),
}
os.makedirs(a.out, exist_ok=True)
json.dump(manifest, open(os.path.join(a.out, "manifest.json"), "w"), indent=1)
print(f"manifest: {len(chunks)} programs -> {a.out}/manifest.json")

if a.goldens:
    if not a.prompts:
        sys.exit("--goldens needs --prompts (the contract corpus)")
    import subprocess
    text = json.loads(open(a.prompts).readline())["text"]
    r = subprocess.run(["llama-tokenize", "-m", a.gguf, "-p", text, "--ids"],
                       capture_output=True, text=True, check=True)
    ids = [int(x) for x in r.stdout.replace("[", " ").replace("]", " ").replace(",", " ").split()]
    cap = {}
    state = {"open": True}
    for ci, c in enumerate(d["chunks"]):
        pr = c["net"].prog
        o_si, o_ro = pr.set_input, pr.read_output
        def si(port, arr, ci=ci, o_si=o_si):
            if state["open"]:
                cap.setdefault(ci, {"in": [], "out": []})["in"].append(
                    (port, hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()))
            return o_si(port, arr)
        def ro(port, ci=ci, o_ro=o_ro):
            v = o_ro(port)
            if state["open"]:
                cap[ci]["out"].append(
                    (port, hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest()))
            return v
        pr.set_input, pr.read_output = si, ro
    print("exporter ids[:5]:", ids[:5], "len", len(ids), flush=True)
    m.generate(ids, max_new_tokens=a.new_tokens, max_len=int(a.max_len), temperature=0.0,
               top_p=1.0, top_k=0, batched_prefill=False)
    state["open"] = False
    for ci in (0, 1, 2):
        if ci in cap:
            print(f"prog{ci} capture order in:", [(str(pt), sh[:12]) for pt, sh in cap[ci]["in"][:4]], flush=True)
    goldens = {}
    for ci, c in enumerate(d["chunks"]):
        ins = cap[ci]["in"]; outs = cap[ci]["out"]
        ports_in = [s["port"] for s in chunks[ci]["srcs"]]
        ports_out = [x["port"] for x in chunks[ci]["dsts"]]   # state outs stay device-side (share_buffer)
        smap_in, smap_out = {}, {}
        for pt, sh in ins: smap_in.setdefault(pt, sh)     # FIRST occurrence = first decode step
        for pt, sh in outs: smap_out.setdefault(pt, sh)
        missing_in = [pt for pt in ports_in if pt not in smap_in]
        missing_out = [pt for pt in ports_out if pt not in smap_out]
        assert not missing_in and not missing_out, f"chunk {ci}: uncaptured {missing_in} {missing_out}"
        goldens[str(ci)] = {
            "srcs": [smap_in[pt] for pt in ports_in],
            "dsts": [smap_out[pt] for pt in ports_out],
        }
    json.dump(goldens, open(os.path.join(a.out, "goldens.json"), "w"), indent=1)
    print(f"goldens: first-step sha256 for {len(goldens)} programs -> {a.out}/goldens.json")
