#!/usr/bin/env python3
"""Make the minimal actual-runtime-change copy of vulkan_encoder.py.

Reads /var/tmp/encwall-v071/base/vulkan_encoder.py, applies the 3-line
batch-eval change to _submit_resident's marshal loop, writes
/tmp/parakeet-perf-resident/vulkan_encoder_batcheval_runtime.py plus a
unified diff .patch. This is the LAND form (minimal runtime change), as
distinct from the env-gated wrapper used for the A/B trials.
"""
from pathlib import Path

src = Path("/var/tmp/encwall-v071/base/vulkan_encoder.py")
out_py = Path("/tmp/parakeet-perf-resident/vulkan_encoder_batcheval_runtime.py")
out_patch = Path("/tmp/parakeet-perf-resident/vulkan_encoder_batcheval.patch")

text = src.read_text()
old = """        payload = {}
        in_bytes = 0
        marshal_started = time.monotonic_ns()
        for name, value in inputs.items():
            mx.eval(value)
            raw = np.ascontiguousarray(np.asarray(value)).tobytes()
            payload[name] = raw
            in_bytes += len(raw)"""
new = """        payload = {}
        in_bytes = 0
        marshal_started = time.monotonic_ns()
        ordered_inputs = list(inputs.items())
        # batch-eval: ONE graph walk + sync for all inputs instead of one
        # per tensor (measured: marshal segment is ~97% mx.eval readiness
        # wait; batching removes up to 144 redundant syncs per pass).
        mx.eval(*[value for _, value in ordered_inputs])
        for name, value in ordered_inputs:
            raw = np.ascontiguousarray(np.asarray(value)).tobytes()
            payload[name] = raw
            in_bytes += len(raw)"""
assert old in text, "anchor not found in base vulkan_encoder.py"
patched = text.replace(old, new, 1)
out_py.write_text(patched)

import difflib
diff = difflib.unified_diff(
    text.splitlines(keepends=True),
    patched.splitlines(keepends=True),
    fromfile="a/vulkan_encoder.py",
    tofile="b/vulkan_encoder_batcheval_runtime.py",
)
out_patch.write_text("".join(diff))

import hashlib
print("runtime copy sha256:", hashlib.sha256(out_py.read_bytes()).hexdigest())
print("patch lines:", len(out_patch.read_text().splitlines()))
