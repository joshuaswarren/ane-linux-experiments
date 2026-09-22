#!/usr/bin/env python3
"""A/B bitwise + speed check: stock vulkan_decoder_step vs _fast variant.
Compares LSTM-path and joint-path outputs bit-for-bit over random tokens
and frames, and reports medians.
Usage: probe_tdt_ab.py <encoder_hidden.npy> <model_dir> <iters>
"""
import importlib.util, statistics, sys, time
from pathlib import Path
import numpy as np
import mlx.core as mx
from mlx.coreml.vulkan_decoder import load_decoder

enc_path, model_dir, iters = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])

from mlx.coreml import vulkan_decoder_step as base
from mlx.coreml import vulkan_decoder_step_fast as fast

encoder = mx.array(np.load(enc_path).astype(np.float32))
mx.eval(encoder)
nframes = encoder.shape[1]
pb = base.pack_step_weights(load_decoder(model_dir / "decoder.mlpackage"), model_dir / "joint.mlpackage")
pf = fast.pack_step_weights(load_decoder(model_dir / "decoder.mlpackage"), model_dir / "joint.mlpackage")
hidden = mx.zeros((2, 1, 640), dtype=mx.float32)
cell = mx.zeros((2, 1, 640), dtype=mx.float32)
mx.eval(hidden, cell)

rng = np.random.default_rng(7)
bad = 0
tb, tf = [], []
for _ in range(20):  # warm both
    base.run_step(pb, hidden, cell, 5, encoder, 3)
    fast.run_step(pf, hidden, cell, 5, encoder, 3)
for i in range(iters):
    tok = int(rng.integers(0, 8193)); fr = int(rng.integers(0, nframes))
    sb, tokb, durb, lb, _ = base.run_step(pb, hidden, cell, tok, encoder, fr)
    sf, tokf, durf, lf, _ = fast.run_step(pf, hidden, cell, tok, encoder, fr)
    if not (np.array_equal(np.asarray(sb), np.asarray(sf)) and np.array_equal(np.asarray(lb), np.asarray(lf)) and tokb == tokf and durb == durf):
        bad += 1
    if i >= iters - 60:
        t = time.monotonic_ns()
        base.run_step(pb, hidden, cell, tok, encoder, fr)
        tb.append((time.monotonic_ns() - t) / 1e6)
        t = time.monotonic_ns()
        fast.run_step(pf, hidden, cell, tok, encoder, fr)
        tf.append((time.monotonic_ns() - t) / 1e6)
    # joint-only path
    if i % 3 == 0:
        tok = int(rng.integers(0, 8193)); fr = int(rng.integers(0, nframes))
        sb, tokb, durb, lb, _ = base.run_step(pb, None, None, 0, encoder, fr, skip_lstm=True, dec_in=hidden[0].reshape(1, 640))
        sf, tokf, durf, lf, _ = fast.run_step(pf, None, None, 0, encoder, fr, skip_lstm=True, dec_in=hidden[0].reshape(1, 640))
        if not (np.array_equal(np.asarray(sb), np.asarray(sf)) and np.array_equal(np.asarray(lb), np.asarray(lf)) and tokb == tokf and durb == durf):
            bad += 1

med = lambda xs: round(statistics.median(xs), 3)
print(f"bitwise_mismatches={bad}/{iters}")
print(f"lstm_stock_ms={med(tb)} lstm_fast_ms={med(tf)}")
