#!/usr/bin/env python3
"""Run a complete one-token Qwen3.8-2B forward pass with ANE linear layers.

This is the first end-to-end model path in this work. It loads the selected
Qwen3.8-2B Q4_K_M GGUF, dequantizes each tensor, sends every linear projection
through the ANE 512x256 runtime, keeps Gated DeltaNet recurrent state and
full-attention K/V state across tokens, computes the remaining elementwise
operations on the CPU, and produces output logits from the tied embedding.

The CPU operations are explicit. They cover RMSNorm, depthwise causal
convolution, sigmoid/SiLU, RoPE, delta-rule recurrence, causal softmax, and
the final logits dot product. This is a working correctness path, not a
claim that every non-linear primitive has already moved to the ANE.

  python3 ane-qwen-model.py -m Qwen3.8-2B-Q4_K_M.gguf -p "The engine runs"
"""
import argparse
import importlib.util
import os

import numpy as np



def load(name):
    path = os.path.join(os.path.dirname(__file__), name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sigmoid(x):
    x = np.clip(x.astype(np.float32), -80.0, 80.0)
    return (1.0 / (1.0 + np.exp(-x))).astype(np.float16)


def silu(x):
    x = x.astype(np.float32)
    return (x / (1.0 + np.exp(-np.clip(x, -80.0, 80.0)))).astype(np.float16)


def rms_norm(x, weight, eps=1e-6):
    x32 = x.astype(np.float32)
    return (x32 * (1.0 / np.sqrt(np.mean(x32 * x32) + eps)) * weight.astype(np.float32)).astype(np.float16)


def l2_norm(x, eps=1e-6):
    x32 = x.astype(np.float32)
    return (x32 / np.sqrt(np.sum(x32 * x32, axis=-1, keepdims=True) + eps)).astype(np.float16)


def rope(x, position, rotary_dim=64, theta=10_000_000.0):
    out = x.astype(np.float32).copy()
    inv = theta ** (-np.arange(0, rotary_dim, 2, dtype=np.float32) / rotary_dim)
    angles = position * inv
    cos, sin = np.cos(angles), np.sin(angles)
    even = out[:, :rotary_dim:2].copy()
    odd = out[:, 1:rotary_dim:2].copy()
    out[:, :rotary_dim:2] = even * cos - odd * sin
    out[:, 1:rotary_dim:2] = even * sin + odd * cos
    return out.astype(np.float16)

class NumpyDevice:
    """Reference backend using the same canonical matrices on the CPU."""

    def __init__(self, **_):
        pass

    def gemm(self, weights, activation, _descriptor):
        return weights.astype(np.float32) @ activation.astype(np.float32)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def causal_attention(q, keys, values):
    q32 = q.astype(np.float32)
    key32 = np.repeat(keys.astype(np.float32), 4, axis=0)
    value32 = np.repeat(values.astype(np.float32), 4, axis=0)
    score = np.einsum("hd,htd->ht", q32, key32) / np.sqrt(256.0)
    score -= score.max(axis=1, keepdims=True)
    prob = np.exp(score)
    prob /= prob.sum(axis=1, keepdims=True)
    return np.einsum("ht,htd->hd", prob, value32).astype(np.float16)


class QwenModel:
    """Qwen3.5 hybrid model with ANE-backed linear projections."""

    def __init__(self, model_path, gguf_py, runtime, weights, descriptor, qid):
        self.weights = weights
        self.runtime = runtime
        self.descriptor = descriptor
        self.qid = qid
        self.device = runtime.Device(qid=qid)
        self.layers = []
        for index in range(25):
            prefix = f"blk.{index}"
            full = self.has(f"{prefix}.attn_q.weight")
            layer = {
                "full": full,
                "input_norm": self.tensor(f"{prefix}.attn_norm.weight"),
                "post_norm": self.tensor(f"{prefix}.post_attention_norm.weight"),
                "ffn_gate": self.tensor(f"{prefix}.ffn_gate.weight").T,
                "ffn_up": self.tensor(f"{prefix}.ffn_up.weight").T,
                "ffn_down": self.tensor(f"{prefix}.ffn_down.weight").T,
            }
            if full:
                layer.update({
                    "q": self.tensor(f"{prefix}.attn_q.weight").T,
                    "k": self.tensor(f"{prefix}.attn_k.weight").T,
                    "v": self.tensor(f"{prefix}.attn_v.weight").T,
                    "o": self.tensor(f"{prefix}.attn_output.weight").T,
                    "q_norm": self.tensor(f"{prefix}.attn_q_norm.weight"),
                    "k_norm": self.tensor(f"{prefix}.attn_k_norm.weight"),
                    "keys": [],
                    "values": [],
                })
            else:
                layer.update({
                    "qkv": self.tensor(f"{prefix}.attn_qkv.weight").T,
                    "z": self.tensor(f"{prefix}.attn_gate.weight").T,
                    "beta": self.tensor(f"{prefix}.ssm_beta.weight").T,
                    "alpha": self.tensor(f"{prefix}.ssm_alpha.weight").T,
                    "out": self.tensor(f"{prefix}.ssm_out.weight").T,
                    "conv": self.tensor(f"{prefix}.ssm_conv1d.weight").T,
                    "a_log": self.tensor(f"{prefix}.ssm_a"),
                    "dt_bias": self.tensor(f"{prefix}.ssm_dt.bias"),
                    "ssm_norm": self.tensor(f"{prefix}.ssm_norm.weight"),
                    "conv_state": np.zeros((6144, 3), dtype=np.float16),
                    "recurrent": np.zeros((16, 128, 128), dtype=np.float32),
                })
            self.layers.append(layer)
        self.output_norm = self.tensor("output_norm.weight")
        self.embedding = self.tensor("token_embd.weight")

    def has(self, name):
        return name in self.weights.names()

    def tensor(self, name):
        return self.weights.tensor(name)

    def projection(self, matrix, activation):
        result = np.zeros(matrix.shape[0], dtype=np.float32)
        for row0 in range(0, matrix.shape[0], 512):
            acc = np.zeros(512, dtype=np.float32)
            for col0 in range(0, matrix.shape[1], 256):
                tile = np.zeros((512, 256), dtype=np.float16)
                rows = min(512, matrix.shape[0] - row0)
                cols = min(256, matrix.shape[1] - col0)
                tile[:rows, :cols] = matrix[row0:row0 + rows, col0:col0 + cols]
                x = np.zeros(256, dtype=np.float16)
                x[:cols] = activation[col0:col0 + cols]
                acc += self.device.gemm(tile, x, self.descriptor).astype(np.float32)
            result[row0:row0 + min(512, matrix.shape[0] - row0)] = acc[:min(512, matrix.shape[0] - row0)]
        return result

    def mlp(self, layer, hidden):
        x = rms_norm(hidden, layer["post_norm"])
        gate = self.projection(layer["ffn_gate"], x)
        up = self.projection(layer["ffn_up"], x)
        act = silu(gate) * up
        down = self.projection(layer["ffn_down"], act)
        return (hidden.astype(np.float32) + down).astype(np.float16)

    def linear_layer(self, layer, hidden):
        x = rms_norm(hidden, layer["input_norm"])
        mixed = self.projection(layer["qkv"], x).astype(np.float16)
        z = self.projection(layer["z"], x).astype(np.float16)
        beta = sigmoid(self.projection(layer["beta"], x))
        alpha = self.projection(layer["alpha"], x).astype(np.float32)

        window = np.concatenate((layer["conv_state"], mixed[:, None]), axis=1)
        layer["conv_state"] = window[:, 1:]
        mixed = np.sum(window.astype(np.float32) * layer["conv"].astype(np.float32), axis=1)
        mixed = silu(mixed.astype(np.float16))
        query, key, value = np.split(mixed, 3)
        query = l2_norm(query.reshape(16, 128))
        key = l2_norm(key.reshape(16, 128))
        value = value.reshape(16, 128).astype(np.float32)
        decay = -np.exp(layer["a_log"].astype(np.float32)) * np.log1p(
            np.exp(np.clip(alpha + layer["dt_bias"].astype(np.float32), -80, 80))
        )
        state = layer["recurrent"]
        output = np.zeros((16, 128), dtype=np.float32)
        for head in range(16):
            state[head] *= np.exp(decay[head])
            kh = key[head].astype(np.float32)
            vh = value[head]
            delta = (vh - state[head].T @ kh) * float(beta[head])
            state[head] += np.outer(kh, delta)
            output[head] = state[head].T @ query[head].astype(np.float32)
        norm = rms_norm(output.astype(np.float16), layer["ssm_norm"])
        norm = norm * silu(z.reshape(16, 128))
        mixed_out = self.projection(layer["out"], norm.reshape(-1))
        return self.mlp(layer, (hidden.astype(np.float32) + mixed_out).astype(np.float16))

    def full_layer(self, layer, hidden, position):
        x = rms_norm(hidden, layer["input_norm"])
        q = self.projection(layer["q"], x)
        k = self.projection(layer["k"], x)
        v = self.projection(layer["v"], x)
        q_heads, gate = q[:2048].reshape(8, 256), q[2048:]
        k_heads, v_heads = k.reshape(2, 256), v.reshape(2, 256)
        q_heads = rope(rms_norm(q_heads, layer["q_norm"]), position)
        k_heads = rope(rms_norm(k_heads, layer["k_norm"]), position)
        layer["keys"].append(k_heads.copy())
        layer["values"].append(v_heads.copy())
        keys = np.stack(layer["keys"], axis=1)
        values = np.stack(layer["values"], axis=1)
        attended = causal_attention(q_heads, keys, values)
        gated = attended.reshape(-1) * (1.0 / (1.0 + np.exp(-gate.astype(np.float32))))
        mixed_out = self.projection(layer["o"], gated.astype(np.float16))
        return self.mlp(layer, (hidden.astype(np.float32) + mixed_out).astype(np.float16))

    def step(self, hidden, position):
        for layer in self.layers:
            hidden = self.full_layer(layer, hidden, position) if layer["full"] else self.linear_layer(layer, hidden)
        return hidden

    def logits(self, hidden):
        return self.embedding.astype(np.float32).T @ (
            rms_norm(hidden, self.output_norm).astype(np.float32)
        )

    def close(self):
        self.device.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", required=True)
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("--gguf-py")
    parser.add_argument("--qid", type=int, default=None)
    parser.add_argument("--backend", choices=("ane", "cpu"), default="ane")
    args = parser.parse_args()

    tokenizer_module = load("ane-tokenizer.py")
    weights_module = load("ane-weights.py")
    runtime = load("ane-runtime.py")
    if args.backend == "cpu":
        runtime.Device = NumpyDevice
    tokenizer = tokenizer_module.Tokenizer(args.model)
    weights = weights_module.GGUFWeights(args.model, args.gguf_py)
    descriptor = None if args.backend == "cpu" else runtime.load_descriptor(
        os.path.join(os.path.dirname(__file__), "ane-network.py")
    )
    token_ids = tokenizer.encode(args.prompt)
    model = QwenModel(args.model, args.gguf_py, runtime, weights, descriptor, args.qid)
    try:
        hidden = np.zeros(2048, dtype=np.float16)
        for position, token_id in enumerate(token_ids):
            hidden = model.step(weights.row("token_embd.weight", token_id), position)
        logits = model.logits(hidden)
        next_id = int(np.argmax(logits))
        print(f"prompt_tokens={token_ids}")
        print(f"layers={len(model.layers)} full_layers={sum(layer['full'] for layer in model.layers)}")
        print(f"hidden_shape={hidden.shape} logits_shape={logits.shape} next_token={next_id}")
        print(f"hidden_finite={np.isfinite(hidden).all()} logits_finite={np.isfinite(logits).all()}")
        print("ANE_QWEN_FULL_TOKEN_STEP_OK")
    finally:
        model.close()


if __name__ == "__main__":
    main()
