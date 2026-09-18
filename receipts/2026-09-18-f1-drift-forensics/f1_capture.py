#!/usr/bin/env python3
"""F1 drift forensics: capture real conv-module boundary tensors on the GPU.

Encoder-runner wrapper for fused_e2e --no-ane: every conv statement that the
V family would place (pw1/pw2/dw, matched the same way vk_conv registers
them) dumps its input x and GPU output y as .npy under F1_CAP_DIR. Nothing is
modified; the run stays the certified all-GPU path.
"""
from __future__ import annotations
import importlib.util
import os
import re
from pathlib import Path

import numpy as np

_SPEC = importlib.util.spec_from_file_location(
    "vk_conv_orig", "/tmp/conv-lane/vk_conv.py")
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)
AneIsland = _mod.AneIsland

import mlx.core as mx

CAP = Path(os.environ["F1_CAP_DIR"])
CAP.mkdir(parents=True, exist_ok=True)
PW1 = re.compile(r"encoder_layers_(\d+)_conv_pointwise_conv1_weight_to_fp16")
PW2 = re.compile(r"encoder_layers_(\d+)_conv_pointwise_conv2_weight_to_fp16")


class EncoderRunner(_mod.EncoderRunner):
    def __init__(self, mil_path, model_root, island, placed=None):
        super().__init__(mil_path, model_root, island)
        self._pw2_seen = 0

    def apply(self, stmt):
        out = super().apply(stmt)
        try:
            if stmt.op == "conv" and stmt.shape is not None:
                wname = str(stmt.kwargs.get("weight", "")).strip().strip("'\"")
                wc = self.const_stmt.get(wname)
                if wc is not None and wc.shape is not None:
                    kind = layer = None
                    m = PW1.fullmatch(wname)
                    if m is not None and tuple(wc.shape) == (2048, 1024, 1):
                        kind, layer = "pw1", int(m.group(1))
                    else:
                        m = PW2.fullmatch(wname)
                        if m is not None and tuple(wc.shape) == (1024, 1024, 1):
                            kind, layer = "pw2", int(m.group(1))
                            self._pw2_seen += 1
                        elif tuple(wc.shape) == (1024, 1, 9):
                            kind = "dw"
                            if "bias" not in stmt.kwargs:
                                raise RuntimeError("dw conv without bias")
                            layer = self._pw2_seen
                    if kind is not None:
                        x = self.tensor(stmt.kwargs["x"])
                        mx.eval(x)
                        mx.eval(out)
                        np.save(CAP / f"{kind}-L{layer:02d}-x.npy", np.asarray(x))
                        np.save(CAP / f"{kind}-L{layer:02d}-y.npy", np.asarray(out))
        except Exception:
            raise
        return out
