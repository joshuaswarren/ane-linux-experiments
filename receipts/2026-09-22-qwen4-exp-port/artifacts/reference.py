"""NumPy float64 reference for qwen4_exp (text stack), mirroring
transformers 5.8.0.dev0 modeling_qwen4_exp.py line-for-line.

Batch-1, no padding. Maintains the same cache states as the MLX port:
  gdn conv state, recurrent state, indexer raw keys, PLE conv state,
  n-gram token context.
"""
import math
from typing import Optional

import numpy as np
_rsqrt = lambda x: 1.0 / np.sqrt(x)

MASK64 = (1 << 64) - 1
GAMMA = 0x9E3779B97F4A7C15
M1 = 0xBF58476D1CE4E5B9
M2 = 0x94D049BB133111EB
PRIME1 = 10007


def _splitmix64(v: int) -> int:
    v = (v + GAMMA) & MASK64
    v = ((v ^ (v >> 30)) * M1) & MASK64
    v = ((v ^ (v >> 27)) * M2) & MASK64
    return (v ^ (v >> 31)) & MASK64


def build_layer_multipliers(unigram_vocab, ngram_size, ple_layer_index, seed):
    max_long = (1 << 63) - 1
    mult_max = max_long // max(unigram_vocab, 1)
    half = max(1, mult_max // 2)
    base = seed + PRIME1 * ple_layer_index
    out = []
    for i in range(ngram_size):
        v = (base + GAMMA * (i + 1)) & MASK64
        out.append(2 * (_splitmix64(v) % half) + 1)
    return np.array(out, dtype=np.int64)


def is_prime(v):
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


def nth_prime_after(start, count):
    p = start
    for _ in range(count):
        p += 1
        while not is_prime(p):
            p += 1
    return p


def rmsnorm(x, w, eps=1e-6, group=None):
    # HF: out = norm(x.f32) * (1 + w); reference weights passed are ALREADY 1+w
    xf = x.astype(np.float64)
    if group is not None:
        shape = x.shape
        xf = xf.reshape(*shape[:-1], -1, group)
        wg = np.asarray(w).reshape(-1, group)
        out = xf * _rsqrt((xf * xf).mean(-1, keepdims=True) + eps)
        out = out * wg
        return out.reshape(shape)
    out = xf * _rsqrt((xf * xf).mean(-1, keepdims=True) + eps)
    return out * w


def rmsnorm_gated_sigmoid(x, gate, w, eps=1e-6):
    # HF Qwen4ExpTextRMSNormGated (sigmoid): norm-then-gate, plain weight
    xf = x.astype(np.float64)
    var = (xf * xf).mean(-1, keepdims=True)
    xh = xf * 1.0 / np.sqrt(var + eps)
    xh = w * xh
    return xh * (1.0 / (1.0 + np.exp(-gate.astype(np.float64))))


def l2norm(x, eps=1e-6):
    return x * 1.0 / np.sqrt((x * x).sum(-1, keepdims=True) + eps)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def softplus(x):
    return np.log1p(np.exp(-np.abs(x))) + np.maximum(x, 0)


def causal_conv1d(x, weight, kernel, dilation=1):
    """x: [B, C, L] full input (already includes any prepended state).
    weight: [C, K]. Output length = L - (K-1)*dilation."""
    B, C, L = x.shape
    K = kernel
    out_len = L - (K - 1) * dilation
    out = np.zeros((B, C, out_len))
    for k in range(K):
        out += weight[:, k][:, None] * x[:, :, k * dilation: k * dilation + out_len]
    return out


def chunk_gated_delta_rule(q, k, v, g, beta, initial_state=None, chunk_size=64):
    # HF torch_chunk_gated_delta_rule, fp32/64
    B, T, _, Dk = k.shape
    Hv, Dv = v.shape[-2:]
    def _th(x):
        return np.transpose(x, (0, 2, 1)) if x.ndim == 3 else np.transpose(x, (0, 2, 1, 3))
    q, k, v, beta, decay = [_th(x) for x in (q, k, v, beta, g)]
    q, k = l2norm(q), l2norm(k)
    scaling = q.shape[-1] ** -0.5
    q = q * scaling
    pad = (chunk_size - T % chunk_size) % chunk_size
    q = np.pad(q, ((0, 0), (0, 0), (0, pad), (0, 0)))
    k = np.pad(k, ((0, 0), (0, 0), (0, pad), (0, 0)))
    v = np.pad(v, ((0, 0), (0, 0), (0, pad), (0, 0)))
    beta = np.pad(beta, ((0, 0), (0, 0), (0, pad)))
    decay = np.pad(decay, ((0, 0), (0, 0), (0, pad)))
    NC = (T + pad) // chunk_size
    v_beta = v * beta[..., None]
    k_beta = k * beta[..., None]
    q = q.reshape(B, Hv, NC, chunk_size, Dk)
    k = k.reshape(B, Hv, NC, chunk_size, Dk)
    k_beta = k_beta.reshape(B, Hv, NC, chunk_size, Dk)
    v_beta = v_beta.reshape(B, Hv, NC, chunk_size, Dv)
    decay = decay.reshape(B, Hv, NC, chunk_size)
    strict_upper = np.triu(np.ones((chunk_size, chunk_size), bool), 1)
    cum_decay = np.cumsum(decay, axis=3)
    pairwise = np.exp(
        np.where(
            strict_upper,
            -np.inf,
            cum_decay[..., :, None] - cum_decay[..., None, :],
        )
    )
    ut = (k_beta @ np.swapaxes(k, -1, -2)) * pairwise
    intra = (q @ np.swapaxes(k, -1, -2)) * pairwise
    decayed_k_beta = k_beta * np.exp(cum_decay)[..., None]
    # forward substitution for unit-lower-triangular solve (N<=tiny; no linalg.solve_triangular in numpy)
    new_values = solve_unit_lower(ut, v_beta)
    k_cumdecay = solve_unit_lower(ut, decayed_k_beta)
    state = np.zeros((B, Hv, Dk, Dv)) if initial_state is None else initial_state.astype(np.float64)
    q = q * np.exp(cum_decay)[..., None]
    k = k * np.exp(cum_decay[..., -1:] - cum_decay)[..., None]
    chunk_decay = np.exp(cum_decay[..., -1])[..., None, None]
    out = np.zeros_like(new_values)
    for i in range(NC):
        v_new = new_values[:, :, i] - k_cumdecay[:, :, i] @ state
        inter = q[:, :, i] @ state
        out[:, :, i] = inter + intra[:, :, i] @ v_new
        state = state * chunk_decay[:, :, i] + np.swapaxes(k[:, :, i], -1, -2) @ v_new
    out = out.reshape(B, Hv, -1, Dv)[..., :T, :].transpose(0, 2, 1, 3)
    return out, state


def solve_unit_lower(A, B):
    # solves A X = B with A unit lower triangular (last two dims), iterative forward subst
    N = A.shape[-1]
    X = B.copy()
    for i in range(N):
        X[..., i, :] = B[..., i, :] - (A[..., i, :i, None] * X[..., :i, :]).sum(-2)
    return X


def recurrent_gated_delta_rule(q, k, v, g, beta, initial_state=None):
    B, T, _, Dk = k.shape
    Hv, Dv = v.shape[-2:]
    def _th(x):
        return np.transpose(x, (0, 2, 1)) if x.ndim == 3 else np.transpose(x, (0, 2, 1, 3))
    q, k, v, beta, decay = [_th(x) for x in (q, k, v, beta, g)]
    q, k = l2norm(q), l2norm(k)
    q = q / math.sqrt(q.shape[-1])
    state = np.zeros((B, Hv, Dk, Dv)) if initial_state is None else initial_state.astype(np.float64)
    out = np.zeros_like(v)
    for i in range(T):
        q_t, k_t, v_t = q[:, :, i], k[:, :, i], v[:, :, i]
        state = state * np.exp(decay[:, :, i])[..., None, None]
        kv_mem = (state * k_t[..., None]).sum(-2)
        delta = (v_t - kv_mem) * beta[:, :, i][..., None]
        state = state + k_t[..., None] * delta[..., None, :]
        out[:, :, i] = (state * q_t[..., None]).sum(-2)
    out = np.transpose(out, (0, 2, 1, 3))
    return out, state


class RefModel:
    def __init__(self, weights: dict, cfg: dict):
        self.w = weights
        self.cfg = cfg
        rp = cfg.get("rope_parameters", cfg.get("rope_scaling") or {})
        self.rope_theta = float(rp.get("rope_theta", 1e7))
        self.partial = float(rp.get("partial_rotary_factor", 0.25))
        self.mrope_section = rp.get("mrope_section", [11, 11, 10])
        self.hc = cfg["hc_count"]
        self.head_dim = cfg["head_dim"]
        self.eos = cfg.get("eos_token_id", 0)
        if isinstance(self.eos, list):
            self.eos = self.eos[0]
        self.ngram_size = cfg["ngram_size"]
        self.hpn = cfg["heads_per_ngram"]
        self.seed = cfg.get("seed", 1234)
        self.ple_layer_ids = cfg.get("ple_layer_ids", [])
        # n-gram head vocab per PLE layer
        self.ngram_heads = (self.ngram_size - 1) * self.hpn
        self.ple_prime_sizes = {}
        for li, one_idx in enumerate(self.ple_layer_ids):
            self.ple_prime_sizes[li] = [
                nth_prime_after(cfg["ngram_vocab_size_base"] - 1, li * self.ngram_heads + h + 1)
                for h in range(self.ngram_heads)
            ]

    # --- rope -------------------------------------------------------------
    def rope(self, position_ids):
        # position_ids: [3, L]; rotary = head_dim * partial
        dim = int(self.head_dim * self.partial)
        inv = 1.0 / (self.rope_theta ** (np.arange(0, dim, 2, dtype=np.float64) / dim))
        freqs = position_ids[:, :, None].astype(np.float64) * inv[None, None, :]
        cos, sin = np.cos(freqs), np.sin(freqs)
        cos = self._recompose(cos)
        sin = self._recompose(sin)
        return np.concatenate([cos, cos], -1), np.concatenate([sin, sin], -1)

    def _recompose(self, freq):
        out = freq[0].copy()
        for dim, offset in ((1, 1), (2, 2)):
            length = self.mrope_section[dim] * 3
            idx = np.arange(offset, min(length, out.shape[-1]), 3)
            if idx.size:
                out[..., idx] = freq[dim, ..., : idx.size]
        return out

    def apply_rope(self, x, cos, sin):
        # x: [L, H, hd]; cos/sin: [L, r] (broadcasts over leading dims of x too)
        r = cos.shape[-1]
        xr, xn = x[..., :r], x[..., r:]
        x1, x2 = xr[..., : r // 2], xr[..., r // 2:]
        rot = np.concatenate([-x2, x1], -1)
        cs = cos.reshape(*cos.shape[:-1], *([1] * (x.ndim - cos.ndim)), r)
        sn = sin.reshape(*sin.shape[:-1], *([1] * (x.ndim - sin.ndim)), r)
        out = xr * cs + rot * sn
        if r < x.shape[-1]:
            return np.concatenate([out, xn], -1)
        return out

    # --- linear attention --------------------------------------------------
    def gated_delta_net(self, x, layer, cache):
        w = self.w
        p = f"model.language_model.layers.{layer}.linear_attn"
        B, S, H = x.shape
        qkv = x @ w[f"{p}.in_proj_qkv.weight"].T
        z = (x @ w[f"{p}.in_proj_z.weight"].T).reshape(B, S, -1, self.w[f"{p}.norm.weight"].shape[0])
        b = x @ w[f"{p}.in_proj_b.weight"].T
        a = x @ w[f"{p}.in_proj_a.weight"].T
        conv_w = w[f"{p}.conv1d.weight"][:, 0, :]  # [C, K]
        K = conv_w.shape[-1]
        conv_state = cache.get(f"{p}.conv")
        if conv_state is None:
            conv_state = np.zeros((1, qkv.shape[-1], K - 1))
        qkv_full = np.concatenate([conv_state, qkv.transpose(0, 2, 1)], axis=2)
        cache[f"{p}.conv"] = qkv_full[:, :, -(K - 1):]
        conv_out = _silu(causal_conv1d(qkv_full, conv_w, K)).transpose(0, 2, 1)
        kd = self.cfg["linear_key_head_dim"]
        nkh = self.cfg["linear_num_key_heads"]
        nvh = self.cfg["linear_num_value_heads"]
        q, k, v = np.split(conv_out, [nkh * kd, 2 * nkh * kd], -1)
        q = q.reshape(B, S, nkh, kd)
        k = k.reshape(B, S, nkh, kd)
        v = v.reshape(B, S, nvh, kd)
        if nvh // nkh > 1:
            q = np.repeat(q, nvh // nkh, axis=2)
            k = np.repeat(k, nvh // nkh, axis=2)
        beta = sigmoid(b)
        A_log = w[f"{p}.A_log"]
        dt = w[f"{p}.dt_bias"]
        g = -np.exp(A_log) * softplus(a + dt)
        if S == 1:
            out, state = recurrent_gated_delta_rule(q, k, v, g, beta, cache[f"{p}.ssm"])
        else:
            out, state = chunk_gated_delta_rule(q, k, v, g, beta, cache.get(f"{p}.ssm"))
        cache[f"{p}.ssm"] = state
        out = rmsnorm_gated_sigmoid(out, z, w[f"{p}.norm.weight"])
        return out.reshape(B, S, -1) @ w[f"{p}.out_proj.weight"].T

    # --- QSA ---------------------------------------------------------------
    def indexer(self, x, layer, cos, sin, cache):
        w = self.w
        p = f"model.language_model.layers.{layer}.self_attn.indexer"
        cfg = self.cfg
        H = cfg["indexer_n_heads"]
        hd = cfg["indexer_head_dim"]
        cr = cfg["indexer_compress_ratio"]
        budget = cfg["indexer_budget"]
        block_topk = budget // cr
        B, S, _ = x.shape
        KV = cache["kv_len"] + S
        qk = x @ w[f"{p}.index_qk_proj.weight"].T
        q, token_k = np.split(qk, [H * hd], -1)
        q = q.reshape(B, S, H, hd)
        q = rmsnorm(q, w[f"{p}.q_layernorm.weight"])
        raw_keys_all = cache.get(f"{p}.keys")
        raw_keys_all = token_k[0] if raw_keys_all is None else np.concatenate([raw_keys_all, token_k[0]], 0)
        cache[f"{p}.keys"] = raw_keys_all

        q = self.apply_rope(q[0], cos[KV - S:KV], sin[KV - S:KV])  # [S, H, hd]

        NB = KV // cr
        sel = []
        for qi in range(S):
            vis = KV - S + qi + 1
            ncb = vis // cr
            toks = []
            if ncb > 0:
                blocks = raw_keys_all[: ncb * cr].reshape(ncb, cr, hd)
                pooled = rmsnorm(blocks.mean(1), w[f"{p}.k_layernorm.weight"])
                starts = np.arange(ncb) * cr
                pooled = self.apply_rope(pooled, cos[starts], sin[starts])
                scores = np.maximum(
                    (q[qi].astype(np.float64) @ pooled.astype(np.float64).T),
                    0,
                ).sum(0) / math.sqrt(hd)
                k = min(block_topk, ncb)
                idx = np.argpartition(scores, -k)[-k:]
                toks.extend((idx[:, None] * cr + np.arange(cr)[None, :]).reshape(-1).tolist())
            toks.extend(range(ncb * cr, vis))
            sel.append(toks)

        mask = np.full((S, KV), -np.inf)
        for qi, toks in enumerate(sel):
            mask[qi, toks] = 0.0
        return mask

    def attention(self, x, layer, cos, sin, cache):
        w = self.w
        p = f"model.language_model.layers.{layer}.self_attn"
        cfg = self.cfg
        B, S, _ = x.shape
        KV = cache["kv_len"] + S
        causal = np.zeros((S, KV))
        causal += np.triu(np.ones((S, KV)), KV - S + 1) * -1e30
        sel_mask = self.indexer(x, layer, cos, sin, cache)
        mask = causal + sel_mask

        nh, nkv = cfg["num_attention_heads"], cfg["num_key_value_heads"]
        hd = cfg["head_dim"]
        qg = (x @ w[f"{p}.q_proj.weight"].T).reshape(B, S, nh, 2 * hd)
        q, gate = np.split(qg, 2, -1)
        q = q.reshape(B, S, nh, hd)
        gate = gate.reshape(B, S, nh * hd)
        k = (x @ w[f"{p}.k_proj.weight"].T).reshape(B, S, nkv, hd)
        v = (x @ w[f"{p}.v_proj.weight"].T).reshape(B, S, nkv, hd)
        q = rmsnorm(q, w[f"{p}.q_norm.weight"])
        k = rmsnorm(k, w[f"{p}.k_norm.weight"])
        q = self.apply_rope(q[0], cos[KV - S:KV], sin[KV - S:KV])
        k = self.apply_rope(k[0], cos[KV - S:KV], sin[KV - S:KV])
        cache[f"{p}.k"] = k if f"{p}.k" not in cache else np.concatenate([cache[f"{p}.k"], k], 0)
        cache[f"{p}.v"] = v[0] if f"{p}.v" not in cache else np.concatenate([cache[f"{p}.v"], v[0]], 0)
        Kf, Vf = cache[f"{p}.k"], cache[f"{p}.v"]
        rep = nh // nkv
        Kf = np.repeat(Kf, rep, 1)
        Vf = np.repeat(Vf, rep, 1)
        att = np.einsum("qhd,khd->hqk", q, Kf) * hd ** -0.5 + mask
        att = att - att.max(-1, keepdims=True)
        p_att = np.exp(att)
        p_att /= p_att.sum(-1, keepdims=True)
        out = np.einsum("hqk,khd->qhd", p_att, Vf)
        out = out.reshape(S, -1) * sigmoid(gate[0])
        cache["kv_len"] = KV
        return out @ w[f"{p}.o_proj.weight"].T

    # --- MoE ---------------------------------------------------------------
    def moe(self, x, layer):
        w = self.w
        p = f"model.language_model.layers.{layer}.mlp"
        S = x.shape[1]
        flat = x.reshape(-1, x.shape[-1])
        logits = flat @ w[f"{p}.gate.weight"].T
        probs = np.exp(logits - logits.max(-1, keepdims=True))
        probs /= probs.sum(-1, keepdims=True)
        k = self.cfg["num_experts_per_tok"]
        top = np.argsort(-probs, -1)[:, :k]
        vals = np.take_along_axis(probs, top, -1)
        vals /= vals.sum(-1, keepdims=True)
        gu = w[f"{p}.experts.gate_up_proj"]
        dn = w[f"{p}.experts.down_proj"]
        out = np.zeros_like(flat)
        for t in range(flat.shape[0]):
            for j, e in enumerate(top[t]):
                g_u = flat[t] @ gu[e].T
                gate, up = g_u[: g_u.shape[0] // 2], g_u[g_u.shape[0] // 2:]
                h = _silu(gate) * up
                out[t] += (h @ dn[e].T) * vals[t, j]
        shared = _silu(flat @ w[f"{p}.shared_expert.gate_proj.weight"].T) * (flat @ w[f"{p}.shared_expert.up_proj.weight"].T)
        shared = shared @ w[f"{p}.shared_expert.down_proj.weight"].T
        gate_s = sigmoid(flat @ w[f"{p}.shared_expert_gate.weight"].T)
        return (out + gate_s * shared).reshape(x.shape)

    # --- gated residual ----------------------------------------------------
    def gated_residual(self, x, p, combine=True):
        w = self.w
        normed = rmsnorm(x, w[f"{p}.hc_norm.weight"], group=self.cfg["hidden_size"])
        mix = _silu(normed @ w[f"{p}.input_mix_weight_down.weight"].T / self.hc)
        mix = sigmoid(mix @ w[f"{p}.input_mix_weight_up.weight"].T)
        hc, hid = self.hc, self.cfg["hidden_size"]
        streams = normed.reshape(*x.shape[:-1], hc, hid)
        mixed = (mix.reshape(*streams.shape) * streams).mean(-2)
        if not combine:
            return mixed
        inj = 2 * sigmoid(normed @ w[f"{p}.block_inject_weight.weight"].T / self.hc)
        return mixed, x, inj

    # --- PLE ---------------------------------------------------------------
    def ngram_embedding(self, ids, layer, ple_layer_index, cache):
        p = f"model.language_model.layers.{layer}.ple.ple_embedding"
        w = self.w
        ctx_len = self.ngram_size - 1
        prev = cache.get(f"{p}.ctx")
        if prev is None:
            prev = np.full((1, ctx_len), self.eos, dtype=np.int64)
        if ids.shape[1] >= ctx_len:
            cache[f"{p}.ctx"] = ids[0, -ctx_len:][None, :]
        else:
            pad = np.full((1, ctx_len - ids.shape[1]), self.eos, dtype=ids.dtype)
            cache[f"{p}.ctx"] = np.concatenate([pad, ids], 1)
        history = np.concatenate([prev[0], ids[0]])

        def shift_eos(hist, shift):
            if shift == 0:
                return hist
            L = len(hist)
            pos = np.arange(L)
            eos_pos = np.where(hist == self.eos, pos, -1)
            prev_eos_incl = np.maximum.accumulate(eos_pos)
            prev_eos = np.concatenate([[-1], prev_eos_incl[:-1]])
            seg_start = prev_eos + 1
            pos_in_seg = pos - seg_start
            src = pos - shift
            gathered = hist[np.maximum(src, 0)]
            valid = (pos_in_seg >= shift) & (src >= 0)
            return np.where(valid, gathered, self.eos)

        shifted = [shift_eos(history, s) for s in range(self.ngram_size)]
        mults = build_layer_multipliers(
            self.cfg["vocab_size"], self.ngram_size, ple_layer_index, self.seed
        )
        sizes = self.ple_prime_sizes[ple_layer_index]
        offs = []
        off = 0
        for s in sizes:
            offs.append(off)
            off += s
        blocks = []
        for ngram in range(2, self.ngram_size + 1):
            h0 = (ngram - 2) * self.hpn
            mixed = shifted[0].astype(np.int64) * mults[0]
            for pp in range(1, ngram):
                mixed = np.bitwise_xor(mixed, shifted[pp].astype(np.int64) * mults[pp])
            ids_n = mixed[:, None] % np.array(sizes[h0:h0 + self.hpn])[None, :]
            blocks.append(ids_n + np.array(offs[h0:h0 + self.hpn])[None, :])
        ng = np.concatenate(blocks, -1)[-ids.shape[1]:]
        emb = w[f"{p}.ngram_embedding.weight"][ng]  # [S, heads, hd]
        return emb.reshape(1, ids.shape[1], -1)

    def ple(self, x, ids, layer, ple_layer_index, cache):
        w = self.w
        p = f"model.language_model.layers.{layer}.ple"
        hc, hid = self.hc, self.cfg["hidden_size"]
        emb = self.ngram_embedding(ids, layer, ple_layer_index, cache)
        key_n = rmsnorm(emb @ w[f"{p}.key_proj.weight"].T, w[f"{p}.norm_key.weight"], group=hid)
        value = emb @ w[f"{p}.value_proj.weight"].T
        query_n = rmsnorm(x, w[f"{p}.norm_query.weight"], group=hid)
        gate = (key_n.reshape(*x.shape[:-1], hc, hid) * query_n.reshape(*x.shape[:-1], hc, hid)).sum(
            -1, keepdims=True
        ) / math.sqrt(hid)
        gate = np.sign(gate) * np.sqrt(np.abs(gate).clip(1e-6))
        gv = sigmoid(gate) * value[:, :, None, :]
        gv_flat = gv.reshape(*x.shape[:2], hc * hid)
        gv_normed = rmsnorm(gv_flat, w[f"{p}.norm_conv.weight"], group=hid)
        conv_w = w[f"{p}.conv1d.weight"][:, 0, :]
        K = conv_w.shape[-1]
        dilation = self.ngram_size
        state_len = (K - 1) * dilation
        conv_state = cache.get(f"{p}.conv")
        xf = gv_normed.transpose(0, 2, 1)
        if conv_state is not None:
            xf = np.concatenate([conv_state, xf], 2)
        cache[f"{p}.conv"] = xf[:, :, -state_len:]
        xf = np.pad(xf, ((0, 0), (0, 0), (state_len, 0)))[..., -(state_len + x.shape[1]):]
        out = _silu(causal_conv1d_dilated(xf, conv_w, K, dilation)).transpose(0, 2, 1)
        return gv_flat + out

    # --- forward -----------------------------------------------------------
    def layer(self, x, layer, cos, sin, ids, cache):
        cfg = self.cfg
        lt = cfg["layer_types"][layer]
        if layer + 1 in self.ple_layer_ids:
            x = x + self.ple(x, ids, layer, self.ple_layer_ids.index(layer + 1), cache)
        p = f"model.language_model.layers.{layer}.attn_hyper_connection"
        mixed, hyper, inj = self.gated_residual(x, p)
        if lt == "linear_attention":
            h = self.gated_delta_net(mixed, layer, cache)
        else:
            h = self.attention(mixed, layer, cos, sin, cache)
        h = h[None]  # [B, S, H]
        p = f"model.language_model.layers.{layer}.mlp_hyper_connection"
        mixed, hyper, inj = self.gated_residual(x, p)
        h = self.moe(mixed, layer)
        return hyper + (h[:, :, None, :] * inj[..., :, None]).reshape(hyper.shape)

    def forward(self, ids, cache=None):
        if cache is None:
            cache = {"kv_len": 0}
        w = self.w
        x = w["model.language_model.embed_tokens.weight"][ids]
        S = x.shape[1]
        off = cache["kv_len"]
        # full-history rope tables: the QSA indexer ropes pooled key blocks at
        # absolute block-start positions
        pos3 = np.stack([np.arange(off + S)] * 3)
        cos, sin = self.rope(pos3)
        x = np.repeat(x, self.hc, -1)
        for i in range(self.cfg["num_hidden_layers"]):
            x = self.layer(x, i, cos, sin, ids, cache)
        mixed = self.gated_residual(
            x, "model.language_model.hyper_connection_mixer", combine=False
        )
        return mixed @ w["language_model.lm_head.weight"].T


def _silu(x):
    return x / (1.0 + np.exp(-x))


def causal_conv1d_dilated(x, weight, kernel, dilation):
    B, C, L = x.shape
    out_len = L - (kernel - 1) * dilation
    out = np.zeros((B, C, out_len))
    for k in range(kernel):
        out += weight[:, k][:, None] * x[:, :, k * dilation: k * dilation + out_len]
    return out
