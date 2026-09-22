#!/usr/bin/env python3
"""cProfile run_step to find where the ~2.3 ms/call host wall goes.
Usage: probe_tdt_cprof.py <encoder_hidden.npy> <model_dir> <iters>
"""
import cProfile, io, pstats, sys
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
for _ in range(20):
    run_step(packed, hidden, cell, 5, encoder, 3)

pr = cProfile.Profile()
pr.enable()
for i in range(iters):
    run_step(packed, hidden, cell, 5 + (i % 4), encoder, 3)
pr.disable()
s = io.StringIO()
pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(18)
print(s.getvalue())
