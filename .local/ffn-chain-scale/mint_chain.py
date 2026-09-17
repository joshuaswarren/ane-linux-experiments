#!/usr/bin/env python3
"""Mint 48 fused FFN chain bundles (island-ffn-L{LL}-f{m}, m in 1..2) by
template surgery on the certified as-minted L00-f1 chain program.

The chain program (28 tasks, mm1[4096x1024] -> silu -> mm2[1024x4096]) is
identical in structure for every FFN site; only the const payload differs.
Per site: write fp16(W1_lm) into the mm1 payload slots and
fp16(W2perm_lm[j,q]=W2_lm[j,q^3840]) into the mm2 payload slots (the XOR-only
emit-side repack proven by gate v4, rel_l2 0.000242/0.000239/0.000243).
Biases are all-zero (verified: both shared FFN bias blobs absmax 0), so mm1
immediate / mm2 bias slots stay as minted. Every other byte is untouched.

Self-checks (fail loud, no partial output):
  A. template extraction == L00-f1 decoded real weights (layout validation
     against the certified template, shas in the palette-decode receipt)
  B. mint(L00-f1) is byte-identical to gate4's device-proven
     repacked-xor.anec (sha256 dc85fd12...)
  C. per-bundle extract-back == intended matrices, exact
  D. byte diff vs template confined to the mm1/mm2 payload regions
Emit: bundles/<name>/{manifest.json,program-0.anec} + mint.json records.
"""
import hashlib, json, shutil
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "weights"
TEMPLATE = Path("/tmp/chain-template.anec")
TPL_MANIFEST = Path("/tmp/chain-template-manifest.json")
GATE4_REPACK = Path("/tmp/gate4-repacked-xor.anec")  # fetched from jw16
OUT = HERE / "bundles"

BASE = 25728
MM1_STRIDE, MM1_HDR, MM1_BIAS = 32960, 128, 32
MM2_BASE = BASE + MM1_STRIDE * 256
XOR = 3840


def payload_collection_sha256(payloads):
    """Canonical identity from bundle_payload_identity.py / h13_package_to_bundle."""
    records = [{"role": p["role"], "path": p["path"], "byte_size": p["byte_size"],
                "sha256": p["sha256"]}
               for p in sorted(payloads, key=lambda p: p["path"])]
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

tpl_bytes = TEMPLATE.read_bytes()
assert hashlib.sha256(tpl_bytes).hexdigest() == \
    "e10db91639ab705509a0e586c017e7687ffb60f391289ace5605574d6382580b"


def extract(d):
    v = np.frombuffer(bytes(d), dtype="<u2")
    W1 = np.empty((4096, 1024), dtype=np.float32)
    for t in range(256):
        s = (BASE + t * MM1_STRIDE + MM1_HDR + MM1_BIAS) // 2
        blk = v[s:s + 16 * 1024].view("<f2").astype(np.float32).reshape(1024, 16)
        W1[16 * t:16 * (t + 1), :] = blk.T
    W2 = np.empty((1024, 4096), dtype=np.float32)
    for tt in range(160):
        s = (MM2_BASE + tt * 49216 + 12) // 2
        blk = v[s:s + 4096 * 6].view("<f2").astype(np.float32).reshape(4096, 6)
        for cc in range(6):
            W2[6 * tt + cc, :] = blk[:, cc]
    for j4 in range(16):
        s = (MM2_BASE + 160 * 49216 + j4 * 32832 + 8) // 2
        blk = v[s:s + 4096 * 4].view("<f2").astype(np.float32).reshape(4096, 4)
        for cc4 in range(4):
            W2[960 + 4 * j4 + cc4, :] = blk[:, cc4]
    return W1, W2


# ---- self-check A: template holds the L00-f1 decoded weights ----
w1_name = "encoder_layers_0_feed_forward1_linear1_weight_to_fp16_palettized"
w2_name = "encoder_layers_0_feed_forward1_linear2_weight_to_fp16_palettized"
W1_l00 = np.load(WEIGHTS / f"{w1_name}.npy").astype(np.float32)
W2_l00 = np.load(WEIGHTS / f"{w2_name}.npy").astype(np.float32)
tW1, tW2 = extract(tpl_bytes)
assert np.array_equal(tW1, W1_l00), "template mm1 payload != decoded W1"
assert np.array_equal(tW2, W2_l00), "template mm2 payload != decoded W2"
print("A: template extraction == L00-f1 decoded weights EXACT", flush=True)


def mint(W1, W2):
    """Write W1 into mm1 slots and W2[j, q^XOR] into mm2 slots of the template."""
    d = bytearray(tpl_bytes)
    v = np.frombuffer(d, dtype="<u2")  # writable view into d
    W2p = W2[:, np.arange(4096) ^ XOR]
    W1f = W1.astype(np.float16)
    W2pf = W2p.astype(np.float16)
    for t in range(256):
        s = (BASE + t * MM1_STRIDE + MM1_HDR + MM1_BIAS) // 2
        v[s:s + 16 * 1024] = W1f[16 * t:16 * (t + 1), :].T.reshape(-1).view("<u2")
    for tt in range(160):
        s = (MM2_BASE + tt * 49216 + 12) // 2
        v[s:s + 4096 * 6] = W2pf[6 * tt:6 * tt + 6, :].T.reshape(-1).view("<u2")
    for j4 in range(16):
        s = (MM2_BASE + 160 * 49216 + j4 * 32832 + 8) // 2
        v[s:s + 4096 * 4] = W2pf[960 + 4 * j4:960 + 4 * j4 + 4, :].T.reshape(-1).view("<u2")
    return d, W2p


# ---- self-check B: mint(L00-f1) == gate4 repacked-xor.anec ----
d00, _ = mint(W1_l00, W2_l00)
g4 = GATE4_REPACK.read_bytes()
assert hashlib.sha256(bytes(d00)).hexdigest() == hashlib.sha256(g4).hexdigest() == \
    "dc85fd1245c495a98031855dac7190a1e7c308efe4e4936bf123d8c7aceb309b", "check B FAIL"
print("B: mint(L00-f1) byte-identical to gate4 repacked-xor.anec", flush=True)

# ---- self-check D on L00: diff confined to payload regions ----
diff = np.frombuffer(bytes(d00), dtype=np.uint8) != np.frombuffer(tpl_bytes, dtype=np.uint8)
idx = np.nonzero(diff)[0]
mm1_lo = BASE + MM1_HDR + MM1_BIAS
mm1_hi = BASE + 256 * MM1_STRIDE
mm2_lo = MM2_BASE
mm2_hi = len(tpl_bytes)
assert idx.size and idx.min() >= mm1_lo and idx.max() < mm2_hi, \
    f"diff outside payload regions: {idx.min()}..{idx.max()}"
in_mm1 = idx[(idx >= mm1_lo) & (idx < mm2_lo)]
in_mm2 = idx[idx >= mm2_lo]
print(f"D: diff {idx.size} bytes (mm1 {in_mm1.size}, mm2 {in_mm2.size}), "
      f"confined to [{mm1_lo},{mm2_hi})", flush=True)

# ---- mint all 48 ----
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
tpl_manifest = json.loads(TPL_MANIFEST.read_text())
records = {}
for layer in range(24):
    for m in (1, 2):
        name = f"island-ffn-L{layer:02d}-f{m}"
        W1 = np.load(WEIGHTS / f"encoder_layers_{layer}_feed_forward{m}_linear1_weight_to_fp16_palettized.npy").astype(np.float32)
        W2 = np.load(WEIGHTS / f"encoder_layers_{layer}_feed_forward{m}_linear2_weight_to_fp16_palettized.npy").astype(np.float32)
        data, W2p = mint(W1, W2)
        # check C: extract-back exact (mm1 == W1, mm2 == W2perm)
        eW1, eW2 = extract(data)
        assert np.array_equal(eW1, W1), f"{name} extract-back W1 mismatch"
        assert np.array_equal(eW2, W2p), f"{name} extract-back W2perm mismatch"
        sha = hashlib.sha256(bytes(data)).hexdigest()
        bdir = OUT / name
        bdir.mkdir()
        (bdir / "program-0.anec").write_bytes(bytes(data))
        man = dict(tpl_manifest)
        man["name"] = name
        man["graph_hash"] = sha
        man["payloads"] = [dict(tpl_manifest["payloads"][0], sha256=sha)]
        # The worker validates release_asset.model_sha256 as the canonical
        # payload-collection identity (h13_package_to_bundle.py:676).
        man["release_asset"] = dict(tpl_manifest["release_asset"],
                                    model_sha256=payload_collection_sha256(man["payloads"]))
        (bdir / "manifest.json").write_text(json.dumps(man, indent=2) + "\n")
        records[name] = dict(
            program_sha256=sha,
            w1_sha256=hashlib.sha256(W1.astype(np.float16).tobytes()).hexdigest(),
            w2perm_sha256=hashlib.sha256(W2p.astype(np.float16).tobytes()).hexdigest(),
            extract_back="EXACT",
        )
        print(f"{name}: sha={sha[:12]} extract-back EXACT", flush=True)

json.dump(records, open(HERE / "mint.json", "w"), indent=1)
print(f"MINT PASS: {len(records)} bundles -> {OUT}", flush=True)
