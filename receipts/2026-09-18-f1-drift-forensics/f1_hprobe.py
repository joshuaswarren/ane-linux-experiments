#!/usr/bin/env python3
"""F1 drift forensics: decode-probe encoder runner for fused_e2e.

Bypasses the encoder entirely and returns a prepared hidden (built by
f1_prep_probes.py) so fused_e2e exercises only the decoder path. Diagnostic
only -- never ships. F1_HIDDEN selects the hidden .npy; the encoder mask is
passed through from the mel stage unchanged.
"""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path

import numpy as np

import mlx.core as mx

_SPEC = importlib.util.spec_from_file_location(
    "vk_conv_orig", "/tmp/conv-lane/vk_conv.py")
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)
AneIsland = _mod.AneIsland


class EncoderRunner(_mod.EncoderRunner):
    def __init__(self, mil_path, model_root, island, placed=None):
        super().__init__(mil_path, model_root, island)
        self._probe_hidden = np.load(Path(os.environ["F1_HIDDEN"]))

    def run(self, inputs: dict, wanted: set, stop_after: str) -> dict:
        return {
            "encoder_hidden": mx.array(self._probe_hidden),
            "encoder_mask": inputs["attention_mask"],
        }
