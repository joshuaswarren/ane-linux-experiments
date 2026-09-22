#!/usr/bin/env python3
"""Steady-state cost of the GPU-resident TDT loop (run_tdt_loop).
First call includes one-time kernel transpile/compile; subsequent calls
measure the real per-pipeline loop cost.
Usage: probe_tdt_loop.py <encoder_hidden.npy> <model_dir> <iters>
"""
import sys, time, statistics
from pathlib import Path
import numpy as np
import mlx.core as mx
from mlx.coreml.vulkan_decoder import load_decoder
from mlx.coreml import vulkan_decoder_step as vds
from mlx.coreml.vulkan_tdt_loop import run_tdt_loop
from mlx.coreml.parakeet_tdt import _validate, TdtConfig

enc_path, model_dir, iters = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
encoder = np.load(enc_path).astype(np.float32)
enc_mx = mx.array(encoder)
mx.eval(enc_mx)
decoder = load_decoder(model_dir / "decoder.mlpackage")
packed = vds.pack_step_weights(decoder, model_dir / "joint.mlpackage")

# TdtConfig from the reference lock via a shim object
class Cfg:
    blank_token_id = 8192
    durations = [0, 1, 2, 3, 4]
    max_symbols_per_step = 10
    vocab_size = 8193

n = encoder.shape[1]
times = []
out = None
for i in range(iters):
    t = time.monotonic_ns()
    out = run_tdt_loop(packed, enc_mx, n, Cfg, initial_hidden=None, initial_cell=None)
    d = (time.monotonic_ns() - t) / 1e6
    times.append(d)
print("tokens", out.token_ids[:8], "count", len(out.token_ids))
print("first_ms", round(times[0], 1), "second_ms", round(times[1], 1))
print("steady_median_ms", round(statistics.median(times[2:]), 1))
