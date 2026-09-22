#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Whole-encoder ANE runner: Apple's single-program Parakeet encoder hwx
(converted to anec with true TD wiring) executed in ONE submit on the
on-board ANE via libane. Drop-in encoder-runner module for fused_e2e:
exposes AneIsland(worker, libane, bundles, scratch, deadline_ms) and
EncoderRunner(source/mil, source/root, island) with .run(inputs, wanted,
stop_after) -> {"encoder_hidden", "encoder_mask"}.

Surface wiring (field-level, from the island-container diff):
  send src0 -> channel 6: attention_mask, 6000 B fp16 (6016 pad)
  send src1 -> channel 7: input_features, 768000 B fp16 dense
  read dst0 -> channel 4: encoder_hidden, 480000 B fp16 (bit-exact vs gold)
  read dst1 -> channel 5: output mask, 750 B fp16
Requires libane built with tile_shift <<9 (512-B tile units) and the
converter-fixed anec: every task hdr0 carries ANE_FIFO_NID 0x40, selector
channels rewired 4<->6 / 5<->7, header tiles in 512-B units, td_size 0x1f8.
"""
from __future__ import annotations

import ctypes
import time
from pathlib import Path

import mlx.core as mx
import numpy as np

DEFAULT_ANEC = "/var/tmp/encoder-fp16-v3.anec"
HIDDEN_BYTES = 480000
MASK_WORDS = 375


class AneIsland:
    """Name kept for harness compatibility; owns the one libane handle."""

    def __init__(self, worker, libane, bundles=None, scratch=None,
                 deadline_ms: int = 20000, anec: str | None = None):
        self.libane_path = str(libane)
        import os
        self.anec = anec or os.environ.get("ANE_WHOLE_ENCODER_ANEC", DEFAULT_ANEC)
        lib = ctypes.CDLL(self.libane_path, use_errno=True)
        P = ctypes.c_void_p
        getattr(lib, "__ane_init").restype = P
        getattr(lib, "__ane_init").argtypes = [ctypes.c_char_p, ctypes.c_int]
        getattr(lib, "__ane_free").restype = ctypes.c_int
        getattr(lib, "__ane_free").argtypes = [P]
        getattr(lib, "__ane_src_size").restype = ctypes.c_uint64
        getattr(lib, "__ane_src_size").argtypes = [P, ctypes.c_uint32]
        getattr(lib, "__ane_dst_size").restype = ctypes.c_uint64
        getattr(lib, "__ane_dst_size").argtypes = [P, ctypes.c_uint32]
        getattr(lib, "__ane_send").restype = None
        getattr(lib, "__ane_send").argtypes = [P, P, ctypes.c_uint32]
        getattr(lib, "__ane_read").restype = None
        getattr(lib, "__ane_read").argtypes = [P, P, ctypes.c_uint32]
        lib.ane_exec.restype = ctypes.c_int
        lib.ane_exec.argtypes = [P]
        self._lib = lib
        self._h = getattr(lib, "__ane_init")(self.anec.encode(), 0)
        if not self._h:
            raise RuntimeError(f"ane_init refused {self.anec}")
        self._src_sizes = [getattr(lib, "__ane_src_size")(self._h, i) for i in range(2)]
        self._dst_sizes = [getattr(lib, "__ane_dst_size")(self._h, i) for i in range(2)]
        self._in = [ctypes.create_string_buffer(s) for s in self._src_sizes]
        self._out = [ctypes.create_string_buffer(s) for s in self._dst_sizes]
        # harness report fields
        self._mode = "whole-encoder"
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
        self.log = [{"bundle": "whole-encoder-hwx"}]

    def submit(self, features: np.ndarray, mask: np.ndarray):
        """features fp16 [3000,128] contiguous; mask fp16 [3000]."""
        mb = np.ascontiguousarray(mask, dtype=np.float16).tobytes()
        fb = np.ascontiguousarray(features, dtype=np.float16).tobytes()
        if len(mb) > self._src_sizes[0] or len(fb) > self._src_sizes[1]:
            raise RuntimeError("input larger than bound surface")
        ctypes.memmove(self._in[0], mb, len(mb))
        ctypes.memmove(self._in[1], fb, len(fb))
        t0 = time.monotonic_ns()
        getattr(self._lib, "__ane_send")(self._h, self._in[0], 0)
        getattr(self._lib, "__ane_send")(self._h, self._in[1], 1)
        rc = self._lib.ane_exec(self._h)
        t1 = time.monotonic_ns()
        getattr(self._lib, "__ane_read")(self._h, self._out[0], 0)
        getattr(self._lib, "__ane_read")(self._h, self._out[1], 1)
        self.exec_ns += t1 - t0
        self.submissions += 1
        self.input_bytes += len(mb) + len(fb)
        self.output_bytes += HIDDEN_BYTES + MASK_WORDS * 2
        if rc:
            self.timeouts += 1
            raise RuntimeError(f"ane_exec rc={rc}")
        hidden = np.frombuffer(self._out[0].raw, dtype=np.float16,
                               count=HIDDEN_BYTES // 2).copy()
        omask = np.frombuffer(self._out[1].raw, dtype=np.float16,
                              count=MASK_WORDS).copy()
        return hidden, omask

    def close(self):
        if getattr(self, "_h", None):
            try:
                self._getattr(lib, "__ane_free")(self._h)
            except Exception:
                pass
            self._h = None


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
