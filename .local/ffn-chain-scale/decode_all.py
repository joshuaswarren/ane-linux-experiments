#!/usr/bin/env python3
"""Decode ALL 96 FFN weight tensors (24 layers x 2 modules x linear1/2) from
the pinned parakeet package palette blobs into dense fp16, with round-trip
proofs and sha records. Same byte-exact semantics as decode_palette.py
(L00-f1), generalized to every constexpr_lut_to_dense op feeding an FFN
linear weight. Also re-verifies the two shared FFN bias blobs are all-zero.
"""
import hashlib, json, struct
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PKG = Path.home() / ".cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018/encoder.mlpackage"
OUT = HERE / "weights"
OUT.mkdir(exist_ok=True)

# 2026-09-17 palette-decode receipt shas for L00-f1 (cross-check)
KNOWN = {
    "encoder_layers_0_feed_forward1_linear1_weight_to_fp16_palettized":
        "c9b4539c2b1d13eee4d251de248aba02bae66578ed70dc76944eb6c9548fb54c",
    "encoder_layers_0_feed_forward1_linear2_weight_to_fp16_palettized":
        "2f220ee1670ba4057bcb5109088dc3ce45071b6171767fb0064480271d95745c",
}

import sys
sys.path.insert(0, "/home/joshuawarren/src/ane-linux-experiments/.local/ane-ffn-wt/overlay/tools")
from coreml.proto import load_model
from coreml.depalettize import (
    read_blob_metadata, unpack_packed_uints, _blob_backed_tensor, _read_blob,
)

model = load_model((PKG / "Data/com.apple.CoreML/model.mlmodel").read_bytes())
program = model.mlProgram
weights_dir = PKG / "Data/com.apple.CoreML/weights"

results = {}
n_ops = 0
for name, function in sorted(program.functions.items()):
    for block in function.block_specializations.values():
        for op in block.operations:
            if op.type != "constexpr_lut_to_dense":
                continue
            out_name = op.outputs[0].name
            if "feed_forward" not in out_name or "_weight_" not in out_name:
                continue
            n_ops += 1
            indices_binding = op.inputs["indices"].arguments[0]
            lut_binding = op.inputs["lut"].arguments[0]
            i_dtype, i_shape, i_file, i_off = _blob_backed_tensor(indices_binding, out_name)
            l_dtype, l_shape, l_file, l_off = _blob_backed_tensor(lut_binding, out_name)
            assert i_dtype == 35 and l_dtype == 10, (i_dtype, l_dtype)
            assert len(i_shape) == 2, i_shape  # [4096,1024] or [1024,4096]

            idx_payload = _read_blob(weights_dir, i_file, i_off, out_name + ".indices")
            lut_payload = _read_blob(weights_dir, l_file, l_off, out_name + ".lut")
            idx_md = read_blob_metadata((weights_dir / i_file.split("/")[-1]).open("rb"), i_off)
            lut_md = read_blob_metadata((weights_dir / l_file.split("/")[-1]).open("rb"), l_off)
            assert idx_md.dtype_code == 11, idx_md.dtype_code
            assert len(lut_payload) == 2 * int(np.prod(l_shape)), (len(lut_payload), l_shape)

            nbits = 4
            elem = int(np.prod(i_shape))
            lut = np.frombuffer(lut_payload, dtype="<u2")
            assert lut.size == int(np.prod(l_shape)), (lut.size, l_shape)
            idx = unpack_packed_uints(idx_payload, nbits, elem).reshape(i_shape)
            assert idx.max() < (1 << nbits)

            num_pal = l_shape[-2]
            assert l_shape[-1] == 1 and len(l_shape) == len(i_shape) + 2
            pal = np.zeros(i_shape, dtype=np.int64)
            stride = num_pal
            for axis in reversed(range(len(i_shape))):
                blk = i_shape[axis] // l_shape[axis]
                coords = np.arange(i_shape[axis]) // blk
                pal += np.broadcast_to(
                    coords.reshape([-1 if a == axis else 1 for a in range(len(i_shape))]),
                    i_shape) * stride
                stride *= l_shape[axis]
            W = lut[pal.reshape(-1) + idx.reshape(-1)].reshape(i_shape).copy()

            # round-trip proof: re-pack indices + lut -> bit-identical blobs
            lo, hi = idx.reshape(-1)[0::2], idx.reshape(-1)[1::2]
            repacked = (lo | (hi << 4)).astype(np.uint8).tobytes()
            rt = (repacked == idx_payload[: len(repacked)]) and not any(idx_payload[len(repacked):])
            lut_rt = lut_payload == lut.tobytes()
            assert rt and lut_rt, f"round-trip FAIL {out_name}"

            sha = hashlib.sha256(W.tobytes()).hexdigest()
            ok = KNOWN.get(out_name)
            if ok:
                assert sha == ok, f"L00-f1 cross-check FAIL {out_name}: {sha} != {ok}"
            np.save(OUT / f"{out_name}.npy", W.view("<f2"))
            results[out_name] = dict(shape=list(W.shape), dense_sha256=sha,
                                     roundtrip=True)
            print(f"{out_name}: {W.shape} sha={sha[:12]} rt=EXACT", flush=True)

assert n_ops == 96, f"expected 96 FFN weight ops, got {n_ops}"

# shared FFN bias blobs: verify all-zero (linear_1_bias_0 [4096], linear_2_bias_0 [1024])
wb = (weights_dir / "weight.bin").read_bytes()
biases = {}
for tag, off, n in (("linear_1_bias_0_to_fp16", 4497472, 4096),
                    ("linear_2_bias_0_to_fp16", 6605056, 1024)):
    md = read_blob_metadata(__import__("io").BytesIO(wb), off)
    assert md.dtype_code == 1
    payload = wb[md.data_offset: md.data_offset + md.size_bytes]
    b = np.frombuffer(payload, dtype="<f2").astype(np.float32)
    amax = float(np.abs(b).max())
    assert amax == 0.0, f"{tag} NOT all-zero: absmax={amax}"
    biases[tag] = dict(absmax=amax, n=n)
    print(f"{tag}: absmax={amax} (all-zero, shared by all 96 sites)")

json.dump({"weights": results, "biases": biases}, open(HERE / "decode_all.json", "w"), indent=1)
print(f"DECODE PASS: {n_ops} weights + 2 zero biases -> {OUT}")
