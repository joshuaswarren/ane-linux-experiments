#!/usr/bin/env python3
"""Compose Qwen full-attention and recurrent state on Linux ANE."""

import contextlib
import importlib.util
import io
import os
import runpy
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
CONTEXT = 128
ATTENTION_DIMENSION = 256
QUERY_HEADS = 8
KV_HEADS = 2
QUERY_GROUP_SIZE = QUERY_HEADS // KV_HEADS
RECURRENT_HEADS = 16
CONVOLUTION_CHANNELS = 6144
CONVOLUTION_KERNEL_SIZE = 4
RECURRENT_DIMENSION = 128


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ATTENTION = load_module("attention_runtime", ROOT / "attention-runtime.py")
SOFTMAX = load_module("softmax_runtime", ROOT / "softmax-runtime.py")
RECURRENT = load_module("recurrent_runtime", ROOT / "recurrent-runtime.py")


def harvest_elementwise_descriptors(path):
    with contextlib.redirect_stdout(io.StringIO()):
        namespace = runpy.run_path(path, run_name="qwen_elementwise_harvest")
    os.close(namespace["fd"])
    return namespace["_descriptors"]


class QwenTokenRuntime:
    """Own bounded ANE state for every Qwen attention and recurrent layer."""

    def __init__(
        self,
        device,
        descriptor,
        elementwise_descriptors,
        recurrent_artifact,
        full_layers,
        recurrent_layers,
    ):
        if full_layers < 0 or recurrent_layers < 0:
            raise ValueError("layer counts must be non-negative")
        self.closed = False
        self.programs = []
        self.attention_states = []
        self.recurrent_runners = []
        self.convolutions = []
        try:
            self.elementwise = SOFTMAX.ElementwiseBackend(
                device, elementwise_descriptors
            )
            self.softmax = SOFTMAX.Softmax128(self.elementwise)
            self.normalization = SOFTMAX.Normalization(self.elementwise)
            self.activations = SOFTMAX.Activations(self.elementwise)
            for _ in range(recurrent_layers):
                self.convolutions.append(
                    SOFTMAX.CausalConvolution(
                        self.elementwise,
                        channels=CONVOLUTION_CHANNELS,
                        kernel_size=CONVOLUTION_KERNEL_SIZE,
                    )
                )
            for _ in range(full_layers):
                layer_states = []
                for _ in range(KV_HEADS):
                    score = ATTENTION.MutableGemm(device, descriptor, CONTEXT)
                    self.programs.append(score)
                    value = ATTENTION.MutableGemm(
                        device, descriptor, ATTENTION_DIMENSION
                    )
                    self.programs.append(value)
                    layer_states.append(
                        ATTENTION.AttentionGemmState(
                            score,
                            value,
                            context=CONTEXT,
                            dimension=ATTENTION_DIMENSION,
                        )
                    )
                self.attention_states.append(layer_states)
            initial_state = np.zeros(
                (RECURRENT_HEADS, RECURRENT_DIMENSION, RECURRENT_DIMENSION),
                dtype=np.float16,
            )
            for _ in range(recurrent_layers):
                runner = RECURRENT.RecurrentRunner(
                    recurrent_artifact, device=device
                )
                self.recurrent_runners.append(runner)
                runner.initialize(initial_state)
        except BaseException:
            self.close()
            raise
        self._attention_scale = np.full(
            SOFTMAX.LANES, np.float16(1.0 / 16.0), dtype=np.float16
        )

    def full_attention(self, layer_index, query, key, value):
        self._ensure_open()
        query = self._require(
            query, (QUERY_HEADS, ATTENTION_DIMENSION), "query"
        )
        key = self._require(key, (KV_HEADS, ATTENTION_DIMENSION), "key")
        value = self._require(value, (KV_HEADS, ATTENTION_DIMENSION), "value")
        states = self.attention_states[layer_index]
        for kv_head, state in enumerate(states):
            state.append(key[kv_head], value[kv_head])
        attended = np.empty_like(query)
        for query_head in range(QUERY_HEADS):
            state = states[query_head // QUERY_GROUP_SIZE]
            scores = state.scores(query[query_head])
            scaled = np.empty_like(scores)
            scaled[: SOFTMAX.LANES] = self.elementwise(
                "mul", scores[: SOFTMAX.LANES], self._attention_scale
            )
            scaled[SOFTMAX.LANES :] = self.elementwise(
                "mul", scores[SOFTMAX.LANES :], self._attention_scale
            )
            attended[query_head] = state.attend(self.softmax(scaled))
        return attended

    def causal_convolution(self, layer_index, value, weight):
        self._ensure_open()
        return self.convolutions[layer_index](value, weight)

    def rms_norm(self, value, weight):
        self._ensure_open()
        return self.normalization.rms_norm(value, weight)

    def l2_norm(self, value, scale=1.0):
        self._ensure_open()
        return self.normalization.l2_norm(value, scale)

    def sigmoid(self, value):
        self._ensure_open()
        return self.activations.sigmoid(value)

    def sigmoid_mul(self, value, multiplier):
        self._ensure_open()
        return self.activations.sigmoid_mul(value, multiplier)

    def silu(self, value):
        self._ensure_open()
        return self.activations.silu(value)

    def silu_mul(self, value, multiplier):
        self._ensure_open()
        return self.activations.silu_mul(value, multiplier)

    def decay_multiplier(self, alpha, bias, a_log):
        self._ensure_open()
        return self.activations.decay_multiplier(alpha, bias, a_log)

    def recurrent(self, layer_index, query, key, value, beta, decay):
        self._ensure_open()
        vector_shape = (RECURRENT_HEADS, RECURRENT_DIMENSION)
        gate_shape = (RECURRENT_HEADS,)
        query = self._require(query, vector_shape, "query")
        key = self._require(key, vector_shape, "key")
        value = self._require(value, vector_shape, "value")
        beta = self._require(beta, gate_shape, "beta")
        decay = self._require(decay, gate_shape, "decay")
        return self.recurrent_runners[layer_index].step(
            query, key, value, beta, decay
        )

    def _ensure_open(self):
        if self.closed:
            raise RuntimeError("Qwen token runtime is closed")

    @staticmethod
    def _require(value, shape, name):
        value = np.asarray(value)
        if value.dtype != np.float16 or value.shape != shape:
            raise ValueError(
                f"{name} shape and dtype must be {shape} float16, "
                f"got {value.shape} {value.dtype}"
            )
        return value

    def close(self):
        if self.closed:
            return
        for runner in self.recurrent_runners:
            runner.close()
        for program in self.programs:
            program.close()
        elementwise = getattr(self, "elementwise", None)
        if elementwise is not None:
            elementwise.close()
        self.closed = True


if __name__ == "__main__":
    raise SystemExit("import QwenTokenRuntime from this file")
