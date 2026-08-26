#!/usr/bin/env python3
"""Run the first real Qwen token-step projection boundary on the ANE.

This connects four real pieces without pretending to be a full language model:

1. llama.cpp token IDs from ``ane-tokenizer.py``;
2. one real token embedding row from the selected Qwen GGUF;
3. tiled ANE projection calls for a full-attention layer's Q/K/V tensors;
4. persistent K/V state in ``ane-kv-cache.py``.

The current Qwen3.8-2B model uses a hybrid Gated DeltaNet/full-attention
architecture. This script exercises a full-attention layer (layer 3), but it
stops before RMSNorm, RoPE, attention, logits, and sampling. Those operations
need their Qwen-specific descriptor mapping. The K/V rows stored here are the
raw projected rows, which makes this a boundary test rather than a claim of
model-quality inference.

  python3 ane-qwen-step.py -m Qwen3.8-2B-Q4_K_M.gguf -p "The engine runs"
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


def projection(device, matrix, activation, descriptor):
    """Run W @ x by sending each 512x256 tile to the ANE."""
    result = np.zeros(matrix.shape[0], dtype=np.float32)
    for row0 in range(0, matrix.shape[0], 512):
        acc = np.zeros(512, dtype=np.float32)
        for col0 in range(0, matrix.shape[1], 256):
            tile = np.zeros((512, 256), dtype=np.float16)
            tile[:min(512, matrix.shape[0] - row0),
                 :min(256, matrix.shape[1] - col0)] = \
                matrix[row0:row0 + 512, col0:col0 + 256]
            x = np.zeros(256, dtype=np.float16)
            x[:min(256, matrix.shape[1] - col0)] = activation[col0:col0 + 256]
            acc += device.gemm(tile, x, descriptor).astype(np.float32)
        result[row0:row0 + min(512, matrix.shape[0] - row0)] = acc[:min(512, matrix.shape[0] - row0)]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", required=True)
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("--gguf-py")
    parser.add_argument("--qid", type=int, default=None)
    args = parser.parse_args()

    tokenizer = load("ane-tokenizer.py").Tokenizer(args.model)
    weights = load("ane-weights.py").GGUFWeights(args.model, args.gguf_py)
    runtime = load("ane-runtime.py")
    cache_module = load("ane-kv-cache.py")
    descriptor = runtime.load_descriptor(os.path.join(os.path.dirname(__file__), "ane-network.py"))

    token_ids = tokenizer.encode(args.prompt)
    embedding_record = next(t for t in weights.reader.tensors if t.name == "token_embd.weight")
    if embedding_record.shape[0] != 2048:
        raise ValueError(f"unexpected embedding shape {tuple(embedding_record.shape)}")
    layer = "blk.3"
    q_weight = weights.tensor(f"{layer}.attn_q.weight")
    k_weight = weights.tensor(f"{layer}.attn_k.weight")
    v_weight = weights.tensor(f"{layer}.attn_v.weight")
    cache = cache_module.KVCache(n_heads=2, head_dim=256, max_seq=len(token_ids))

    with runtime.Device(qid=args.qid) as device:
        last_q = None
        for token_id in token_ids:
            activation = weights.row("token_embd.weight", token_id)
            q = projection(device, q_weight, activation, descriptor)
            k = projection(device, k_weight, activation, descriptor)
            v = projection(device, v_weight, activation, descriptor)
            cache.append(k.reshape(2, 1, 256), v.reshape(2, 1, 256))
            last_q = q

    keys, values = cache.view()
    print(f"prompt_tokens={token_ids}")
    print(f"layer={layer} q_shape={last_q.shape} kv_shape={keys.shape}")
    print(f"kv_length={cache.length} q_finite={np.isfinite(last_q).all()} "
          f"kv_finite={np.isfinite(keys).all() and np.isfinite(values).all()}")
    print("ANE_QWEN_TOKEN_BOUNDARY_OK")


if __name__ == "__main__":
    main()
