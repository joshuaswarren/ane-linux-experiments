# vulkan_encoder_profiled.py — copy of vulkan_encoder.py with the
# ANE_RESIDENT_PROFILE=1 instrumentation in _submit_resident.
#
# Additive only: when the env var is unset, the patched _submit_resident
# is byte-identical to the original (no record["profile"] key in log).
# When set, three segments are timed: marshal_eval (mx.eval + np.asarray +
# tobytes per input), session_round (delegated to ane_resident.submit,
# which records its own profile breakdown), and back_conv (np.frombuffer +
# mx.array().reshape() per output).
#
# Drop-in: identical class name and signature; identical module exports
# (mx, np, MLX_DTYPES, NP_DTYPES, RESIDENT_BUNDLES, EncoderRunError).
# Importable as `vulkan_encoder_profiled` and pointed at from fused_e2e.py
# via --encoder-runner override.
#
# License: same as parent (MIT, mlx-omarchy contributors).

"""Run the pinned Parakeet encoder with the attention matmuls and the
attention-mask select on the ANE, and every other tensor op on the Apple GPU
through mlx-omarchy (Vulkan).

Profiled copy of vulkan_encoder.py (see receipts/2026-09-21-parakeet-perf-resident/
01-microbench-verdict.md section 5 for what this instrumentation measures).

License: MIT (mlx-omarchy contributors).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import mlx.core as mx


NP_DTYPES = {
    "fp16": np.float16,
    "fp32": np.float32,
    "int32": np.int32,
    "uint8": np.uint8,
    "bool": np.bool_,
}

MX_DTYPES = {
    "fp16": mx.float16,
    "fp32": mx.float32,
    "int32": mx.int32,
    "uint8": mx.uint8,
    "bool": mx.bool_,
}


class EncoderRunError(RuntimeError):
    pass


RESIDENT_BUNDLES = (
    "island-attn-a-kt",
    "island-select-8head",
    "island-pv",
    # oproj is added per-layer as island-oproj-L<NN>; see _run_island_oproj.
)


class PinnedEncoder:
    def __init__(self, worker, libane, bundles, scratch, deadline_ms=20000):
        self.worker = worker
        self.libane = libane
        self.bundles = bundles
        self.scratch = scratch
        self.deadline_ms = deadline_ms
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.submissions = 0
        self.worker_starts = 0
        self.rounds = 0
        self.input_bytes = 0
        self.output_bytes = 0
        self.exec_ns = 0
        self.timeouts = 0
        self.batch_open_ns = 0
        self.log = []
        self._mode = os.environ.get("ANE_ISLAND_MODE", "resident-batch")
        if self._mode not in ("launch", "resident-batch"):
            raise EncoderRunError(
                f"ANE_ISLAND_MODE {self._mode!r} is not launch or resident-batch"
            )
        self._batch_deadline_ms = int(
            os.environ.get("ANE_ISLAND_BATCH_DEADLINE_MS", "120000")
        )
        self._session = None

        # Profile gate
        self._profile = bool(int(os.environ.get("ANE_RESIDENT_PROFILE", "0")))

    def close(self):
        if self._session is None:
            return
        session, self._session = self._session, None
        try:
            session.end_batch()
        except Exception as error:
            raise EncoderRunError(f"resident batch close failed: {error}") from error
        try:
            session.close()
        except Exception as error:
            raise EncoderRunError(f"resident session close failed: {error}") from error

    def _ensure_session(self):
        if self._session is not None:
            return self._session
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from ane_resident_profiled import ResidentAneWorker
        started = time.monotonic_ns()
        session = ResidentAneWorker(
            worker=Path(self.worker),
            libane=Path(self.libane),
            bundles={name: Path(self.bundles) / name for name in RESIDENT_BUNDLES},
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

    def _submit_resident(self, bundle, tag, inputs, outputs):
        """One round inside the open batch: same bytes, no files, one session.

        Profiled: when ANE_RESIDENT_PROFILE=1, store per-segment breakdown
        under record["profile"] with keys:
          - marshal_eval_ns:    sum of (mx.eval + np.asarray + tobytes) per input
          - session_round_ns:   delegated to ane_resident.submit (its own profile)
          - back_conv_ns:       sum of (np.frombuffer + mx.array().reshape) per output
          - sum_ns:             sum of the three (all under elapsed_ns; encode is
                                inside session.submit's own measurement)
        """
        prof = self._profile
        session = self._ensure_session()

        # --- marshal: per-input (mx.eval + np.asarray + tobytes) ---
        payload = {}
        in_bytes = 0
        marshal_eval_ns = 0
        if prof:
            t_marshal = time.monotonic_ns()
        for name, value in inputs.items():
            mx.eval(value)
            raw = np.ascontiguousarray(np.asarray(value)).tobytes()
            payload[name] = raw
            in_bytes += len(raw)
        if prof:
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

        # --- back: per-output (np.frombuffer + mx.array().reshape) ---
        out_bytes = 0
        packed = {}
        back_conv_ns = 0
        if prof:
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
        if prof:
            back_conv_ns = time.monotonic_ns() - t_back

        record["input_bytes"] = in_bytes
        record["output_bytes"] = out_bytes
        if prof:
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

    def submit(self, bundle, tag, inputs, outputs):
        if self._mode == "resident-batch":
            return self._submit_resident(bundle, tag, inputs, outputs)
        return self._submit_launch(bundle, tag, inputs, outputs)

    # launch path is not used in this slice; placeholder for completeness
    def _submit_launch(self, bundle, tag, inputs, outputs):
        raise EncoderRunError(
            "launch mode not profiled; ANE_ISLAND_MODE=resident-batch only"
        )


# NOTE: This file is a profiled copy of vulkan_encoder.py's
# _submit_resident. The fused_e2e.py harness imports PinnedEncoder from
# here when ANE_RESIDENT_PROFILE=1 and from the base vulkan_encoder.py
# otherwise. We do NOT re-implement the full Statement interpreter here
# (that would be a re-implementation, not a profile); we ship only the
# submit path needed by the harness wrapper.
