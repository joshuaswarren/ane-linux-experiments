#!/usr/bin/env python3
"""Full attention on the Apple Neural Engine, including both activation matmuls.

This closes the gap left in scripts/ane-transformer.py, where Q@K^T and
attn@V ran on the CPU. The reason given was that the ANE gemm reads its weights
from the kernel-weight DMA blob, so it computes W @ x and never x @ y.

That framing was too pessimistic. The gemm computes:

    out[o] = sum_i W[o][i] * x[i]        o < 512, i < 256

An activation can play the role of W. Both attention products fall out of it:

  Q@K^T:   scores[t][s] = sum_i K[s][i] * Q[t][i]
           so put K in the blob (rows 0..T-1, rest zero) and feed Q[t] as x.
           K does not change across t, so the blob is built once and reused
           for all T queries.

  attn@V:  out[t][j]    = sum_s V[s][j] * attn[t][s]
           so put V-transpose in the blob and feed attn[t] as x. Also one
           blob for all T rows.

The "CPU re-layout per step" that looked prohibitive is just to_blob() on a
numpy array, the same call already used for real weights. The genuine cost is
the 512 KB weight blob written and DMA'd per distinct matrix, not the index
arithmetic, which is why both helpers below build their blob once.

With this plus scripts/ane-softmax.py, every arithmetic step of a
transformer block runs on the engine: QKV projections, scores, the 1/sqrt(d)
scale, softmax, the attention-weighted sum, and the feed-forward network.

  usage: python3 ane-attention.py            # verify vs numpy
         python3 ane-attention.py --repeat 3 # stability
"""
import os
import runpy
import sys

import numpy as np

_repeats = 1
if "--repeat" in sys.argv:
    _repeats = int(sys.argv[sys.argv.index("--repeat") + 1])
_saved_argv, sys.argv = sys.argv, [sys.argv[0]]

_here = os.path.dirname(os.path.abspath(__file__))


def _find(name):
    for cand in (os.path.join(_here, name),
                 os.path.expanduser(f"~/ane-boot/{name}"),
                 os.path.expanduser(f"~/src/ane-linux-experiments/{name}")):
        if os.path.exists(cand):
            return cand
    sys.exit(f"{name} not found")


NET = runpy.run_path(_find("ane-network.py"), run_name="net_harvest")
SM = runpy.run_path(_find("ane-softmax.py"), run_name="sm_harvest")
sys.argv = _saved_argv

run_gemm = NET["run_gemm"]
relu_ane = NET["relu_ane"]
C_GEMM = NET["C_GEMM"]      # 512 output channels
K_GEMM = NET["K_GEMM"]      # 256 live input channels
N_WEIGHTS = NET["N_WEIGHTS"]

softmax_ane_row = SM["softmax_ane_row"]
run_ew = SM["run_ew"]
_const = SM["_const"]
C_EW = SM["C_EW"]


def to_blob(W):
    """(512,256) fp16 -> weight blob. 16 tiles x 16384; W[o][i] at
    tile(o//32)*16384 + 6 + i*32 + (o%32). Probe-decoded, see ane-network.py."""
    blob = np.zeros(N_WEIGHTS, dtype=np.float16)
    for t in range(16):
        base = t * 16384 + 6
        blob[base:base + K_GEMM * 32] = W[32 * t:32 * t + 32].T.reshape(-1)
    return blob


def _as_weight_matrix(rows):
    """Pad an (n, d) activation up to the gemm's (512, 256) weight shape."""
    W = np.zeros((C_GEMM, K_GEMM), dtype=np.float16)
    n, d = rows.shape
    W[:n, :d] = rows
    return W


def qk_scores_ane(Q, K):
    """scores[t][s] = dot(Q[t], K[s]), computed on the ANE. K goes in the blob."""
    T = Q.shape[0]
    blob = to_blob(_as_weight_matrix(K))          # built once, reused per query
    out = np.empty((T, T), dtype=np.float32)
    for t in range(T):
        row = run_gemm(blob, Q[t].astype(np.float16))
        out[t] = row[:T].astype(np.float32)
    return out


def av_ane(attn, V):
    """out[t][j] = sum_s attn[t][s]*V[s][j], on the ANE. V-transpose in the blob."""
    T = attn.shape[0]
    d = V.shape[1]
    blob = to_blob(_as_weight_matrix(V.T[:K_GEMM]))   # V^T is (d, T)
    out = np.empty((T, d), dtype=np.float32)
    for t in range(T):
        x = np.zeros(K_GEMM, dtype=np.float16)
        x[:T] = attn[t]
        row = run_gemm(blob, x)
        out[t] = row[:d].astype(np.float32)
    return out


def scale_ane(scores, factor):
    """Multiply a score row by a constant on the ANE (elementwise mul)."""
    T = len(scores)
    padded = np.zeros(C_EW, dtype=np.float16)
    padded[:T] = scores
    scaled = run_ew("mul", padded, _const(np.float16(factor)))
    return scaled[:T].astype(np.float32)


def attention_ane(Q, K, V):
    """Whole attention block on the engine: scores, scale, softmax, weighted sum."""
    T = Q.shape[0]
    scores = qk_scores_ane(Q, K)
    inv_sqrt_d = float(1.0 / np.sqrt(K_GEMM))
    scaled = np.stack([scale_ane(scores[t], inv_sqrt_d) for t in range(T)])
    probs = np.stack([softmax_ane_row(scaled[t]) for t in range(T)])
    return av_ane(probs.astype(np.float16), V), scores, probs


def attention_ref(Q, K, V):
    Q32, K32, V32 = Q.astype(np.float32), K.astype(np.float32), V.astype(np.float32)
    scores = Q32 @ K32.T
    scaled = scores / np.sqrt(K_GEMM)
    e = np.exp(scaled - scaled.max(axis=-1, keepdims=True))
    probs = e / e.sum(axis=-1, keepdims=True)
    return probs @ V32, scores, probs


def main():
    rng = np.random.default_rng(3)
    T = 4
    Q = (rng.standard_normal((T, K_GEMM)) * 0.3).astype(np.float16)
    K = (rng.standard_normal((T, K_GEMM)) * 0.3).astype(np.float16)
    V = (rng.standard_normal((T, K_GEMM)) * 0.3).astype(np.float16)

    for i in range(_repeats):
        got, scores, probs = attention_ane(Q, K, V)
        ref, ref_scores, ref_probs = attention_ref(Q, K, V)

        s_err = np.abs(scores - ref_scores).max()
        p_err = np.abs(probs - ref_probs).max()
        o_err = np.abs(got - ref).max()
        print(f"run {i + 1}: "
              f"scores_max_err={s_err:.4f} "
              f"probs_max_err={p_err:.4f} "
              f"out_max_err={o_err:.4f} "
              f"argmax_match={np.array_equal(got.argmax(-1), ref.argmax(-1))}")

    print()
    print("scores[0]      =", scores[0])
    print("scores_ref[0]  =", ref_scores[0])
    print("probs[0]       =", probs[0], "sum", probs[0].sum())
    print("probs_ref[0]   =", ref_probs[0])
    print("out[0][:5]     =", got[0, :5])
    print("out_ref[0][:5] =", ref[0, :5])


if __name__ == "__main__":
    main()
