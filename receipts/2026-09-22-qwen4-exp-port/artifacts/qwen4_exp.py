# Qwen4Exp (Qwen3.8-Flash-Next, `model_type: qwen4_exp`) for mlx-lm.
#
# Port of the transformers 5.8.0.dev0 reference
# (src/transformers/models/qwen4_exp/modeling_qwen4_exp.py, text stack;
# vision tower and MTP head are dropped, matching qwen3_5 handling).
# New components vs qwen3_next/qwen3_5 are implemented in composed MLX ops:
#   - Qwen Sparse Attention block-indexer (topk/gather over pooled key blocks)
#   - Gated Residual / hyper-connections (hc_count streams, lowrank mixer)
#   - Per-Layer Embedding (PLE): hashed n-gram embeddings + dilated short conv
#
# Weight names mirror the HF checkpoint exactly; zero-centered RMSNorm
# (out = norm(x) * (1 + w)) is mapped to plain MLX RMSNorm by adding 1.0 to
# the stored weight in `TextModel.sanitize`.

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import mlx.core as mx
import mlx.nn as nn
from mlx.utils import tree_map

from .base import BaseModelArgs, create_attention_mask, create_ssm_mask
from .cache import ArraysCache, KVCache
from .gated_delta import gated_delta_update
from .rope_utils import initialize_rope
from .switch_layers import SwitchGLU


class GroupedRMSNorm(nn.Module):
    """Zero-centered RMSNorm with optional group_size (HF Qwen4ExpTextRMSNorm).

    Stored weight is already 1+w (sanitize adds 1.0); normalization runs per
    group of `group_size` trailing elements when given.
    """

    def __init__(self, dims: int, eps: float = 1e-6, group_size: Optional[int] = None):
        super().__init__()
        if group_size is not None and dims % group_size != 0:
            raise ValueError(f"dims ({dims}) must be divisible by group_size ({group_size})")
        self.weight = mx.ones(dims)
        self.eps = eps
        self.group_size = group_size

    @staticmethod
    def _cd(x: mx.array) -> type:
        # HF norms compute in f32; f64 is used by the CPU reference gate.
        return x.dtype if x.dtype == mx.float64 else mx.float32

    def __call__(self, x: mx.array) -> mx.array:
        if self.group_size is not None:
            shape = x.shape
            x = mx.reshape(x, (*shape[:-1], -1, self.group_size))
            w = mx.reshape(self.weight.astype(self._cd(x)), (-1, self.group_size))
        else:
            w = self.weight.astype(self._cd(x))
        cd = self._cd(x)
        x = x.astype(cd)
        x = x * mx.rsqrt(mx.mean(x * x, axis=-1, keepdims=True) + self.eps)
        x = (x * w).astype(self.weight.dtype)
        return mx.reshape(x, shape) if self.group_size is not None else x


class SigmoidRMSNormGated(nn.Module):
    """HF Qwen4ExpTextRMSNormGated with output_gate_type=sigmoid.

    Norm before gate; plain (non-zero-centered) weight.
    """

    def __init__(self, dims: int, eps: float = 1e-6):
        super().__init__()
        self.weight = mx.ones(dims)
        self.eps = eps

    def __call__(self, x: mx.array, gate: mx.array) -> mx.array:
        dtype = x.dtype
        cd = x.dtype if x.dtype == mx.float64 else mx.float32
        x = x.astype(cd)
        x = x * mx.rsqrt(mx.mean(x * x, axis=-1, keepdims=True) + self.eps)
        x = (self.weight.astype(cd) * x.astype(dtype)).astype(cd)
        x = x * mx.sigmoid(gate.astype(cd))
        return x.astype(dtype)


def splitmix64_list(seed: int, n: int) -> List[int]:
    # python ints are arbitrary precision: mirrors HF _splitmix64/_build_layer_multipliers bit-exactly
    MASK = (1 << 64) - 1
    GAMMA = 0x9E3779B97F4A7C15
    M1 = 0xBF58476D1CE4E5B9
    M2 = 0x94D049BB133111EB

    def sm(v: int) -> int:
        v = (v + GAMMA) & MASK
        v = ((v ^ (v >> 30)) * M1) & MASK
        v = ((v ^ (v >> 27)) * M2) & MASK
        return (v ^ (v >> 31)) & MASK

    return [sm(seed + GAMMA * (i + 1)) for i in range(n)]


def nth_prime_after(start: int, count: int) -> int:
    def is_prime(v: int) -> bool:
        if v < 2:
            return False
        if v % 2 == 0:
            return v == 2
        d = 3
        while d * d <= v:
            if v % d == 0:
                return False
            d += 2
        return True

    prime = start
    for _ in range(count):
        prime += 1
        while not is_prime(prime):
            prime += 1
    return prime


class NGramEmbedding(nn.Module):
    """HF Qwen4ExpTextNGramEmbedding: hashed bigram/trigram embedding lookup."""

    def __init__(self, args, embedding_dim: int, ple_layer_index: int):
        super().__init__()
        self.ngram_size = args.ngram_size
        self.context_len = self.ngram_size - 1
        self.heads_per_ngram = args.heads_per_ngram
        self.ngram_heads = (self.ngram_size - 1) * self.heads_per_ngram
        self.ple_layer_index = ple_layer_index
        self.unigram_vocab_size = args.vocab_size
        self.seed = args.seed
        eos = args.eos_token_id
        self.eos_token_id = eos[0] if isinstance(eos, list) else eos

        self.head_vocab_sizes = [
            nth_prime_after(args.ngram_vocab_size_base - 1,
                            self.ple_layer_index * self.ngram_heads + h + 1)
            for h in range(self.ngram_heads)
        ]
        self.head_offsets = []
        off = 0
        for s in self.head_vocab_sizes:
            self.head_offsets.append(off)
            off += s
        self.total_vocab_size = off

        mults = splitmix64_list(args.seed + 10007 * ple_layer_index, self.ngram_size)
        max_long = (1 << 63) - 1
        half_bound = max(1, (max_long // max(self.unigram_vocab_size, 1)) // 2)
        self.layer_multipliers = [2 * (m % half_bound) + 1 for m in mults]

        head_dim = embedding_dim // self.ngram_heads
        divisor = args.make_ngram_vocab_size_divisible_by
        padded = math.ceil(self.total_vocab_size / divisor) * divisor
        self.ngram_embedding = nn.Embedding(padded, head_dim)

    def __call__(
        self,
        input_ids: mx.array,
        previous_context: Optional[mx.array],
        state_store: Optional[list] = None,
    ) -> mx.array:
        if previous_context is None:
            previous_context = mx.full(
                (input_ids.shape[0], self.context_len), self.eos_token_id, dtype=mx.int32
            )
        if state_store is not None:
            tail = input_ids[:, -self.context_len:]
            if input_ids.shape[1] < self.context_len:
                pad = mx.full(
                    (input_ids.shape[0], self.context_len - input_ids.shape[1]),
                    self.eos_token_id, dtype=mx.int32,
                )
                tail = mx.concatenate([pad, tail], axis=1)
            state_store[0] = tail

        history = mx.concatenate([previous_context, input_ids], axis=1)

        def shift_right_ignore_eos(ids: mx.array, shift: int) -> mx.array:
            if shift == 0:
                return ids
            B, L = ids.shape
            pos = mx.arange(L)
            eos_pos = mx.where(ids == self.eos_token_id, pos[None, :], mx.full((B, L), -1))
            prev_eos_incl = mx.cummax(eos_pos, axis=1)
            prev_eos = mx.concatenate([mx.full((B, 1), -1), prev_eos_incl[:, :-1]], axis=1)
            seg_start = prev_eos + 1
            pos_in_seg = pos[None, :] - seg_start
            src = pos - shift
            gather = mx.maximum(src, 0)
            shifted = ids[:, gather]
            valid = (pos_in_seg >= shift) & (src[None, :] >= 0)
            return mx.where(valid, shifted, mx.full((B, L), self.eos_token_id))

        shifted = [shift_right_ignore_eos(history, s) for s in range(self.ngram_size)]

        blocks = []
        for ngram in range(2, self.ngram_size + 1):
            h0 = (ngram - 2) * self.heads_per_ngram
            heads = self.heads_per_ngram
            mixed = shifted[0].astype(mx.int64) * self.layer_multipliers[0]
            for p in range(1, ngram):
                mixed = mx.bitwise_xor(
                    mixed, shifted[p].astype(mx.int64) * self.layer_multipliers[p]
                )
            sizes = self.head_vocab_sizes[h0:h0 + heads]
            offs = self.head_offsets[h0:h0 + heads]
            ngram_ids = mixed[:, :, None] % mx.array(sizes)[None, None, :]
            blocks.append(ngram_ids + mx.array(offs)[None, None, :])

        ngram_ids = mx.concatenate(blocks, axis=-1)[:, -input_ids.shape[1]:]
        return self.ngram_embedding(ngram_ids).reshape(
            input_ids.shape[0], input_ids.shape[1], -1
        )


class PLELayer(nn.Module):
    """HF Qwen4ExpTextPLELayer."""

    def __init__(self, args, layer_idx: int, ple_layer_index: int):
        super().__init__()
        self.layer_idx = layer_idx
        self.hidden_size = args.hidden_size
        self.hc_count = args.hc_count
        ple_embed_dim = args.ple_embed_dim
        hc_hidden = self.hidden_size * self.hc_count
        self.ple_embedding = NGramEmbedding(args, ple_embed_dim, ple_layer_index)
        conv_k = args.ple_conv_kernel_size
        conv_d = args.ngram_size
        self.short_conv_state_len = (conv_k - 1) * conv_d
        self.key_proj = nn.Linear(ple_embed_dim, hc_hidden, bias=False)
        self.value_proj = nn.Linear(ple_embed_dim, self.hidden_size, bias=False)
        self.norm_key = GroupedRMSNorm(hc_hidden, eps=args.rms_norm_eps, group_size=self.hidden_size)
        self.norm_query = GroupedRMSNorm(hc_hidden, eps=args.rms_norm_eps, group_size=self.hidden_size)
        self.norm_conv = GroupedRMSNorm(hc_hidden, eps=args.rms_norm_eps, group_size=self.hidden_size)
        self.conv1d = nn.Conv1d(
            hc_hidden, hc_hidden, kernel_size=conv_k, groups=hc_hidden,
            dilation=conv_d, bias=False,
        )

    def _short_conv(self, x: mx.array, conv_state: Optional[mx.array],
                    cache: Optional[Any] = None) -> mx.array:
        # mlx conv1d is channels-last: x [B, L, C]
        seq_len = x.shape[1]
        if conv_state is not None:
            x = mx.concatenate([conv_state, x], axis=1)
        if cache is not None:
            cache[2] = mx.contiguous(x[:, -(self.short_conv_state_len):, :])
            mx.eval(cache[2])  # pin MLX f64 CPU eval order
        x = mx.pad(x, [(0, 0), (self.short_conv_state_len, 0), (0, 0)])
        x = x[:, -(self.short_conv_state_len + seq_len):, :]
        x = nn.silu(self.conv1d(x))
        return x

    def __call__(
        self,
        hidden_states: mx.array,
        input_ids: mx.array,
        cache: Optional[Any] = None,
    ) -> mx.array:
        prev_ctx = None
        conv_state = None
        if cache is not None:
            prev_ctx = cache[3]
            conv_state = cache[2]
        state_store = [None]
        embeddings = self.ple_embedding(input_ids, prev_ctx, state_store)
        if cache is not None:
            cache[3] = state_store[0]
        key_normed = self.norm_key(self.key_proj(embeddings)).reshape(
            *hidden_states.shape[:-1], self.hc_count, self.hidden_size
        )
        value = self.value_proj(embeddings)
        query_normed = self.norm_query(hidden_states).reshape(
            *hidden_states.shape[:-1], self.hc_count, self.hidden_size
        )
        gate = mx.sum(key_normed * query_normed, axis=-1, keepdims=True) / math.sqrt(
            self.hidden_size
        )
        gate = mx.sign(gate) * mx.sqrt(mx.maximum(mx.abs(gate), 1e-6))
        gated_value = mx.sigmoid(gate) * mx.expand_dims(value, -2)
        gated_value_flat = gated_value.reshape(*gate.shape[:2], -1)
        gated_value_normed = self.norm_conv(gated_value_flat)
        out = gated_value_flat + self._short_conv(gated_value_normed, conv_state, cache)
        return out


class GatedResidual(nn.Module):
    """HF Qwen4ExpTextGatedResidual (hyper-connections)."""

    def __init__(self, args, use_combine: bool = True):
        super().__init__()
        self.hc_count = args.hc_count
        self.hidden_size = args.hidden_size
        hc_hidden = self.hc_count * self.hidden_size
        self.hc_norm = GroupedRMSNorm(hc_hidden, eps=args.rms_norm_eps, group_size=self.hidden_size)
        self.input_mix_weight_down = nn.Linear(hc_hidden, args.hc_lowrank, bias=False)
        self.input_mix_weight_up = nn.Linear(args.hc_lowrank, hc_hidden, bias=False)
        self.block_inject_weight = (
            nn.Linear(hc_hidden, self.hc_count, bias=False) if use_combine else None
        )

    def __call__(self, hyper_input: mx.array):
        normed = self.hc_norm(hyper_input)
        w = nn.silu(self.input_mix_weight_down(normed) / self.hc_count)
        w = mx.sigmoid(self.input_mix_weight_up(w))
        streams = normed.reshape(*hyper_input.shape[:-1], self.hc_count, self.hidden_size)
        mixed = mx.mean(w.reshape(*streams.shape) * streams, axis=-2)
        if self.block_inject_weight is None:
            return mixed
        inj = 2 * mx.sigmoid(self.block_inject_weight(normed) / self.hc_count)
        return mixed, hyper_input, inj


class GatedDeltaNet(nn.Module):
    """HF Qwen4ExpTextGatedDeltaNet on the mlx-lm gated_delta_update path."""

    def __init__(self, args, layer_idx: int):
        super().__init__()
        self.hidden_size = args.hidden_size
        self.num_v_heads = args.linear_num_value_heads
        self.num_k_heads = args.linear_num_key_heads
        self.head_k_dim = args.linear_key_head_dim
        self.head_v_dim = args.linear_value_head_dim
        self.key_dim = self.head_k_dim * self.num_k_heads
        self.value_dim = self.head_v_dim * self.num_v_heads
        self.conv_kernel_size = args.linear_conv_kernel_dim
        self.conv_dim = self.key_dim * 2 + self.value_dim
        self.conv1d = nn.Conv1d(
            self.conv_dim, self.conv_dim, kernel_size=self.conv_kernel_size,
            groups=self.conv_dim, bias=False,
        )
        self.in_proj_qkv = nn.Linear(self.hidden_size, self.key_dim * 2 + self.value_dim, bias=False)
        self.in_proj_z = nn.Linear(self.hidden_size, self.value_dim, bias=False)
        self.in_proj_b = nn.Linear(self.hidden_size, self.num_v_heads, bias=False)
        self.in_proj_a = nn.Linear(self.hidden_size, self.num_v_heads, bias=False)
        self.dt_bias = mx.ones(self.num_v_heads)
        self.A_log = mx.zeros(self.num_v_heads)
        self.norm = SigmoidRMSNormGated(self.head_v_dim, eps=args.rms_norm_eps)
        self.out_proj = nn.Linear(self.value_dim, self.hidden_size, bias=False)

    def __call__(
        self,
        x: mx.array,
        mask: Optional[mx.array] = None,
        cache: Optional[Any] = None,
    ) -> mx.array:
        B, S, _ = x.shape
        qkv = self.in_proj_qkv(x)
        z = self.in_proj_z(x).reshape(B, S, self.num_v_heads, self.head_v_dim)
        b = self.in_proj_b(x)
        a = self.in_proj_a(x)

        conv_state = cache[0] if (cache is not None and cache[0] is not None) else mx.zeros(
            (B, self.conv_kernel_size - 1, self.conv_dim), dtype=x.dtype
        )
        if mask is not None:
            qkv = mx.where(mask[..., None], qkv, 0)
        conv_input = mx.concatenate([conv_state, qkv], axis=1)
        if cache is not None:
            cache[0] = mx.contiguous(conv_input[:, -(self.conv_kernel_size - 1):, :])
        conv_out = nn.silu(self.conv1d(conv_input))

        q, k, v = [
            t.reshape(B, S, h, d)
            for t, h, d in zip(
                mx.split(conv_out, [self.key_dim, 2 * self.key_dim], -1),
                [self.num_k_heads, self.num_k_heads, self.num_v_heads],
                [self.head_k_dim, self.head_k_dim, self.head_v_dim],
            )
        ]

        state = cache[1] if cache is not None else None
        if state is None:
            # contract is f32 state for real checkpoints; f64 follows
            # activations so the CPU reference gate runs fully in f64
            state = mx.zeros((B, self.num_v_heads, self.head_v_dim, self.head_k_dim),
                             dtype=x.dtype if x.dtype == mx.float64 else mx.float32)
        # exact HF l2norm (eps=1e-6 on the sum) + Dk**-0.5 readout scale on q
        q = q * (self.head_k_dim ** -0.5) * mx.rsqrt(mx.sum(q * q, axis=-1, keepdims=True) + 1e-6)
        k = k * mx.rsqrt(mx.sum(k * k, axis=-1, keepdims=True) + 1e-6)

        out, state = gated_delta_update(
            q, k, v, a, b, self.A_log, self.dt_bias, state, mask, use_kernel=False
        )
        if cache is not None:
            cache[1] = state
            cache.advance(S)

        out = self.norm(out, z)
        return self.out_proj(out.reshape(B, S, -1))


class QSAIndexer(nn.Module):
    """HF Qwen4ExpTextQSAIndexer (composed ops, vectorized over queries)."""

    def __init__(self, args, layer_idx: int):
        super().__init__()
        self.layer_idx = layer_idx
        self.index_n_heads = args.indexer_n_heads
        self.index_kv_heads = args.indexer_kv_heads
        self.index_head_dim = args.indexer_head_dim
        self.token_budget = args.indexer_budget
        self.compress_ratio = args.indexer_compress_ratio
        self.block_topk = self.token_budget // self.compress_ratio
        self.index_qk_proj = nn.Linear(
            args.hidden_size,
            (self.index_n_heads + self.index_kv_heads) * self.index_head_dim,
            bias=False,
        )
        self.q_layernorm = GroupedRMSNorm(self.index_head_dim, eps=args.rms_norm_eps)
        self.k_layernorm = GroupedRMSNorm(self.index_head_dim, eps=args.rms_norm_eps)

    def __call__(
        self,
        hidden_states: mx.array,
        cos: mx.array,
        sin: mx.array,
        indexer_keys: mx.array,
        kv_offset: int,
    ) -> mx.array:
        """Returns an additive float mask [B, Q, KV]: 0 where selected, -inf else."""
        B, Q, _ = hidden_states.shape
        KV = kv_offset + Q
        hd = self.index_head_dim
        cr = self.compress_ratio
        H = self.index_n_heads

        qk = self.index_qk_proj(hidden_states)
        q, token_k = mx.split(qk, [H * hd], axis=-1)
        q = q.reshape(B, Q, H, hd)
        q = self.q_layernorm(q)
        raw_keys = indexer_keys  # [B, KV, hd]

        cur_cos = cos[:, kv_offset:KV, :]
        cur_sin = sin[:, kv_offset:KV, :]
        q = apply_rope_partial(q, cur_cos, cur_sin)  # [B, Q, H, hd]

        NB_full = KV // cr  # complete blocks over full kv
        sel = mx.zeros((B, Q, KV), dtype=mx.bool_)
        if NB_full > 0:
            kblocks = raw_keys[:, : NB_full * cr, :].reshape(B, NB_full, cr, hd)
            pooled = mx.mean(kblocks.astype(mx.float32), axis=2).astype(raw_keys.dtype)
            pooled = self.k_layernorm(pooled)  # [B, NB_full, hd]
            group_starts = mx.arange(NB_full) * cr
            pooled = apply_rope_partial(
                pooled[:, :, None, :], cos[:, group_starts, :], sin[:, group_starts, :]
            )[:, :, 0, :]  # [B, NB_full, hd]

            qf = q.astype(mx.float32).transpose(0, 2, 1, 3).reshape(B, H, Q, hd)
            pf = pooled.astype(mx.float32)[:, None]  # [B, 1, NB, hd]
            scores = (qf[:, :, :, None, :] * pf[:, :, None, :, :]).sum(-1)  # [B,H,Q,NB]
            scores = mx.maximum(scores, 0).sum(axis=1) / math.sqrt(hd)  # [B, Q, NB]
            ends = (mx.arange(NB_full) + 1) * cr
            valid = ends[None, None, :] <= (kv_offset + mx.arange(Q)[None, :, None] + 1)
            neg = mx.full(scores.shape, -mx.inf)
            scores = mx.where(valid, scores, neg)
            k = min(self.block_topk, NB_full)
            sel_blocks = mx.argpartition(scores, kth=-k, axis=-1)[..., -k:]  # [B, Q, k]
            block_tokens = (sel_blocks * cr)[:, :, :, None] + mx.arange(cr)[None, None, None, :]
            block_tokens = block_tokens.reshape(B, Q, -1)  # [B, Q, k*cr]
            sel = mx.put_along_axis(
                sel, block_tokens, mx.ones_like(block_tokens, dtype=mx.bool_), axis=-1
            )
            # per-query tail: tokens after the last fully-visible complete
            # block through the current query position (HF: visible[ncb*cr:])
            tail_start = ((kv_offset + mx.arange(Q) + 1) // cr) * cr  # [Q]
            t = mx.arange(KV)
            tail = (t[None, :] >= tail_start[:, None]) & (
                t[None, :] <= (kv_offset + mx.arange(Q))[:, None]
            )
            sel = sel | tail[None]
            mask = mx.where(sel, 0.0, -mx.inf)
            return mask


def apply_rope_partial(x: mx.array, cos: mx.array, sin: mx.array) -> mx.array:
    """Half-rotation rope on first `cos.shape[-1]` dims.

    x: [B, L, H, hd]; cos/sin: [B, L, rotary]. (HF apply_rotary_pos_emb.)
    """
    rotary = cos.shape[-1]
    x_rope = x[..., :rotary]
    x_nope = x[..., rotary:]
    cos = mx.expand_dims(cos, -2)
    sin = mx.expand_dims(sin, -2)
    x1, x2 = mx.split(x_rope, 2, axis=-1)
    rot = mx.concatenate([-x2, x1], axis=-1)
    out = x_rope * cos + rot * sin
    return mx.concatenate([out, x_nope], axis=-1) if rotary < x.shape[-1] else out


class QSAAttention(nn.Module):
    """HF Qwen4ExpTextAttention (indexed attention with output gate)."""

    def __init__(self, args, layer_idx: int):
        super().__init__()
        self.layer_idx = layer_idx
        self.head_dim = args.head_dim
        self.num_attention_heads = args.num_attention_heads
        self.num_key_value_heads = args.num_key_value_heads
        self.scale = self.head_dim ** -0.5

        self.q_proj = nn.Linear(
            args.hidden_size, self.num_attention_heads * self.head_dim * 2, bias=False
        )
        self.k_proj = nn.Linear(args.hidden_size, self.num_key_value_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(args.hidden_size, self.num_key_value_heads * self.head_dim, bias=False)
        self.o_proj = nn.Linear(self.num_attention_heads * self.head_dim, args.hidden_size, bias=False)
        self.q_norm = GroupedRMSNorm(self.head_dim, eps=args.rms_norm_eps)
        self.k_norm = GroupedRMSNorm(self.head_dim, eps=args.rms_norm_eps)
        self.indexer = QSAIndexer(args, layer_idx)

    def __call__(
        self,
        x: mx.array,
        cos: mx.array,
        sin: mx.array,
        mask: Optional[mx.array],
        cache: Optional[Any] = None,
    ) -> mx.array:
        B, L, D = x.shape
        kv_offset = cache.offset if cache is not None else 0

        raw_keys_full = cache.indexer_keys if cache is not None else None
        if raw_keys_full is None:
            raw_keys_full = mx.zeros((B, 0, self.indexer.index_head_dim), dtype=x.dtype)
        cur_raw = self.indexer.index_qk_proj(x)[
            :, :, self.indexer.index_n_heads * self.indexer.index_head_dim:
        ].reshape(B, L, self.indexer.index_head_dim)
        raw_keys_full = mx.concatenate([raw_keys_full, cur_raw], axis=1)
        if cache is not None:
            cache.indexer_keys = raw_keys_full

        sel_mask = self.indexer(x, cos, sin, raw_keys_full, kv_offset)
        add_mask = mask if mask is not None else mx.zeros_like(sel_mask)
        full_mask = add_mask + sel_mask

        queries, gate = mx.split(
            self.q_proj(x).reshape(B, L, self.num_attention_heads, -1), 2, axis=-1
        )
        gate = gate.reshape(B, L, -1)
        keys = self.k_proj(x).reshape(B, L, self.num_key_value_heads, self.head_dim)
        values = self.v_proj(x).reshape(B, L, self.num_key_value_heads, self.head_dim)

        queries = self.q_norm(queries)  # [B, L, H, hd]
        keys = self.k_norm(keys)  # [B, L, KV, hd]
        values = values.transpose(0, 2, 1, 3)

        cur_cos = cos[:, kv_offset:kv_offset + L, :]
        cur_sin = sin[:, kv_offset:kv_offset + L, :]
        queries = apply_rope_partial(queries, cur_cos, cur_sin)
        keys = apply_rope_partial(keys, cur_cos, cur_sin)
        queries = queries.transpose(0, 2, 1, 3)
        keys = keys.transpose(0, 2, 1, 3)

        if cache is not None:
            keys, values = cache.update_and_fetch(keys, values)

        # composed attention (explicit, mirrors HF eager_attention_forward;
        # sdpa fusion is a non-goal for this port)
        att = (queries @ keys.transpose(0, 1, 3, 2)) * self.scale + full_mask[:, None]
        att = att - mx.max(att, axis=-1, keepdims=True)
        att = mx.softmax(att, axis=-1)
        out = att @ values
        out = out.transpose(0, 2, 1, 3).reshape(B, L, -1)
        return self.o_proj(out * mx.sigmoid(gate))


class SparseMoeBlock(nn.Module):
    """HF Qwen4ExpTextSparseMoeBlock (top-k router + SwitchGLU + gated shared expert)."""

    def __init__(self, args):
        super().__init__()
        self.num_experts = args.num_experts
        self.top_k = args.num_experts_per_tok
        self.norm_topk_prob = args.norm_topk_prob
        self.gate = nn.Linear(args.hidden_size, args.num_experts, bias=False)
        self.switch_mlp = SwitchGLU(args.hidden_size, args.moe_intermediate_size, args.num_experts)
        self.shared_expert_gate = nn.Linear(args.hidden_size, 1, bias=False)
        self.shared_expert = MLP(args.hidden_size, args.shared_expert_intermediate_size)

    def __call__(self, x: mx.array) -> mx.array:
        mx.eval(x)  # pin MLX f64 CPU eval order (see Qwen4ExpTextModel note)
        gates = mx.softmax(self.gate(x).astype(mx.float32), axis=-1)
        k = self.top_k
        inds = mx.argpartition(gates, kth=-k, axis=-1)[..., -k:]
        scores = mx.take_along_axis(gates, inds, axis=-1)
        if self.norm_topk_prob:
            scores = scores / mx.sum(scores, axis=-1, keepdims=True)
        y = self.switch_mlp(x, inds)
        y = (y * scores[..., None]).sum(axis=-2)
        shared = self.shared_expert(x)
        out = y + mx.sigmoid(self.shared_expert_gate(x)) * shared
        mx.eval(out)  # pin MLX f64 CPU eval order
        return out


class MLP(nn.Module):
    def __init__(self, dim, hidden_dim):
        super().__init__()
        self.gate_proj = nn.Linear(dim, hidden_dim, bias=False)
        self.down_proj = nn.Linear(hidden_dim, dim, bias=False)
        self.up_proj = nn.Linear(dim, hidden_dim, bias=False)

    def __call__(self, x: mx.array) -> mx.array:
        return self.down_proj(nn.silu(self.gate_proj(x)) * self.up_proj(x))


class MropeRotary(nn.Module):
    """HF Qwen4ExpTextRotaryEmbedding: partial mrope with interleaved recomposition."""

    def __init__(self, args):
        super().__init__()
        # NOTE: inv_freq computed per call — mx.array attributes become
        # nn.Module parameters and would pollute the weight tree.
        self._dim = int(args.head_dim * args.partial_rotary_factor)
        self._theta = float(args.rope_theta)
        self.mrope_section = list(
            args.rope_parameters.get("mrope_section", [11, 11, 10])
        )

    def __call__(self, position_ids: mx.array) -> Tuple[mx.array, mx.array]:
        """position_ids: [3, B, L]. Returns cos/sin [B, L, rotary]."""
        inv_freq = 1.0 / (
            self._theta ** (mx.arange(0, self._dim, 2, dtype=mx.float32) / self._dim)
        )
        freqs = position_ids[:, :, :, None].astype(mx.float32) * inv_freq[None, None, None, :]
        cos = mx.cos(freqs)
        sin = mx.sin(freqs)
        cos = self._recompose(cos)
        sin = self._recompose(sin)
        return mx.concatenate([cos, cos], axis=-1), mx.concatenate([sin, sin], axis=-1)

    def _recompose(self, freq: mx.array) -> mx.array:
        """HF recomposition_frequencies: keep T grid, interleave H/W every 3rd slot."""
        out = freq[0]
        for dim, offset in ((1, 1), (2, 2)):
            length = self.mrope_section[dim] * 3
            idxs = mx.arange(offset, min(length, out.shape[-1]), 3)
            if idxs.shape[-1] == 0:
                continue
            idx = mx.repeat(
                mx.repeat(idxs[None, None, :], out.shape[0], axis=0), out.shape[1], axis=1
            )
            out = mx.put_along_axis(out, idx, freq[dim, ..., : idxs.shape[-1]], axis=-1)
        return out


class DecoderLayer(nn.Module):
    def __init__(self, args, layer_idx: int):
        super().__init__()
        self.layer_type = args.layer_types[layer_idx]
        self.is_linear = self.layer_type == "linear_attention"
        if self.is_linear:
            self.linear_attn = GatedDeltaNet(args, layer_idx)
        else:
            self.self_attn = QSAAttention(args, layer_idx)
        self.mlp = SparseMoeBlock(args)
        if layer_idx + 1 in (args.ple_layer_ids or []):
            self.ple = PLELayer(
                args, layer_idx, (args.ple_layer_ids or []).index(layer_idx + 1)
            )
        else:
            self.ple = None
        self.attn_hyper_connection = GatedResidual(args)
        self.mlp_hyper_connection = GatedResidual(args)

    def __call__(
        self,
        x: mx.array,
        cos: mx.array,
        sin: mx.array,
        attn_mask: Optional[mx.array],
        ssm_mask: Optional[mx.array],
        input_ids: mx.array,
        cache: Optional[Any] = None,
    ) -> mx.array:
        if self.ple is not None:
            x = x + self.ple(x, input_ids, cache)
        mixed, hyper_input, inj = self.attn_hyper_connection(x)
        if self.is_linear:
            h = self.linear_attn(mixed, ssm_mask, cache)
        else:
            h = self.self_attn(mixed, cos, sin, attn_mask, cache)
        mx.eval(h)  # pin MLX f64 CPU eval order (see Qwen4ExpTextModel note)
        x = hyper_input + (mx.expand_dims(h, -2) * mx.expand_dims(inj, -1)).reshape(
            hyper_input.shape
        )
        mixed, hyper_input, inj = self.mlp_hyper_connection(x)
        h = self.mlp(mixed)
        mx.eval(h)  # pin MLX f64 CPU eval order
        return hyper_input + (mx.expand_dims(h, -2) * mx.expand_dims(inj, -1)).reshape(
            hyper_input.shape
        )


@dataclass
class TextModelArgs(BaseModelArgs):
    model_type: str = "qwen4_exp_text"
    hidden_size: int = 2048
    num_hidden_layers: int = 48
    num_attention_heads: int = 24
    num_key_value_heads: int = 2
    head_dim: int = 256
    rms_norm_eps: float = 1e-6
    vocab_size: int = 248320
    max_position_embeddings: int = 262144
    hidden_act: str = "silu"
    linear_num_value_heads: int = 48
    linear_num_key_heads: int = 16
    linear_key_head_dim: int = 128
    linear_value_head_dim: int = 128
    linear_conv_kernel_dim: int = 4
    layer_types: Optional[List[str]] = None
    hc_count: int = 4
    hc_lowrank: int = 320
    ple_layer_ids: Optional[List[int]] = None
    ple_embed_dim: Optional[int] = None
    ple_conv_kernel_size: int = 4
    ngram_size: int = 3
    heads_per_ngram: int = 8
    ngram_vocab_size_base: int = 20_000_000
    make_ngram_vocab_size_divisible_by: int = 128
    seed: int = 1234
    indexer_n_heads: Optional[int] = None
    indexer_kv_heads: Optional[int] = None
    indexer_head_dim: Optional[int] = None
    indexer_budget: Optional[int] = None
    indexer_compress_ratio: Optional[int] = None
    num_experts: int = 512
    num_experts_per_tok: int = 10
    moe_intermediate_size: int = 512
    shared_expert_intermediate_size: int = 512
    norm_topk_prob: bool = True
    eos_token_id: Optional[Any] = None
    rope_parameters: Dict[str, Any] = field(
        default_factory=lambda: {
            "rope_type": "default",
            "mrope_section": [11, 11, 10],
            "rope_theta": 1e7,
            "partial_rotary_factor": 0.25,
        }
    )
    partial_rotary_factor: float = 0.25
    rope_theta: float = 1e7

    def __post_init__(self):
        if self.ple_embed_dim is None:
            self.ple_embed_dim = self.hidden_size
        if self.layer_types is None:
            self.layer_types = [
                "linear_attention" if (i + 1) % 4 else "indexed_attention"
                for i in range(self.num_hidden_layers)
            ]
        self.layer_types = [
            "indexed_attention" if t == "full_attention" else t for t in self.layer_types
        ]
        rp = dict(self.rope_parameters)
        self.partial_rotary_factor = rp.get("partial_rotary_factor", 0.25)
        self.rope_theta = rp.get("rope_theta", 1e7)
        self.rope_parameters = rp


class Qwen4ExpTextModel(nn.Module):
    def __init__(self, args: TextModelArgs):
        super().__init__()
        self.args = args
        self.embed_tokens = nn.Embedding(args.vocab_size, args.hidden_size)
        self.layers = [DecoderLayer(args, i) for i in range(args.num_hidden_layers)]
        self.rotary_emb = MropeRotary(args)
        self.hyper_connection_mixer = GatedResidual(args, use_combine=False)
        self.hc_count = args.hc_count

    def __call__(
        self,
        inputs: mx.array,
        cache: Optional[Any] = None,
    ) -> mx.array:
        B, L = inputs.shape
        if cache is None:
            cache = [None] * len(self.layers)
        first = next((c for c in cache if c is not None and hasattr(c, "offset")), None)
        offset = first.offset if first is not None else 0
        # text-only: all three rope grids use the same positions; tables span
        # the FULL kv history because the QSA indexer ropes pooled key blocks
        # at their absolute block-start positions.
        pos = mx.arange(offset + L).astype(mx.float32)
        position_ids = mx.tile(pos[None, None, :], (3, B, 1))  # [3, B, KV]
        cos, sin = self.rotary_emb(position_ids)

        attn_mask = None
        ssm_mask = None
        if L > 1:
            if attn_mask is None:
                causal = (mx.arange(L)[None, :, None] >= mx.arange(L)[None, None, :])
                attn_mask = mx.where(causal, 0.0, -1e9)
            ssm_mask = create_ssm_mask(
                inputs, next(
                    (c for c in cache if c is not None and not hasattr(c, "keys")), None
                )
            )

        h = self.embed_tokens(inputs)
        h = mx.repeat(h, self.hc_count, axis=-1)
        for layer, c in zip(self.layers, cache):
            h = layer(h, cos, sin, attn_mask, ssm_mask, inputs, c)
            # NOTE: MLX f64 CPU graphs are evaluation-order sensitive in this
            # model (composite put_along_axis / conv1d / rms_norm mix); force
            # per-layer evaluation to pin deterministic results.
            mx.eval(h)
        return self.hyper_connection_mixer(h)


class TextModel(nn.Module):
    def __init__(self, args: TextModelArgs):
        super().__init__()
        self.args = args
        self.model_type = args.model_type
        self.model = Qwen4ExpTextModel(args)
        self.lm_head = nn.Linear(args.hidden_size, args.vocab_size, bias=False)

    def __call__(self, inputs: mx.array, cache=None) -> mx.array:
        return self.lm_head(self.model(inputs, cache))

    def make_cache(self):
        caches = []
        for l in self.model.layers:
            if l.is_linear:
                n = 4 if l.ple is not None else 2
                caches.append(ArraysCache(size=n))
            else:
                caches.append(QSACache())
        return caches

    def sanitize(self, weights):
        weights = {k: v for k, v in weights.items() if not k.startswith("mtp.")}
        has_3d_experts = any(
            k.endswith("mlp.experts.gate_up_proj") and v.ndim == 3 for k, v in weights.items()
        )
        if has_3d_experts:
            for k in [k for k in weights if k.endswith("mlp.experts.gate_up_proj")]:
                base = k[: -len("mlp.experts.gate_up_proj")]
                dn_key = f"{base}mlp.experts.down_proj"
                gu = weights.pop(k)
                dn = weights.pop(dn_key)
                I = gu.shape[1] // 2
                weights[f"{base}mlp.switch_mlp.gate_proj.weight"] = gu[:, :I, :]
                weights[f"{base}mlp.switch_mlp.up_proj.weight"] = gu[:, I:, :]
                weights[f"{base}mlp.switch_mlp.down_proj.weight"] = dn
        # zero-centered norms: MLX multiplies by the stored weight -> store 1 + w
        norm_suffixes = (
            ".hc_norm.weight",
            ".q_norm.weight",
            ".k_norm.weight",
            ".q_layernorm.weight",
            ".k_layernorm.weight",
            ".norm_key.weight",
            ".norm_query.weight",
            ".norm_conv.weight",
        )
        for k, v in weights.items():
            if any(k.endswith(s) for s in norm_suffixes) and v.ndim == 1:
                weights[k] = v + 1.0
        # conv1d HF layout [C, 1, K] -> mlx [C, K, 1]
        for k, v in weights.items():
            if "conv1d.weight" in k and v.ndim == 3 and v.shape[-1] != 1:
                weights[k] = v.moveaxis(2, 1)
        return weights


class QSACache:
    """KV cache plus raw indexer-key history for one QSA layer."""

    def __init__(self):
        self.keys = None
        self.values = None
        self.indexer_keys = None
        self.offset = 0

    def update_and_fetch(self, keys, values):
        if self.keys is None:
            self.keys, self.values = keys, values
        else:
            self.keys = mx.concatenate([self.keys, keys], axis=2)
            self.values = mx.concatenate([self.values, values], axis=2)
        self.offset += keys.shape[2]
        return self.keys, self.values


@dataclass
class ModelArgs(BaseModelArgs):
    model_type: str
    text_config: dict

    @classmethod
    def from_dict(cls, params):
        if "text_config" not in params:
            return cls(model_type=params["model_type"], text_config=params)
        return super().from_dict(params)


class Model(nn.Module):
    def __init__(self, args: ModelArgs):
        super().__init__()
        self.args = args
        self.model_type = args.model_type
        self.language_model = TextModel(TextModelArgs.from_dict(args.text_config))

    def __call__(self, inputs: mx.array, cache=None) -> mx.array:
        return self.language_model(inputs, cache)

    @property
    def model(self):
        return self.language_model.model

    def sanitize(self, weights):
        sanitized = {}
        for key, value in weights.items():
            if key.startswith("model.visual") or key.startswith("vision_tower"):
                continue
            if key.startswith("model.language_model."):
                key = key.replace("model.language_model.", "language_model.model.", 1)
            elif not key.startswith("language_model."):
                key = "language_model." + key
            sanitized[key] = value
        return self.language_model.sanitize(sanitized)

    def make_cache(self):
        return self.language_model.make_cache()

    @property
    def quant_predicate(self):
        def predicate(path, _):
            if path.endswith("mlp.gate") or path.endswith("shared_expert_gate"):
                return {"group_size": 64, "bits": 8}
            return True

        return predicate
