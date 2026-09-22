#!/usr/bin/env python3
"""Decompose the Parakeet TDT decoder+joint per-step wall (run_step).

  full_lstm_ms   : run_step (LSTM path) incl. its mx.eval
  joint_only_ms  : run_step skip_lstm path incl. eval
  issue/eval_wait: how much of full_lstm is GPU-blocking vs host issue
  redundant_eval : the extra mx.eval(state_out) fused_e2e adds per callback
  flags4_ms      : the four mx.array(np.array(...)) flag vectors per step
Usage: probe_tdt_step.py <encoder_hidden.npy> <model_dir> <iters>
"""
import sys, time, statistics
from pathlib import Path
import numpy as np
import mlx.core as mx
from mlx.coreml.vulkan_decoder import load_decoder
from mlx.coreml.vulkan_decoder_step import pack_step_weights, run_step

enc_path, model_dir, iters = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
encoder = mx.array(np.load(enc_path).astype(np.float32))
mx.eval(encoder)
decoder = load_decoder(model_dir / "decoder.mlpackage")
packed = pack_step_weights(decoder, model_dir / "joint.mlpackage")

hidden = mx.zeros((2, 1, 640), dtype=mx.float32)
cell = mx.zeros((2, 1, 640), dtype=mx.float32)
mx.eval(hidden, cell)

def med(xs): return round(statistics.median(xs), 3)

state = hidden
full, joint, issue_l, eval_l, issue_j, eval_j, extra, flags = ([] for _ in range(8))
dec_in = hidden[0].reshape(1, 640)

for _ in range(iters):
    t = time.monotonic_ns()
    s, tok, dur, _, _ = run_step(packed, state, cell, 5, encoder, 3)
    issue_l.append((time.monotonic_ns() - t) / 1e6)
    t = time.monotonic_ns(); mx.eval(s)
    eval_l.append((time.monotonic_ns() - t) / 1e6)
    t = time.monotonic_ns(); mx.eval(s)
    extra.append((time.monotonic_ns() - t) / 1e6)
    full.append(issue_l[-1] + eval_l[-1])

for _ in range(iters):
    t = time.monotonic_ns()
    s, tok, dur, _, _ = run_step(packed, None, None, 0, encoder, 3,
                                 skip_lstm=True, dec_in=dec_in)
    issue_j.append((time.monotonic_ns() - t) / 1e6)
    t = time.monotonic_ns(); mx.eval(s)
    eval_j.append((time.monotonic_ns() - t) / 1e6)
    joint.append(issue_j[-1] + eval_j[-1])

for _ in range(iters):
    t = time.monotonic_ns()
    a = mx.array(np.array([5, 0], np.int32)); b = mx.array(np.array([0, 0], np.int32))
    c = mx.array(np.array([3, 0], np.int32)); d = mx.array(np.array([3, 0], np.int32))
    mx.eval(a, b, c, d)
    flags.append((time.monotonic_ns() - t) / 1e6)

print(f"iters={iters}")
print(f"full_lstm_ms    median={med(full)} mean={round(statistics.mean(full),3)}")
print(f"joint_only_ms   median={med(joint)} mean={round(statistics.mean(joint),3)}")
print(f"issue_lstm_ms   median={med(issue_l)}  eval_wait_lstm_ms median={med(eval_l)}")
print(f"issue_joint_ms  median={med(issue_j)}  eval_wait_joint_ms median={med(eval_j)}")
print(f"redundant_eval_ms median={med(extra)}")
print(f"flags4_ms       median={med(flags)}")
