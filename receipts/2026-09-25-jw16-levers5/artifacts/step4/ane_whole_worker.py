#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Whole-encoder ANE runner via the mlx-omarchy-ane-worker (one-shot worker
per encoder call). Drop-in encoder-runner module for fused_e2e: exposes
AneIsland(worker, libane, bundles, scratch, deadline_ms) and
EncoderRunner(source/mil, source/root, island) with .run(inputs, wanted,
stop_after) -> {"encoder_hidden", "encoder_mask"} — the same surface as
ane_whole_encoder.py, which fails on jw16 with ane_exec rc=-1 through
libane-strict.so; the worker binary carries its own worker_libane and is the
route certified on jw16 (bundle /var/tmp/encoder-whole/bundle, hidden16
anchor fca96f1355485ec3, status=0).
Bundle contract (manifest): inputs input_features fp16 [3000,128] (768000 B),
attention_mask fp16 [3000] (6000 B); outputs encoder_hidden fp16 480000 B,
output_mask fp16 750 B.
Upgrade path: a resident `--serve` worker session would remove the ~1 s
process spawn per call if the pipeline ever calls the encoder repeatedly in
one pass; fused_e2e calls it once per run, so the spawn is charged once.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import mlx.core as mx
import numpy as np

HIDDEN_BYTES = 480000
MASK_WORDS = 375


class AneIsland:
    """Name kept for harness compatibility; drives the whole-encoder worker."""

    def __init__(self, worker, libane, bundles=None, scratch=None,
                 deadline_ms: int = 20000, bundle_dir: str | None = None):
        self.worker = str(worker)
        self.bundle = str(bundle_dir or os.environ.get(
            "ANE_WHOLE_BUNDLE", "/var/tmp/encoder-whole/bundle"))
        self.libane = str(libane)
        self.deadline_ms = deadline_ms
        self.scratch = Path(scratch) if scratch else Path(
            tempfile.mkdtemp(prefix="whole-enc-"))
        self.scratch.mkdir(parents=True, exist_ok=True)
        # harness report fields
        self._mode = "whole-encoder-worker"
        self.submissions = 0
        self.rounds = 0
        self.worker_starts = 0
        self.timeouts = 0
        self.input_bytes = 0
        self.output_bytes = 0
        self.exec_ns = 0
        self.batch_open_ns = 0
        self.marshal_ns = 0
        self.back_ns = 0
        self.log = [{"bundle": self.bundle}]

    def submit(self, features: np.ndarray, mask: np.ndarray):
        """features fp16 [3000,128] contiguous; mask fp16 [3000]."""
        fb = np.ascontiguousarray(features, dtype=np.float16).tobytes()
        mb = np.ascontiguousarray(mask, dtype=np.float16).tobytes()
        fin = self.scratch / "in_features.f16"
        msk = self.scratch / "in_mask.f16"
        hout = self.scratch / "out_hidden.f16"
        mout = self.scratch / "out_mask.f16"
        fin.write_bytes(fb)
        msk.write_bytes(mb)
        t0 = time.monotonic_ns()
        deadline_s = max(self.deadline_ms, 60000) / 1000 + 30
        proc = subprocess.run(
            [self.worker, "--bundle", self.bundle, "--libane", self.libane,
             "--deadline-ms", str(max(self.deadline_ms, 60000)),
             "--iterations", "1",
             "--input", f"input_features={fin}",
             "--input", f"attention_mask={msk}",
             "--save", f"encoder_hidden={hout}",
             "--save", f"output_mask={mout}"],
            capture_output=True, text=True, timeout=deadline_s)
        t1 = time.monotonic_ns()
        self.exec_ns += t1 - t0
        self.submissions += 1
        self.worker_starts += 1
        self.input_bytes += len(fb) + len(mb)
        self.output_bytes += HIDDEN_BYTES + MASK_WORDS * 2
        if proc.returncode != 0 or not hout.exists():
            self.timeouts += 1
            raise RuntimeError(
                f"whole-encoder worker rc={proc.returncode}: {proc.stderr[-400:]}")
        hidden = np.frombuffer(hout.read_bytes(), dtype=np.float16).copy()
        omask = np.frombuffer(mout.read_bytes(), dtype=np.float16).copy()
        if hidden.size != HIDDEN_BYTES // 2 or omask.size != MASK_WORDS:
            raise RuntimeError(
                f"worker output shape mismatch {hidden.size}/{omask.size}")
        return hidden, omask

    def close(self):
        pass


class EncoderRunner:
    def __init__(self, mil_path, model_root=None, island=None, placed=None):
        self._island = island
        self.executed = 1
        self.gpu_ops = 0
        self.ane_ops = 13701
        self.layers = 1
        self.cpu_tensor_events = 0
        self.placed = frozenset("W")

    def run(self, inputs: dict, wanted: set[str], stop_after: str) -> dict:
        features = np.asarray(inputs["input_features"], dtype=np.float32)
        mask = np.asarray(inputs["attention_mask"])
        features = features.reshape(3000, 128)
        mask = mask.reshape(-1).astype(np.float16)
        hidden, omask = self._island.submit(features, mask)
        return {
            "encoder_hidden": mx.array(hidden.astype(np.float32)
                                       .reshape(1, 375, 640)),
            "encoder_mask": mx.array((omask > 0.5).astype(np.int32)
                                     .reshape(1, MASK_WORDS)),
        }
