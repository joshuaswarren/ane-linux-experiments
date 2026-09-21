# vulkan_encoder_basheval_wrapper.py — --encoder-runner drop-in that patches
# AneIsland._submit_resident's marshal loop to use ONE batched mx.eval per
# round instead of one mx.eval per input tensor.
#
# Current (base vulkan_encoder.py:789-793):
#     for name, value in inputs.items():
#         mx.eval(value)                                  # sync per input
#         raw = np.ascontiguousarray(np.asarray(value)).tobytes()
#
# Lever (this wrapper):
#     ordered = list(inputs.items())
#     mx.eval(*[v for _, v in ordered])                   # ONE sync for all
#     for name, value in ordered:
#         raw = np.ascontiguousarray(np.asarray(value)).tobytes()
#
# Rationale (measured): marshal_eval_ns is 46.03 ms/round (2209 ms/pass,
# 41.9% of stage), and the marshal-split receipt showed ~97% of it is
# mx.eval readiness wait. Each per-input mx.eval is a separate graph walk
# + GPU completion wait; batching evaluates the shared graph once and
# waits once. Byte semantics unchanged: np.asarray still converts the
# same evaluated values, output hashes must stay bit-exact (104/104 +
# three golden sha gates).
#
# Everything else (session submit, back conversion, counters, logs) is
# inherited from the base module unchanged. Env var LEVER_BATCH_EVAL=0
# disables the patch (pure base pass-through).

from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path

import numpy as np
import mlx.core as mx

_BASE_VULKAN = Path(os.environ.get(
    "BASE_VULKAN_ENCODER", "/var/tmp/encwall-v071/base/vulkan_encoder.py"))
spec = importlib.util.spec_from_file_location("_base_vulkan_encoder_basheval", str(_BASE_VULKAN))
_base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_base)

EncoderRunError = _base.EncoderRunError
EncoderRunner = _base.EncoderRunner
AneIsland = _base.AneIsland

if int(os.environ.get("LEVER_BATCH_EVAL", "1")):
    def batch_eval_submit_resident(self, bundle, tag, inputs, outputs):
        """Base _submit_resident with ONE batched mx.eval for all inputs."""
        session = self._ensure_session()
        payload = {}
        in_bytes = 0
        ordered = list(inputs.items())
        # LEVER: single graph evaluation + single sync for all inputs.
        mx.eval(*[value for _, value in ordered])
        for name, value in ordered:
            raw = np.ascontiguousarray(np.asarray(value)).tobytes()
            payload[name] = raw
            in_bytes += len(raw)
        out_names = list(outputs)
        started = time.monotonic_ns()
        try:
            results = session.submit(bundle, tag, payload, out_names)
        except Exception as error:
            raise EncoderRunError(
                f"ANE batch round {tag} ({bundle}) failed: {error}"
            ) from error
        elapsed = time.monotonic_ns() - started
        self.rounds += 1
        self.exec_ns += elapsed
        self.input_bytes += in_bytes
        record = {"tag": tag, "bundle": bundle, "elapsed_ns": elapsed, "round": True}
        out_bytes = 0
        packed = {}
        for name, (shape, dtype_name) in outputs.items():
            raw = results[name]
            count = 1
            for dim in shape:
                count *= dim
            expect = count * np.dtype(_base.NP_DTYPES[dtype_name]).itemsize
            if len(raw) != expect:
                raise EncoderRunError(
                    f"ANE output {name} for {tag} is {len(raw)} bytes, want {expect}"
                )
            out_bytes += len(raw)
            host = np.frombuffer(raw, dtype=_base.NP_DTYPES[dtype_name], count=count)
            packed[name] = mx.array(host).reshape(shape)
        record["input_bytes"] = in_bytes
        record["output_bytes"] = out_bytes
        self.output_bytes += out_bytes
        self.log.append(record)
        return packed

    AneIsland._submit_resident = batch_eval_submit_resident

# Re-export base symbols for fused_e2e import compatibility
for _k in _base.__dict__:
    if _k.startswith("_") or _k in globals():
        continue
    globals()[_k] = getattr(_base, _k)
