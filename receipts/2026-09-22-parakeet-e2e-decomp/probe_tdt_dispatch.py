#!/usr/bin/env python3
"""Per-dispatch cost inside run_step: time each metal_kernel call separately.

Usage: probe_tdt_dispatch.py <encoder_hidden.npy> <model_dir> <iters>
"""
import sys, time, statistics
from pathlib import Path
import numpy as np
import mlx.core as mx
from mlx.coreml import vulkan_decoder_step as vds
from mlx.coreml.vulkan_decoder import load_decoder

enc_path, model_dir, iters = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
encoder = mx.array(np.load(enc_path).astype(np.float32))
mx.eval(encoder)
decoder = load_decoder(model_dir / "decoder.mlpackage")
packed = vds.pack_step_weights(decoder, model_dir / "joint.mlpackage")
hidden = mx.zeros((2, 1, 640), dtype=mx.float32)
cell = mx.zeros((2, 1, 640), dtype=mx.float32)
mx.eval(hidden, cell)
flat_hidden = hidden.reshape(1280,)
flat_cell = cell.reshape(1280,)
chains, fold, proj, joint = vds._chains_kernel(), vds._fold_kernel(), vds._proj_kernel(), vds._joint_kernel()

def timeit(fn, n):
    for _ in range(20): fn()
    xs = []
    for _ in range(n):
        t = time.monotonic_ns(); r = fn(); xs.append((time.monotonic_ns() - t) / 1e6)
    return r, xs

_, chains_t = timeit(lambda: chains(inputs=[packed.embedding, packed.weights, flat_hidden, mx.array(np.array([5,0],np.int32)), flat_hidden], output_shapes=[(25600,)], output_dtypes=[mx.float16], grid=(vds._CHAIN_GROUPS*vds._CHAIN_THREADS,1,1), threadgroup=(vds._CHAIN_THREADS,1,1), stream=mx.gpu)[0], iters)
bsum = _
_, fold_t = timeit(lambda: fold(inputs=[bsum, packed.biases, packed.luts, flat_cell, mx.array(np.array([0,0],np.int32))], output_shapes=[(640,),(640,),(1,)], output_dtypes=[mx.float32,mx.float32,mx.float32], grid=(640,1,1), threadgroup=(640,1,1), stream=mx.gpu), iters)
h1, c1, dbg = _
_, proj_t = timeit(lambda: proj(inputs=[h1, packed.projector, mx.array(np.array([3,0],np.int32))], output_shapes=[(640,),(640,),(1,)], output_dtypes=[mx.float32,mx.float16,mx.float32], grid=(640,1,1), threadgroup=(640,1,1), stream=mx.gpu), iters)
pj, pj16, dbg2 = _
_, joint_t = timeit(lambda: joint(inputs=[pj16, flat_hidden[:640], encoder.reshape(-1), mx.array(np.array([3,0],np.int32)), packed.joint], output_shapes=[(vds._JOINT_OUT,)], output_dtypes=[mx.float32], grid=(33*vds._JOINT_THREADS,1,1), threadgroup=(vds._JOINT_THREADS,1,1), stream=mx.gpu), iters)

def med(xs): return round(statistics.median(xs), 4)
print(f"chains_ms {med(chains_t)}  fold_ms {med(fold_t)}  proj_ms {med(proj_t)}  joint_ms {med(joint_t)}")
print(f"lstm_step = 2*chains + 2*fold + proj + joint = {round(2*med(chains_t)+2*med(fold_t)+med(proj_t)+med(joint_t),4)}")
# empty kernel dispatch floor
_, empty_t = timeit(lambda: mx.eval(mx.array(np.array([1], np.int32))), iters)
print(f"tiny_array_eval_ms {med(empty_t)}")
