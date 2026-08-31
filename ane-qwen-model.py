#!/usr/bin/env python3
"""Run a complete one-token Qwen3.8-2B forward pass with ANE linear layers.

This is the first end-to-end model path in this work. It loads the selected
Qwen3.8-2B Q4_K_M GGUF, dequantizes each tensor, sends every linear projection
through the ANE 512x256 runtime, and keeps recurrent and attention state on the
ANE across tokens. The CPU computes the remaining elementwise operations. The
tied embedding produces output logits through the ANE projection runtime.

The CPU operations are explicit. They cover RMSNorm, depthwise causal
convolution, sigmoid/SiLU, and RoPE. This is a working correctness path, not a
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
    mean_square = np.mean(x32 * x32, axis=-1, keepdims=True)
    scale = 1.0 / np.sqrt(mean_square + eps)
    return _compute_dtype(x32 * scale * weight.astype(np.float32))


def l2_norm(x, scale=1.0, eps=1e-6):
    x32 = x.astype(np.float32)
    magnitude = np.sqrt(np.sum(x32 * x32, axis=-1, keepdims=True) + eps)
    return _compute_dtype(x32 * scale / magnitude)


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

    def __init__(
        self,
        model_path,
        gguf_py,
        runtime,
        weights,
        descriptor,
        descriptor_512,
        qid,
        token_runtime=None,
    ):
        self.cpu_reference = runtime.Device is NumpyDevice
        self.weights = weights
        self.runtime = runtime
        self.descriptor = descriptor
        self.descriptor_512 = descriptor_512
        self.qid = qid
        self.device = runtime.Device(qid=qid)
        self.token_runtime = token_runtime
        self.layers = []
        full_state_index = 0
        recurrent_state_index = 0
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
                    "state_index": full_state_index,
                    "q": self.tensor(f"{prefix}.attn_q.weight"),
                    "k": self.tensor(f"{prefix}.attn_k.weight"),
                    "v": self.tensor(f"{prefix}.attn_v.weight"),
                    "o": self.tensor(f"{prefix}.attn_output.weight"),
                    "q_norm": self.tensor(f"{prefix}.attn_q_norm.weight"),
                    "k_norm": self.tensor(f"{prefix}.attn_k_norm.weight"),
                    "keys": [],
                    "values": [],
                })
                full_state_index += 1
            else:
                layer.update({
                    "state_index": recurrent_state_index,
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
                recurrent_state_index += 1
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

    def normalize_rms(self, value, weight):
        if self.token_runtime is not None:
            return self.token_runtime.rms_norm(
                value.astype(np.float16), weight.astype(np.float16)
            )
        return rms_norm(value, weight)

    def normalize_l2(self, value, scale=1.0):
        if self.token_runtime is not None:
            return self.token_runtime.l2_norm(value.astype(np.float16), scale)
        return l2_norm(value, scale)

    def activate_sigmoid(self, value):
        if self.token_runtime is not None:
            return self.token_runtime.sigmoid(value.astype(np.float16))
        return sigmoid(value)

    def activate_sigmoid_mul(self, value, multiplier):
        if self.token_runtime is not None:
            return self.token_runtime.sigmoid_mul(
                value.astype(np.float16), multiplier.astype(np.float16)
            )
        return _compute_dtype(
            sigmoid(value).astype(np.float32) * multiplier.astype(np.float32)
        )

    def activate_silu(self, value):
        if self.token_runtime is not None:
            return self.token_runtime.silu(value.astype(np.float16))
        return silu(value)

    def activate_silu_mul(self, value, multiplier):
        if self.token_runtime is not None:
            return self.token_runtime.silu_mul(
                value.astype(np.float16), multiplier.astype(np.float16)
            )
        return _compute_dtype(
            silu(value).astype(np.float32) * multiplier.astype(np.float32)
        )

    def recurrent_decay_factor(self, alpha, bias, a_log):
        if self.token_runtime is not None:
            return self.token_runtime.decay_multiplier(
                alpha.astype(np.float16),
                bias.astype(np.float16),
                a_log.astype(np.float16),
            )
        combined = alpha.astype(np.float32) + bias.astype(np.float32)
        decay = a_log.astype(np.float32) * np.logaddexp(0.0, combined)
        return np.exp(decay)

    def mlp(self, layer, hidden):
        x = self.normalize_rms(hidden, layer["post_norm"])
        gate = self.projection(layer["ffn_gate"], x)
        up = self.projection(layer["ffn_up"], x)
        act = self.activate_silu_mul(gate, up)
        down = self.projection(layer["ffn_down"], act)
        return _compute_dtype(hidden.astype(np.float32) + down)

    def linear_layer(self, layer, hidden):
        x = self.normalize_rms(hidden, layer["input_norm"])
        mixed = _compute_dtype(self.projection(layer["qkv"], x))
        z = _compute_dtype(self.projection(layer["z"], x))
        beta = self.activate_sigmoid(self.projection(layer["beta"], x))
        alpha = self.projection(layer["alpha"], x).astype(np.float32)

        if self.token_runtime is not None:
            mixed = self.token_runtime.causal_convolution(
                layer["state_index"], mixed.astype(np.float16), layer["conv"]
            )
        else:
            window = np.concatenate(
                (layer["conv_state"], mixed[:, None]), axis=1
            )
            layer["conv_state"] = window[:, 1:]
            mixed = np.sum(
                window.astype(np.float32) * layer["conv"].astype(np.float32),
                axis=1,
            )
        mixed = self.activate_silu(_compute_dtype(mixed))
        query, key, value = np.split(mixed, 3)
        query = self.normalize_l2(
            query.reshape(16, 128), 1.0 / np.sqrt(128.0)
        )
        key = self.normalize_l2(key.reshape(16, 128))
        value = value.reshape(16, 128)
        decay_factor = self.recurrent_decay_factor(
            alpha, layer["dt_bias"], layer["a_log"]
        )
        if self.token_runtime is not None:
            output = self.token_runtime.recurrent(
                layer["state_index"],
                query.astype(np.float16),
                key.astype(np.float16),
                value.astype(np.float16),
                beta.astype(np.float16),
                decay_factor.astype(np.float16),
            )
        else:
            state = layer["recurrent"]
            output = np.zeros((16, 128), dtype=np.float32)
            for head in range(16):
                state[head] *= decay_factor[head]
                kh = key[head].astype(np.float32)
                vh = value[head].astype(np.float32)
                delta = (vh - state[head].T @ kh) * float(beta[head])
                state[head] += np.outer(kh, delta)
                output[head] = state[head].T @ query[head].astype(np.float32)
        norm = self.normalize_rms(_compute_dtype(output), layer["ssm_norm"])
        norm = self.activate_silu_mul(z.reshape(16, 128), norm)
        mixed_out = self.projection(layer["out"], norm.reshape(-1))
        return self.mlp(layer, _compute_dtype(hidden.astype(np.float32) + mixed_out))

    def full_layer(self, layer, hidden, position):
        x = self.normalize_rms(hidden, layer["input_norm"])
        q = self.projection(layer["q"], x)
        q_full = q.reshape(8, 512)
        q_heads, gate = q_full[:, :256], q_full[:, 256:].reshape(-1)
        k = self.projection(layer["k"], x)
        v = self.projection(layer["v"], x)
        k_heads, v_heads = k.reshape(2, 256), v.reshape(2, 256)
        q_heads = rope(self.normalize_rms(q_heads, layer["q_norm"]), position)
        k_heads = rope(self.normalize_rms(k_heads, layer["k_norm"]), position)
        if self.token_runtime is not None:
            attended = self.token_runtime.full_attention(
                layer["state_index"],
                q_heads.astype(np.float16),
                k_heads.astype(np.float16),
                v_heads.astype(np.float16),
            )
        else:
            layer["keys"].append(k_heads.copy())
            layer["values"].append(v_heads.copy())
            keys = np.stack(layer["keys"], axis=1)
            values = np.stack(layer["values"], axis=1)
            attended = causal_attention(q_heads, keys, values)
        gated = self.activate_sigmoid_mul(gate, attended.reshape(-1))
        mixed_out = self.projection(layer["o"], _compute_dtype(gated))
        return self.mlp(layer, _compute_dtype(hidden.astype(np.float32) + mixed_out))

    def step(self, hidden, position):
        for layer in self.layers:
            hidden = self.full_layer(layer, hidden, position) if layer["full"] else self.linear_layer(layer, hidden)
        return hidden

    def logits(self, hidden):
        h = self.normalize_rms(hidden, self.output_norm)
        if self.cpu_reference:
            return self.embedding.astype(np.float32) @ h.astype(np.float32)
        return self.projection(self.embedding, h, in_cols=256)

    def close(self):
        if self.token_runtime is not None:
            self.token_runtime.close()
        self.device.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", required=True)
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("--gguf-py")
    parser.add_argument("--qid", type=int, default=None)
    parser.add_argument("--backend", choices=("ane", "cpu"), default="ane")
    parser.add_argument("--generate", type=int, default=0)
    parser.add_argument("--recurrent-anec")
    args = parser.parse_args()
    if args.recurrent_anec is not None and args.backend != "ane":
        parser.error("--recurrent-anec requires --backend ane")
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
        if args.recurrent_anec is not None:
            token_runtime_module = load(os.path.join("tools", "qwen-token-runtime.py"))
            softmax_path = os.path.join(os.path.dirname(__file__), "ane-softmax.py")
            elementwise_descriptors = token_runtime_module.harvest_elementwise_descriptors(
                softmax_path
            )
            full_layers = sum(layer["full"] for layer in model.layers)
            model.token_runtime = token_runtime_module.QwenTokenRuntime(
                model.device,
                descriptor,
                elementwise_descriptors,
                args.recurrent_anec,
                full_layers,
                len(model.layers) - full_layers,
            )
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
        print(f"resident_token_runtime={model.token_runtime is not None}")
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
