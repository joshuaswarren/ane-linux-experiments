"""Build a synthetic tiny qwen4_exp checkpoint (HF safetensors layout).

Preserves the architecture structure at toy scale:
  - 4 layers, 3 linear_attention : 1 indexed_attention (3:1 GDN:QSA pattern)
  - 512-expert MoE -> 8 experts top-2 + shared expert
  - hyper-connections hc_count=4, lowrank mixer
  - QSA indexer (budget 4 / compress 2)
  - PLE hashed n-gram embedding on one-indexed layer 2 + dilated short conv
  - partial mrope interleaved
Weights: seeded normal, fp32.
"""
import json
import os
import sys

import numpy as np
from safetensors.numpy import save_file

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "tiny-qwen4exp")

CFG = {
    "model_type": "qwen4_exp",
    "architectures": ["Qwen4ExpForConditionalGeneration"],
    "transformers_version": "5.8.0.dev0",
    "text_config": {
        "model_type": "qwen4_exp_text",
        "vocab_size": 128,
        "hidden_size": 64,
        "num_hidden_layers": 4,
        "num_attention_heads": 4,
        "num_key_value_heads": 1,
        "head_dim": 16,
        "hidden_act": "silu",
        "rms_norm_eps": 1e-6,
        "max_position_embeddings": 512,
        "tie_word_embeddings": False,
        "linear_num_value_heads": 12,
        "linear_num_key_heads": 4,
        "linear_key_head_dim": 8,
        "linear_value_head_dim": 8,
        "linear_conv_kernel_dim": 4,
        "layer_types": ["linear_attention", "linear_attention", "linear_attention",
                        "indexed_attention"],
        "hc_count": 4,
        "hc_lowrank": 8,
        "ple_layer_ids": [2],
        "ple_embed_dim": 64,
        "ple_conv_kernel_size": 4,
        "ngram_size": 3,
        "heads_per_ngram": 2,
        "ngram_vocab_size_base": 101,
        "make_ngram_vocab_size_divisible_by": 128,
        "seed": 1234,
        "indexer_n_heads": 2,
        "indexer_kv_heads": 1,
        "indexer_head_dim": 8,
        "indexer_budget": 4,
        "indexer_compress_ratio": 2,
        "num_experts": 8,
        "num_experts_per_tok": 2,
        "moe_intermediate_size": 32,
        "shared_expert_intermediate_size": 32,
        "norm_topk_prob": True,
        "eos_token_id": [7],
        "bos_token_id": 7,
        "rope_parameters": {
            "rope_type": "default",
            "rope_theta": 10000.0,
            "partial_rotary_factor": 0.25,
            "mrope_section": [1, 1, 0],
        },
    },
}


def build():
    tc = CFG["text_config"]
    rng = np.random.default_rng(0)
    H = tc["hidden_size"]
    hc = tc["hc_count"]
    w = {}

    def n(*shape, scale=0.05):
        return (rng.standard_normal(shape) * scale).astype(np.float32)

    w["model.language_model.embed_tokens.weight"] = n(tc["vocab_size"], H)
    w["language_model.lm_head.weight"] = n(tc["vocab_size"], H)
    w["model.language_model.hyper_connection_mixer.hc_norm.weight"] = n(hc * H) * 0.1
    w["model.language_model.hyper_connection_mixer.input_mix_weight_down.weight"] = n(
        tc["hc_lowrank"], hc * H
    )
    w["model.language_model.hyper_connection_mixer.input_mix_weight_up.weight"] = n(
        hc * H, tc["hc_lowrank"]
    )

    for l in range(tc["num_hidden_layers"]):
        p = f"model.language_model.layers.{l}"
        is_lin = tc["layer_types"][l] == "linear_attention"
        if is_lin:
            kd = tc["linear_key_head_dim"] * tc["linear_num_key_heads"]
            vd = tc["linear_value_head_dim"] * tc["linear_num_value_heads"]
            nv = tc["linear_num_value_heads"]
            a = f"{p}.linear_attn"
            w[f"{a}.in_proj_qkv.weight"] = n(2 * kd + vd, H)
            w[f"{a}.in_proj_z.weight"] = n(vd, H)
            w[f"{a}.in_proj_b.weight"] = n(nv, H)
            w[f"{a}.in_proj_a.weight"] = n(nv, H)
            w[f"{a}.conv1d.weight"] = n(2 * kd + vd, 1, tc["linear_conv_kernel_dim"])
            w[f"{a}.dt_bias"] = (1 + rng.standard_normal(nv)).astype(np.float32)
            w[f"{a}.A_log"] = rng.uniform(0.01, 4, nv).astype(np.float32)
            w[f"{a}.norm.weight"] = (1 + rng.standard_normal(tc["linear_value_head_dim"]) * 0.1).astype(np.float32)
            w[f"{a}.out_proj.weight"] = n(H, vd)
        else:
            a = f"{p}.self_attn"
            hd = tc["head_dim"]
            w[f"{a}.q_proj.weight"] = n(tc["num_attention_heads"] * hd * 2, H)
            w[f"{a}.k_proj.weight"] = n(tc["num_key_value_heads"] * hd, H)
            w[f"{a}.v_proj.weight"] = n(tc["num_key_value_heads"] * hd, H)
            w[f"{a}.o_proj.weight"] = n(H, tc["num_attention_heads"] * hd)
            w[f"{a}.q_norm.weight"] = (rng.standard_normal(hd) * 0.1).astype(np.float32)
            w[f"{a}.k_norm.weight"] = (rng.standard_normal(hd) * 0.1).astype(np.float32)
            ix = f"{a}.indexer"
            w[f"{ix}.index_qk_proj.weight"] = n(
                (tc["indexer_n_heads"] + tc["indexer_kv_heads"]) * tc["indexer_head_dim"], H
            )
            w[f"{ix}.q_layernorm.weight"] = (rng.standard_normal(tc["indexer_head_dim"]) * 0.1).astype(np.float32)
            w[f"{ix}.k_layernorm.weight"] = (rng.standard_normal(tc["indexer_head_dim"]) * 0.1).astype(np.float32)
        # MoE
        E, I = tc["num_experts"], tc["moe_intermediate_size"]
        w[f"{p}.mlp.gate.weight"] = n(E, H)
        w[f"{p}.mlp.experts.gate_up_proj"] = n(E, 2 * I, H)
        w[f"{p}.mlp.experts.down_proj"] = n(E, H, I)
        w[f"{p}.mlp.shared_expert.gate_proj.weight"] = n(tc["shared_expert_intermediate_size"], H)
        w[f"{p}.mlp.shared_expert.up_proj.weight"] = n(tc["shared_expert_intermediate_size"], H)
        w[f"{p}.mlp.shared_expert.down_proj.weight"] = n(H, tc["shared_expert_intermediate_size"])
        w[f"{p}.mlp.shared_expert_gate.weight"] = n(1, H)
        # hyper connections
        for which in ("attn", "mlp"):
            hp = f"{p}.{which}_hyper_connection"
            w[f"{hp}.hc_norm.weight"] = (rng.standard_normal(hc * H) * 0.1).astype(np.float32)
            w[f"{hp}.input_mix_weight_down.weight"] = n(tc["hc_lowrank"], hc * H)
            w[f"{hp}.input_mix_weight_up.weight"] = n(hc * H, tc["hc_lowrank"])
            w[f"{hp}.block_inject_weight.weight"] = n(hc, hc * H)
        # PLE on one-indexed layer 2 -> layer idx 1
        if l + 1 in tc["ple_layer_ids"]:
            pp = f"{p}.ple"
            nheads = (tc["ngram_size"] - 1) * tc["heads_per_ngram"]
            # vocab padded total; the loader pads the same way
            from reference import nth_prime_after
            sizes = [nth_prime_after(tc["ngram_vocab_size_base"] - 1, i + 1) for i in range(nheads)]
            total = sum(sizes)
            padded = ((total + tc["make_ngram_vocab_size_divisible_by"] - 1)
                      // tc["make_ngram_vocab_size_divisible_by"]) * tc["make_ngram_vocab_size_divisible_by"]
            w[f"{pp}.ple_embedding.ngram_embedding.weight"] = n(padded, tc["ple_embed_dim"] // nheads)
            w[f"{pp}.key_proj.weight"] = n(hc * H, tc["ple_embed_dim"])
            w[f"{pp}.value_proj.weight"] = n(H, tc["ple_embed_dim"])
            w[f"{pp}.norm_key.weight"] = (rng.standard_normal(hc * H) * 0.1).astype(np.float32)
            w[f"{pp}.norm_query.weight"] = (rng.standard_normal(hc * H) * 0.1).astype(np.float32)
            w[f"{pp}.norm_conv.weight"] = (rng.standard_normal(hc * H) * 0.1).astype(np.float32)
            w[f"{pp}.conv1d.weight"] = n(hc * H, 1, tc["ple_conv_kernel_size"])

    os.makedirs(OUT, exist_ok=True)
    save_file(w, os.path.join(OUT, "model.safetensors"))
    with open(os.path.join(OUT, "config.json"), "w") as f:
        json.dump(CFG, f, indent=2)
    print(f"wrote {OUT} ({len(w)} tensors)")


if __name__ == "__main__":
    build()
