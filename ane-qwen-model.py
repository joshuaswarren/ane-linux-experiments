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

_F32_REFERENCE = False


def load(name):
    path = os.path.join(os.path.dirname(__file__), name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _compute_dtype(value):
    return value.astype(np.float32) if _F32_REFERENCE else value.astype(np.float16)


def sigmoid(x):
    x = np.clip(x.astype(np.float32), -80.0, 80.0)
    return _compute_dtype(1.0 / (1.0 + np.exp(-x)))


def silu(x):
    x = x.astype(np.float32)
    return _compute_dtype(x / (1.0 + np.exp(-np.clip(x, -80.0, 80.0))))


def rms_norm(x, weight, eps=1e-6):
    x32 = x.astype(np.float32)
    scale = 1.0 / np.sqrt(np.mean(x32 * x32) + eps)
    return _compute_dtype(x32 * scale * weight.astype(np.float32))


def l2_norm(x, eps=1e-6):
    x32 = x.astype(np.float32)
    return _compute_dtype(x32 / np.sqrt(np.sum(x32 * x32, axis=-1, keepdims=True) + eps))


def rope(x, position, rotary_dim=64, theta=10_000_000.0, sections=(11, 11, 10)):
    out = x.astype(np.float32).copy()
    inv = theta ** (-np.arange(0, rotary_dim, 2, dtype=np.float32) / rotary_dim)
    freqs = position * inv
    for offset, section in zip((1, 2), sections[1:]):
        indexes = np.arange(offset, section * 3, 3)
        freqs[indexes] = position * inv[:indexes.size]
    cos, sin = np.cos(freqs), np.sin(freqs)
    rotated = out[:, :rotary_dim].copy()
    half = rotary_dim // 2
    left, right = rotated[:, :half], rotated[:, half:]
    out[:, :half] = left * cos - right * sin
    out[:, half:rotary_dim] = right * cos + left * sin
    return _compute_dtype(out)

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
    prob /= np.sum(prob, axis=1, keepdims=True)
    return _compute_dtype(np.einsum("ht,htd->hd", prob, value32))


class QwenModel:
    """Qwen3.5 hybrid model with ANE-backed linear projections."""

    def __init__(self, model_path, gguf_py, runtime, weights, descriptor, descriptor_512, qid):
        self.cpu_reference = runtime.Device is NumpyDevice
        self.weights = weights
        self.runtime = runtime
        self.descriptor = descriptor
        self.descriptor_512 = descriptor_512
        self.qid = qid
        self.device = runtime.Device(qid=qid)
        self.layers = []
        for index in range(24):
            prefix = f"blk.{index}"
            full = self.has(f"{prefix}.attn_q.weight")
            layer = {
                "full": full,
                "input_norm": self.tensor(f"{prefix}.attn_norm.weight"),
                "post_norm": self.tensor(f"{prefix}.post_attention_norm.weight"),
                "ffn_gate": self.tensor(f"{prefix}.ffn_gate.weight"),
                "ffn_up": self.tensor(f"{prefix}.ffn_up.weight"),
                "ffn_down": self.tensor(f"{prefix}.ffn_down.weight"),
            }
            if full:
                layer.update({
                    "q": self.tensor(f"{prefix}.attn_q.weight"),
                    "k": self.tensor(f"{prefix}.attn_k.weight"),
                    "v": self.tensor(f"{prefix}.attn_v.weight"),
                    "o": self.tensor(f"{prefix}.attn_output.weight"),
                    "q_norm": self.tensor(f"{prefix}.attn_q_norm.weight"),
                    "k_norm": self.tensor(f"{prefix}.attn_k_norm.weight"),
                    "keys": [],
                    "values": [],
                })
            else:
                layer.update({
                    "qkv": self.tensor(f"{prefix}.attn_qkv.weight"),
                    "z": self.tensor(f"{prefix}.attn_gate.weight"),
                    "beta": self.tensor(f"{prefix}.ssm_beta.weight"),
                    "alpha": self.tensor(f"{prefix}.ssm_alpha.weight"),
                    "out": self.tensor(f"{prefix}.ssm_out.weight"),
                    "conv": self.tensor(f"{prefix}.ssm_conv1d.weight"),
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
        if self.cpu_reference:
            return self.weights.tensor32(name)
        return self.weights.tensor(name)

    def embedding_row(self, token_id):
        if self.cpu_reference:
            return self.weights.row32("token_embd.weight", token_id)
        return self.weights.row("token_embd.weight", token_id)
    def projection(self, matrix, activation, in_cols=None):
        if self.cpu_reference:
            return matrix.astype(np.float32) @ activation.astype(np.float32)
        if in_cols is None:
            in_cols = 512 if matrix.shape[1] >= 512 else 256
        descriptor = self.descriptor_512 if in_cols == 512 else self.descriptor
        # Persistent tile BOs cost ~1 KB of device iova per weight element
        # (blob + windows); the DART VM cannot hold every layer resident.
        # Only giant matrices (the 508 M-element tied head) are cached; all
        # other projections keep the shared per-call workspace.
        tile_gemm = None
        if getattr(self.device, "tile_gemm", None) is not None \
                and os.environ.get("ANE_NO_PERSISTENT") != "1":
            if matrix.shape[0] * matrix.shape[1] >= 100_000_000:
                tile_gemm = self.device.tile_gemm
            else:
                tile_gemm = self.device.blob_swap_gemm
        result = np.zeros(matrix.shape[0], dtype=np.float32)
        mid = id(matrix)
        for row0 in range(0, matrix.shape[0], 512):
            acc = np.zeros(512, dtype=np.float32)
            for col0 in range(0, matrix.shape[1], in_cols):
                rows = min(512, matrix.shape[0] - row0)
                cols = min(in_cols, matrix.shape[1] - col0)
                x = np.zeros(in_cols, dtype=np.float16)
                x[:cols] = activation[col0:col0 + cols]
                if tile_gemm is not None:
                    key = (mid, in_cols, row0, col0)
                    acc += tile_gemm(key, matrix, x, descriptor, in_cols).astype(np.float32)
                else:
                    tile = np.zeros((512, in_cols), dtype=np.float16)
                    tile[:rows, :cols] = matrix[row0:row0 + rows, col0:col0 + cols]
                    gemm = self.device.gemm512 if in_cols == 512 else self.device.gemm
                    acc += gemm(tile, x, descriptor).astype(np.float32)
            result[row0:row0 + rows] = acc[:rows]
        return result

    def mlp(self, layer, hidden):
        x = rms_norm(hidden, layer["post_norm"])
        gate = self.projection(layer["ffn_gate"], x)
        up = self.projection(layer["ffn_up"], x)
        act = silu(gate) * up
        down = self.projection(layer["ffn_down"], act)
        return _compute_dtype(hidden.astype(np.float32) + down)

    def linear_layer(self, layer, hidden):
        x = rms_norm(hidden, layer["input_norm"])
        mixed = _compute_dtype(self.projection(layer["qkv"], x))
        z = _compute_dtype(self.projection(layer["z"], x))
        beta = sigmoid(self.projection(layer["beta"], x))
        alpha = self.projection(layer["alpha"], x).astype(np.float32)

        window = np.concatenate((layer["conv_state"], mixed[:, None]), axis=1)
        layer["conv_state"] = window[:, 1:]
        mixed = np.sum(window.astype(np.float32) * layer["conv"].astype(np.float32), axis=1)
        mixed = silu(_compute_dtype(mixed))
        query, key, value = np.split(mixed, 3)
        query = l2_norm(query.reshape(16, 128))
        query = _compute_dtype(query.astype(np.float32) / np.sqrt(128.0))
        key = l2_norm(key.reshape(16, 128))
        value = value.reshape(16, 128).astype(np.float32)
        decay = layer["a_log"].astype(np.float32) * np.log1p(
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
        norm = rms_norm(_compute_dtype(output), layer["ssm_norm"])
        norm = norm * silu(z.reshape(16, 128))
        mixed_out = self.projection(layer["out"], norm.reshape(-1))
        return self.mlp(layer, _compute_dtype(hidden.astype(np.float32) + mixed_out))

    def full_layer(self, layer, hidden, position):
        x = rms_norm(hidden, layer["input_norm"])
        q = self.projection(layer["q"], x)
        q_full = q.reshape(8, 512)
        q_heads, gate = q_full[:, :256], q_full[:, 256:].reshape(-1)
        k = self.projection(layer["k"], x)
        v = self.projection(layer["v"], x)
        k_heads, v_heads = k.reshape(2, 256), v.reshape(2, 256)
        q_heads = rope(rms_norm(q_heads, layer["q_norm"]), position)
        k_heads = rope(rms_norm(k_heads, layer["k_norm"]), position)
        layer["keys"].append(k_heads.copy())
        layer["values"].append(v_heads.copy())
        keys = np.stack(layer["keys"], axis=1)
        values = np.stack(layer["values"], axis=1)
        attended = causal_attention(q_heads, keys, values)
        gated = attended.reshape(-1) * (1.0 / (1.0 + np.exp(-gate.astype(np.float32))))
        mixed_out = self.projection(layer["o"], _compute_dtype(gated))
        return self.mlp(layer, _compute_dtype(hidden.astype(np.float32) + mixed_out))

    def step(self, hidden, position):
        for layer in self.layers:
            hidden = self.full_layer(layer, hidden, position) if layer["full"] else self.linear_layer(layer, hidden)
        return hidden

    def logits(self, hidden):
        h = rms_norm(hidden, self.output_norm)
        if self.cpu_reference:
            return self.embedding.astype(np.float32) @ h.astype(np.float32)
        return self.projection(self.embedding, h, in_cols=256)

    def close(self):
        self.device.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", required=True)
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("--gguf-py")
    parser.add_argument("--qid", type=int, default=None)
    parser.add_argument("--backend", choices=("ane", "cpu"), default="ane")
    parser.add_argument("--generate", type=int, default=0)
    args = parser.parse_args()
    global _F32_REFERENCE
    # Keep recurrent and normalization math in float32 on both backends.
    _F32_REFERENCE = True

    tokenizer_module = load("ane-tokenizer.py")
    weights_module = load("ane-weights.py")
    runtime = load("ane-runtime.py")
    if args.backend == "cpu":
        runtime.Device = NumpyDevice
    tokenizer = tokenizer_module.Tokenizer(args.model)
    weights = weights_module.GGUFWeights(args.model, args.gguf_py)
    descriptor = None
    descriptor_512 = None
    if args.backend == "ane":
        descriptor_path = os.path.join(os.path.dirname(__file__), "ane-network.py")
        descriptor = runtime.load_descriptor(descriptor_path)
        descriptor_512 = runtime.load_descriptor(descriptor_path, (512, 512))
    token_ids = tokenizer.encode(args.prompt)
    model = QwenModel(args.model, args.gguf_py, runtime, weights, descriptor, descriptor_512, args.qid)
    try:
        import time as _time
        step_s = 0.0
        logits_s = 0.0
        hidden = np.zeros(2048, dtype=np.float16)
        for position, token_id in enumerate(token_ids):
            t0 = _time.perf_counter()
            hidden = model.step(model.embedding_row(token_id), position)
            step_s += _time.perf_counter() - t0
        generated_ids = []
        generated_pieces = []
        token_field = weights.reader.get_field("tokenizer.ggml.tokens")
        for offset in range(args.generate + 1):
            t0 = _time.perf_counter()
            logits = model.logits(hidden)
            logits_s += _time.perf_counter() - t0
            next_id = int(np.argmax(logits))
            if offset == args.generate:
                break
            generated_ids.append(next_id)
            generated_pieces.append(token_field.contents(next_id) if token_field else str(next_id))
            hidden = model.step(model.embedding_row(next_id), len(token_ids) + offset)
        top_ids = np.argsort(logits)[-10:][::-1]
        print(f"prompt_tokens={token_ids}")
        print(f"layers={len(model.layers)} full_layers={sum(layer['full'] for layer in model.layers)}")
        print(f"hidden_shape={hidden.shape} logits_shape={logits.shape} next_token={next_id}")
        print(f"top10={[(int(i), float(logits[i])) for i in top_ids]}")
        print(f"generated_ids={generated_ids} generated_pieces={generated_pieces}")
        print(f"hidden_head={hidden[:16].tolist()}")
        print(f"hidden_finite={np.isfinite(hidden).all()} logits_finite={np.isfinite(logits).all()}")
        print(f"timing_s: steps={step_s:.3f} logits={logits_s:.3f} "
              f"(persistent={os.environ.get('ANE_NO_PERSISTENT') != '1'})")
        print("ANE_QWEN_FULL_TOKEN_STEP_OK")
    finally:
        model.close()


if __name__ == "__main__":
    main()
