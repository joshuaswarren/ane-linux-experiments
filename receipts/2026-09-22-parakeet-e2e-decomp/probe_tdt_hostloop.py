#!/usr/bin/env python3
"""Time the host-control TDT loop with/without silent-run batching.
Usage: probe_tdt_hostloop.py <encoder_hidden.npy> <model_dir> <iters> <batch_window or 0>
"""
import os, sys, time, statistics
from pathlib import Path
import numpy as np
import mlx.core as mx
from mlx.coreml import vulkan_decoder_step as vds
from mlx.coreml.parakeet_tdt import tdt_decode, DecoderStep, JointDecision
from mlx.coreml.vulkan_decoder import load_decoder

enc_path, model_dir, iters, win = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
encoder = np.load(enc_path).astype(np.float32)
enc = mx.array(encoder); mx.eval(enc)
M = model_dir
packed = vds.pack_step_weights(load_decoder(Path(M) / "decoder.mlpackage"), Path(M) / "joint.mlpackage")

class Cfg:
    blank_token_id = 8192
    durations = [0, 1, 2, 3, 4]
    max_symbols_per_step = 10
    vocab_size = 8193

def rd(tok, h, c):
    s, *_ = vds.run_step(packed, h, c, tok, enc, 0)
    mx.eval(s)
    return DecoderStep(s[0:640].reshape(1, 640), s[640:1920].reshape(2, 1, 640), s[1920:3200].reshape(2, 1, 640))

def rj(f, state):
    s, tok, dur, _, _ = vds.run_step(packed, None, None, 0, enc, f, skip_lstm=True, dec_in=state)
    return JointDecision(tok, dur)

def rjb(frames, state):
    return vds.run_joint_batch(packed, state, enc, frames)

h = mx.zeros((2, 1, 640)); c = mx.zeros((2, 1, 640)); mx.eval(h, c)
kw = dict(run_joint_batch=rjb) if win > 0 else {}
out = tdt_decode(packed=packed, encoder=enc, valid_frames=int(enc.shape[1]), config=Cfg,
                 initial_hidden=h, initial_cell=c, run_decoder=rd, run_joint=rj, **kw)
ref = (tuple(out.token_ids), tuple(out.frame_indices), tuple(out.durations))
ts = []
for i in range(iters):
    h = mx.zeros((2, 1, 640)); c = mx.zeros((2, 1, 640)); mx.eval(h, c)
    t = time.monotonic_ns()
    out = tdt_decode(packed=packed, encoder=enc, valid_frames=int(enc.shape[1]), config=Cfg,
                     initial_hidden=h, initial_cell=c, run_decoder=rd, run_joint=rj, **kw)
    ts.append((time.monotonic_ns() - t) / 1e6)
    assert (tuple(out.token_ids), tuple(out.frame_indices), tuple(out.durations)) == ref, "sequence drift"
print(f"window={win} tokens={len(out.token_ids)} steady_median_ms={round(statistics.median(ts[2:]),1)} ref_ok")
