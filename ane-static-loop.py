#!/usr/bin/env python3
"""Run an ANEC static graph with resident state across iterations.

`ane_exec_loop` (patched libane) swaps the state input buffer object with the
state output buffer object between dispatches, so state stays resident on the
device instead of round-tripping through the host.

  python3 ane-static-loop.py model.ane [expected_value]
"""
import ctypes
import sys

import numpy as np
from ane import model

network = model(sys.argv[1], lib_path='/tmp/libane_python.so')
expected = float(sys.argv[2]) if len(sys.argv) > 2 else 24.0
network.driver.lib.pyane_exec_loop.argtypes = [
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
]
inputs = [
    np.full(network.src_nchw[0][:4], 3.0, dtype=np.float16),
    np.full(network.src_nchw[1][:4], 2.0, dtype=np.float16),
]
network.driver.lib.pyane_send(
    network.handle,
    *[value.tobytes(order='C') for value in inputs],
    *network.inputs_pad,
)
result = network.driver.lib.pyane_exec_loop(network.handle, 3, 0, 0)
network.driver.lib.pyane_read(
    network.handle,
    *network.outputs,
    *network.outputs_pad,
)
output = np.frombuffer(network.outputs[0], dtype=np.float16).reshape(*network.dst_nchw[0][:4])
print(f'exec_result={result} output_head={output.reshape(-1)[:16].tolist()}')
if result != 0 or not np.all(output == np.float16(expected)):
    raise SystemExit(1)
print('RESIDENT_STATE_LOOP_OK')
