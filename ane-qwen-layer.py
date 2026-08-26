#!/usr/bin/env python3
"""Run one Qwen3.8-2B full-attention layer with ANE linear projections.

Layer 3 is a full-attention layer in the Qwen3.5 hybrid architecture. This
script runs its Q/K/V and output projections through the ANE runtime, while
CPU code handles the operations that do not have ANE descriptors yet:
RMSNorm, Q/K normalization, RoPE, causal softmax attention, and the sigmoid
query gate. K/V state persists across token steps in KVCache.

It compares every ANE projection with a numpy reference built from the same
dequantized Q4_K tensors. It stops before the layer MLP and before logits;
that boundary is explicit because Qwen's other layers use Gated DeltaNet.

  python3 ane-qwen-layer.py -m Qwen3.8-2B-Q4_K_M.gguf -p "The engine runs"
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


def rms_norm(x, weight, eps=1e-6):
    scale = x.astype(np.float32)
    scale *= np.float32(1.0) / np.sqrt(np.mean(scale * scale) + eps)
    return (scale * weight.astype(np.float32)).astype(np.float16)


def rope(x, position, rotary_dim=64, theta=10_000_000.0):
    """Apply half-split RoPE from Qwen3.5 to (heads, head_dim)."""
    out = x.astype(np.float32).copy()
    inv = theta ** (-np.arange(0, rotary_dim, 2, dtype=np.float32) / rotary_dim)
    angles = position * inv
    cos, sin = np.cos(angles), np.sin(angles)
    rotated = out[:, :rotary_dim].copy()
    half = rotary_dim // 2
    left, right = rotated[:, :half], rotated[:, half:]
    out[:, :half] = left * cos - right * sin
    out[:, half:rotary_dim] = right * cos + left * sin
    return out.astype(np.float16)


def causal_attention(q, keys, values):
    """GQA attention for q=(8,256), keys/values=(2,T,256)."""
    q = q.astype(np.float32)
    keys = np.repeat(keys.astype(np.float32), 4, axis=0)
    values = np.repeat(values.astype(np.float32), 4, axis=0)
    scores = np.einsum("hd,htd->ht", q, keys) / np.sqrt(256.0)
    scores -= scores.max(axis=1, keepdims=True)
    probs = np.exp(scores)
    probs /= probs.sum(axis=1, keepdims=True)
    return np.einsum("ht,htd->hd", probs, values).astype(np.float16)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", required=True)
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("--gguf-py")
    parser.add_argument("--qid", type=int, default=None)
    args = parser.parse_args()

    tokenizer_module = load("ane-tokenizer.py")
    weights_module = load("ane-weights.py")
    runtime = load("ane-runtime.py")
    cache_module = load("ane-kv-cache.py")

    tokenizer = tokenizer_module.Tokenizer(args.model)
    weights = weights_module.GGUFWeights(args.model, args.gguf_py)
    descriptor = runtime.load_descriptor(os.path.join(os.path.dirname(__file__), "ane-network.py"))
    token_ids = tokenizer.encode(args.prompt)

    layer = "blk.3"
    q_weight = weights.tensor(f"{layer}.attn_q.weight")
    k_weight = weights.tensor(f"{layer}.attn_k.weight")
    v_weight = weights.tensor(f"{layer}.attn_v.weight")
    o_weight = weights.tensor(f"{layer}.attn_output.weight")
    gate_weight = weights.tensor(f"{layer}.ffn_gate.weight")
    up_weight = weights.tensor(f"{layer}.ffn_up.weight")
    down_weight = weights.tensor(f"{layer}.ffn_down.weight")
    input_norm = weights.tensor(f"{layer}.attn_norm.weight")
    q_norm = weights.tensor(f"{layer}.attn_q_norm.weight")
    k_norm = weights.tensor(f"{layer}.attn_k_norm.weight")
    post_norm = weights.tensor(f"{layer}.post_attention_norm.weight")

    cache = cache_module.KVCache(2, 256, len(token_ids))
    q_err = k_err = v_err = o_err = 0.0
    gate_err = up_err = down_err = 0.0
    hidden = np.zeros(2048, dtype=np.float16)

    with runtime.Device(qid=args.qid) as device:
        for position, token_id in enumerate(token_ids):
            embedding = weights.row("token_embd.weight", token_id)
            normed = rms_norm(embedding, input_norm)

            q = load_projection(device, q_weight, normed, descriptor)
            k = load_projection(device, k_weight, normed, descriptor)
            v = load_projection(device, v_weight, normed, descriptor)
            q_ref = q_weight.astype(np.float32) @ normed.astype(np.float32)
            k_ref = k_weight.astype(np.float32) @ normed.astype(np.float32)
            v_ref = v_weight.astype(np.float32) @ normed.astype(np.float32)
            q_err = max(q_err, float(np.abs(q - q_ref).max()))
            k_err = max(k_err, float(np.abs(k - k_ref).max()))
            v_err = max(v_err, float(np.abs(v - v_ref).max()))

            q_heads, gate = q[:2048].reshape(8, 256), q[2048:]
            k_heads = k.reshape(2, 256)
            v_heads = v.reshape(2, 256)
            q_heads = rms_norm(q_heads, q_norm)
            k_heads = rms_norm(k_heads, k_norm)
            q_heads = rope(q_heads, position)
            k_heads = rope(k_heads, position)
            cache.append(k_heads[None, ...].transpose(1, 0, 2),
                         v_heads[None, ...].transpose(1, 0, 2))
            keys, values = cache.view()
            attended = causal_attention(q_heads, keys, values)
            gated = attended.reshape(-1) * (1.0 / (1.0 + np.exp(-gate.astype(np.float32))))
            output = load_projection(device, o_weight, gated.astype(np.float16), descriptor)
            output_ref = o_weight.astype(np.float32) @ gated
            o_err = max(o_err, float(np.abs(output - output_ref).max()))

            residual = embedding.astype(np.float32) + output
            mlp_input = rms_norm(residual.astype(np.float16), post_norm)
            gate_out = load_projection(device, gate_weight, mlp_input, descriptor)
            up_out = load_projection(device, up_weight, mlp_input, descriptor)
            gate_ref = gate_weight.astype(np.float32) @ mlp_input.astype(np.float32)
            up_ref = up_weight.astype(np.float32) @ mlp_input.astype(np.float32)
            gate_err = max(gate_err, float(np.abs(gate_out - gate_ref).max()))
            up_err = max(up_err, float(np.abs(up_out - up_ref).max()))
            silu = gate_out / (1.0 + np.exp(-gate_out))
            mlp_hidden = (silu * up_out).astype(np.float16)
            down_out = load_projection(device, down_weight, mlp_hidden, descriptor)
            down_ref = down_weight.astype(np.float32) @ mlp_hidden.astype(np.float32)
            down_err = max(down_err, float(np.abs(down_out - down_ref).max()))
            hidden = (residual + down_out).astype(np.float16)

    print(f"prompt_tokens={token_ids}")
    print(f"layer={layer} q_shape={q.shape} kv_shape={keys.shape} kv_length={cache.length}")
    print(f"q_max_abs_err={q_err:.6f} k_max_abs_err={k_err:.6f} "
          f"v_max_abs_err={v_err:.6f} o_max_abs_err={o_err:.6f} "
          f"gate_max_abs_err={gate_err:.6f} up_max_abs_err={up_err:.6f} "
          f"down_max_abs_err={down_err:.6f}")
    print(f"hidden_finite={np.isfinite(hidden).all()} "
          f"kv_finite={np.isfinite(keys).all() and np.isfinite(values).all()}")
    print("ANE_QWEN_FULL_ATTENTION_LAYER_OK")


def load_projection(device, matrix, activation, descriptor):
    """Run arbitrary matrix-vector projection using ANE 512x256 tiles."""
    result = np.zeros(matrix.shape[0], dtype=np.float32)
    for row0 in range(0, matrix.shape[0], 512):
        acc = np.zeros(512, dtype=np.float32)
        for col0 in range(0, matrix.shape[1], 256):
            tile = np.zeros((512, 256), dtype=np.float16)
            tile[:min(512, matrix.shape[0] - row0), :min(256, matrix.shape[1] - col0)] = \
                matrix[row0:row0 + 512, col0:col0 + 256]
            x = np.zeros(256, dtype=np.float16)
            x[:min(256, matrix.shape[1] - col0)] = activation[col0:col0 + 256]
            acc += device.gemm(tile, x, descriptor).astype(np.float32)
        result[row0:row0 + min(512, matrix.shape[0] - row0)] = acc[:min(512, matrix.shape[0] - row0)]
    return result


if __name__ == "__main__":
    main()
