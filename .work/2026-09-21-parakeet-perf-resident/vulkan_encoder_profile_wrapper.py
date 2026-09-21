# vulkan_encoder_profile_wrapper.py — drop-in for --encoder-runner.
# Imports the BASE vulkan_encoder.py, then monkey-patches AneIsland._submit_resident
# with the profiled version (uses ane_resident_profiled.ResidentAneWorker).
# Behavior is unchanged when ANE_RESIDENT_PROFILE is unset (default).
#
# Drop-in means fused_e2e.py can use this file as --encoder-runner and the
# EncoderRunner class is exported identically.

from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

import numpy as np
import mlx.core as mx

# Load the BASE vulkan_encoder.py first
_BASE_VULKAN = Path(os.environ.get("BASE_VULKAN_ENCODER", "/var/tmp/encwall-v071/base/vulkan_encoder.py"))
spec = importlib.util.spec_from_file_location("_base_vulkan_encoder", str(_BASE_VULKAN))
_base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_base)

# Re-export the symbols that fused_e2e.py looks for
EncoderRunError = _base.EncoderRunError
EncoderRunner = _base.EncoderRunner
AneIsland = _base.AneIsland

# If profiling is disabled, just expose the base and exit.
if not int(os.environ.get("ANE_RESIDENT_PROFILE", "0")):
    # Re-export everything the runner module normally exposes
    __all__ = ["EncoderRunError", "EncoderRunner", "AneIsland"]
    sys.modules["vulkan_encoder"] = _base  # alias
    # Make a fake module so `from vulkan_encoder import EncoderRunner` works
    class _ModuleProxy:
        EncoderRunError = EncoderRunError
        EncoderRunner = EncoderRunner
        AneIsland = AneIsland
    sys.modules[__name__] = _ModuleProxy()
    # Wait that's circular; instead, we just leave the symbols in this module.
    globals().update({k: v for k, v in _base.__dict__.items() if not k.startswith("_")})
    return_early = True
else:
    return_early = False


def _patch_anisland():
    """Replace AneIsland._submit_resident with a profiled version.

    The profiled version:
    - Uses ane_resident_profiled.ResidentAneWorker (same env-gated profile fields)
    - Times marshal (mx.eval + np.asarray + tobytes) per input
    - Times back conversion (np.frombuffer + mx.array().reshape) per output
    - Stores per-round record["profile"] dict
    """
    import importlib.util as _ilu
    profiled_resident_path = Path(__file__).resolve().parent / "ane_resident_profiled.py"
    spec2 = _ilu.spec_from_file_location("ane_resident_profiled", str(profiled_resident_path))
    arp = _ilu.module_from_spec(spec2)
    spec2.loader.exec_module(arp)

    NP_DTYPES = _base.NP_DTYPES

    def profiled_submit_resident(self, bundle, tag, inputs, outputs):
        # Mirror the BASE _submit_resident shape exactly, but with timing.
        session = self._ensure_session()
        payload = {}
        in_bytes = 0
        t_marshal = time.monotonic_ns()
        for name, value in inputs.items():
            mx.eval(value)
            raw = np.ascontiguousarray(np.asarray(value)).tobytes()
            payload[name] = raw
            in_bytes += len(raw)
        marshal_eval_ns = time.monotonic_ns() - t_marshal

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
        t_back = time.monotonic_ns()
        for name, (shape, dtype_name) in outputs.items():
            raw = results[name]
            count = 1
            for dim in shape:
                count *= dim
            expect = count * np.dtype(NP_DTYPES[dtype_name]).itemsize
            if len(raw) != expect:
                raise EncoderRunError(
                    f"ANE output {name} for {tag} is {len(raw)} bytes, want {expect}"
                )
            out_bytes += len(raw)
            host = np.frombuffer(raw, dtype=NP_DTYPES[dtype_name], count=count)
            packed[name] = mx.array(host).reshape(shape)
        back_conv_ns = time.monotonic_ns() - t_back

        record["input_bytes"] = in_bytes
        record["output_bytes"] = out_bytes
        record["profile"] = {
            "marshal_eval_ns": marshal_eval_ns,
            "session_round_ns": elapsed,
            "back_conv_ns": back_conv_ns,
            "sum_ns": marshal_eval_ns + elapsed + back_conv_ns,
            "session_profile": (
                session.log[-1].get("profile") if session.log else None
            ),
        }
        self.output_bytes += out_bytes
        self.log.append(record)
        return packed

    def profiled_ensure_session(self):
        if self._session is not None:
            return self._session
        # sys.path insert so ane_resident_profiled can be imported
        profiled_resident_path = Path(__file__).resolve().parent
        sys.path.insert(0, str(profiled_resident_path))
        started = time.monotonic_ns()
        session = arp.ResidentAneWorker(
            worker=Path(self.worker),
            libane=Path(self.libane),
            bundles={name: Path(self.bundles) / name for name in _base.RESIDENT_BUNDLES},
            scratch=Path(self.scratch),
            deadline_ms=self.deadline_ms,
        )
        session.start()
        session.begin_batch(self._batch_deadline_ms)
        self.batch_open_ns = time.monotonic_ns() - started
        self.worker_starts += 1
        self.submissions += 1
        self._session = session
        return session

    AneIsland._submit_resident = profiled_submit_resident
    AneIsland._ensure_session = profiled_ensure_session


if not return_early:
    _patch_anisland()

# Re-export base symbols for fused_e2e import compatibility
for _k in _base.__dict__:
    if _k.startswith("_") or _k in globals():
        continue
    globals()[_k] = getattr(_base, _k)
