#!/usr/bin/env python3
"""Per-kernel GPU time inside the LSTM step (eval after each dispatch).
Usage: probe_tdt_gpukernel.py <encoder_hidden.npy> <model_dir> <iters>
"""
import sys, time, statistics
from pathlib import Path
import numpy as np
import mlx.core as mx
from mlx.coreml.vulkan_decoder import load_decoder
from mlx.coreml import vulkan_decoder_step as vds

enc_path, model_dir, iters = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
encoder = mx.array(np.load(enc_path).astype(np.float32))
mx.eval(encoder)
decoder = load_decoder(model_dir / "decoder.mlpackage")
packed = vds.pack_step_weights(decoder, model_dir / "joint.mlpackage")
hidden = mx.zeros((2, 1, 640), dtype=mx.float32)
cell = mx.zeros((2, 1, 640), dtype=mx.float32)
mx.eval(hidden, cell)
chains, fold, proj, joint = vds._chains_kernel(), vds._fold_kernel(), vds._proj_kernel(), vds._joint_kernel()
flat_hidden = hidden.reshape(1280,)
flat_cell = cell.reshape(1280,)
T = {}
def tick(k, t0):
    t = time.monotonic_ns()
    T.setdefault(k, []).append((t - t0) / 1e6)
    return t

def per_kernel(token_id, frame):
    t = time.monotonic_ns()
    bsums, h1s, c1s = [], [], []
    for layer in (0, 1):
        flags_c = mx.array(np.array([int(token_id), layer], np.int32))
        x_in = flat_hidden if layer == 0 else h1s[0]
        bsum, = chains(
            inputs=[packed.embedding, packed.weights, flat_hidden, flags_c, x_in],
            output_shapes=[(25600,)], output_dtypes=[mx.float16],
            grid=(vds._CHAIN_GROUPS * vds._CHAIN_THREADS, 1, 1),
            threadgroup=(vds._CHAIN_THREADS, 1, 1), stream=mx.gpu)
        mx.eval(bsum)
        t = tick(f"chains{layer}", t)
        flags_f = mx.array(np.array([layer, 0], np.int32))
        h1, c1, dbg = fold(
            inputs=[bsum, packed.biases, packed.luts, flat_cell, flags_f],
            output_shapes=[(640,), (640,), (1,)],
            output_dtypes=[mx.float32, mx.float32, mx.float32],
            grid=(640, 1, 1), threadgroup=(640, 1, 1), stream=mx.gpu)
        mx.eval(h1, c1)
        t = tick(f"fold{layer}", t)
        h1s.append(h1); c1s.append(c1)
    flags_p = mx.array(np.array([int(frame), 0], np.int32))
    pj, pj16, dbg2 = proj(
        inputs=[h1s[1], packed.projector, flags_p],
        output_shapes=[(640,), (640,), (1,)],
        output_dtypes=[mx.float32, mx.float16, mx.float32],
        grid=(640, 1, 1), threadgroup=(640, 1, 1), stream=mx.gpu)
    mx.eval(pj)
    t = tick("proj", t)
    flagsj = mx.array(np.array([int(frame), 0], np.int32))
    (logits,) = joint(
        inputs=[pj16, flat_hidden[:640], encoder.reshape(-1), flagsj, packed.joint],
        output_shapes=[(vds._JOINT_OUT,)], output_dtypes=[mx.float32],
        grid=(33 * vds._JOINT_THREADS, 1, 1), threadgroup=(vds._JOINT_THREADS, 1, 1),
        stream=mx.gpu)
    mx.eval(logits)
    tick("joint", t)

for _ in range(20):
    per_kernel(5, 3)
T.clear()
for i in range(iters):
    per_kernel(5 + (i % 4), 3)
for k in ("chains0", "fold0", "chains1", "fold1", "proj", "joint"):
    print(k, round(statistics.median(T[k]), 4))
