#!/usr/bin/env python3
"""Chain-scale device gate: run minted chain bundles against fp32 refs.

Same libane-strict-fill path and reference model as ffn_gate4.py (the
receipted gate v4): y = silu(x @ W1.T) @ W2.T in fp32 from the
palette-decoded real weights; rngs 11/33/57; budget 0.05. One invocation
gates a list of bundles; the as-minted L00-f1 control (expected 0.947431)
can be included by naming it with the ASMINTED prefix.

usage: ffn_chain_gate.py <libane.so> <weights-dir> <bundles-dir> <outdir>
                         name1 [name2 ...]
Weights dir holds encoder_layers_{L}_feed_forward{m}_linear{h}_weight...
npy files (fp16). Bundle name island-ffn-L{LL}-f{m}.
"""
import ctypes, hashlib, json, sys, time
from pathlib import Path
import numpy as np

LIB = sys.argv[1]
WEIGHTS = Path(sys.argv[2])
BUNDLES = Path(sys.argv[3])
OUT = Path(sys.argv[4])
NAMES = sys.argv[5:]
OUT.mkdir(parents=True, exist_ok=True)

BASE = 25728
MM1_STRIDE, MM1_HDR, MM1_BIAS = 32960, 128, 32

lib = ctypes.CDLL(LIB)
for name, rest, args in (
    ("__ane_init", ctypes.c_void_p, [ctypes.c_char_p, ctypes.c_int]),
    ("__ane_free", None, [ctypes.c_void_p]),
    ("ane_exec", ctypes.c_int, [ctypes.c_void_p]),
    ("__ane_src_size", ctypes.c_uint64, [ctypes.c_void_p, ctypes.c_uint32]),
    ("__ane_dst_size", ctypes.c_uint64, [ctypes.c_void_p, ctypes.c_uint32]),
    ("__ane_send", None, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]),
    ("__ane_read", None, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]),
):
    f = getattr(lib, name); f.restype = rest; f.argtypes = args


def run_bytes(bundle_path, x16):
    nn = lib.__ane_init(str(bundle_path).encode(), 0)
    assert nn
    try:
        s0, d0 = int(lib.__ane_src_size(nn, 0)), int(lib.__ane_dst_size(nn, 0))
        tile = np.zeros(s0, dtype=np.uint8)
        xb = np.frombuffer(x16.tobytes(), dtype=np.uint8)
        tile[:xb.size] = xb
        lib.__ane_send(nn, ctypes.c_char_p(tile.ctypes.data), 0)
        assert lib.ane_exec(nn) == 0
        y = np.zeros(d0 // 2, dtype="<f2")
        lib.__ane_read(nn, ctypes.c_char_p(y.ctypes.data), 0)
        return y[:384000].astype(np.float32).reshape(375, 1024)
    finally:
        lib.__ane_free(nn)


records = {}
worst = 0.0
t0 = time.time()
for name in NAMES:
    asminted = name.startswith("ASMINTED:")
    bundle_name = name.split("ASMINTED:", 1)[1] if asminted else name
    m = name
    layer = int(bundle_name.split("-L")[1].split("-")[0])
    mod = bundle_name.rsplit("-f", 1)[1]
    W1 = np.load(WEIGHTS / f"encoder_layers_{layer}_feed_forward{mod}_linear1_weight_to_fp16_palettized.npy").astype(np.float32)
    W2 = np.load(WEIGHTS / f"encoder_layers_{layer}_feed_forward{mod}_linear2_weight_to_fp16_palettized.npy").astype(np.float32)
    program = BUNDLES / bundle_name / "program-0.anec"
    rec = {"program_sha256": hashlib.sha256(program.read_bytes()).hexdigest()}
    rels = {}
    for rng in (11, 33, 57):
        x = np.random.default_rng(rng).standard_normal((375, 1024)).astype(np.float16)
        p1 = x.astype(np.float32) @ W1.T
        h = p1 / (1 + np.exp(-np.clip(p1, -80, 80)))
        ref = h @ W2.T
        y = run_bytes(program, x)
        rels[f"rng{rng}"] = float(np.linalg.norm(y - ref) / np.linalg.norm(ref))
        print(f"  {m} rng {rng}: rel_l2={rels[f'rng{rng}']:.6f}", flush=True)
    rec["rel_l2"] = rels
    rec["gate_worst"] = max(rels.values())
    rec["asminted_control"] = asminted
    if not asminted:
        worst = max(worst, rec["gate_worst"])
        rec["pass"] = rec["gate_worst"] <= 0.05
    else:
        rec["expected"] = 0.947431
    records[m] = rec

gate = {"records": records, "gate_worst": worst, "budget": 0.05,
        "pass": worst <= 0.05, "wall_s": round(time.time() - t0, 1)}
json.dump(gate, open(OUT / "chain_gate.json", "w"), indent=1)
print(f"GATE {'PASS' if gate['pass'] else 'FAIL'} worst={worst:.6f} "
      f"(budget 0.05) wall={gate['wall_s']}s", flush=True)
sys.exit(0 if gate["pass"] else 1)
