#!/usr/bin/env python3
"""A whole transformer block on the Apple Neural Engine. No CPU arithmetic.

Every arithmetic step runs on the engine:

    q,k,v   = Wq@x, Wk@x, Wv@x          gemm, weights in the DMA blob
    scores  = Q@K^T                     gemm, K in the DMA blob
    scaled  = scores * (1/sqrt(d))      elementwise mul
    probs   = softmax(scaled)           range-reduced Taylor exp,
                                        Newton-Raphson reciprocal,
                                        pairwise-halving max and sum
    attn    = probs@V                   gemm, V-transpose in the DMA blob
    out     = W2@relu(W1@attn)          gemm, elementwise max, gemm

The CPU moves fp16 buffers between calls and builds weight blobs. It performs
no adds, multiplies, exponentials, or divides that contribute to the result.

Compare against scripts/ane-transformer.py, which ran Q@K^T, attn@V, and
(originally) softmax on the CPU.

  usage: python3 ane-block.py            # verify vs numpy
         python3 ane-block.py --repeat 3 # stability
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


ATT = runpy.run_path(_find("ane-attention.py"), run_name="att_harvest")
sys.argv = _saved_argv

run_gemm = ATT["run_gemm"]
relu_ane = ATT["relu_ane"]
to_blob = ATT["to_blob"]
attention_ane = ATT["attention_ane"]
C_GEMM = ATT["C_GEMM"]
K_GEMM = ATT["K_GEMM"]


def gemm(W, x):
    return run_gemm(to_blob(W), x.astype(np.float16))


def block_ane(X, Wq, Wk, Wv, W1, W2):
    T = X.shape[0]
    d = K_GEMM

    Q = np.stack([gemm(Wq, X[t])[:d] for t in range(T)]).astype(np.float16)
    K = np.stack([gemm(Wk, X[t])[:d] for t in range(T)]).astype(np.float16)
    V = np.stack([gemm(Wv, X[t])[:d] for t in range(T)]).astype(np.float16)

    attn, _, _ = attention_ane(Q, K, V)

    attn16 = attn.astype(np.float16)
    return np.stack([gemm(W2, relu_ane(gemm(W1, attn16[t]))[:d]) for t in range(T)])


def block_ref(X, Wq, Wk, Wv, W1, W2):
    X32 = X.astype(np.float32)
    d = K_GEMM
    Q = (Wq.astype(np.float32) @ X32.T).T[:, :d]
    K = (Wk.astype(np.float32) @ X32.T).T[:, :d]
    V = (Wv.astype(np.float32) @ X32.T).T[:, :d]

    scaled = (Q @ K.T) / np.sqrt(d)
    e = np.exp(scaled - scaled.max(axis=-1, keepdims=True))
    attn = (e / e.sum(axis=-1, keepdims=True)) @ V

    h = np.maximum(W1.astype(np.float32) @ attn.T, 0).T
    return (W2.astype(np.float32) @ h[:, :d].T).T


def main():
    rng = np.random.default_rng(5)
    T = 4
    X = (rng.standard_normal((T, K_GEMM)) * 0.4).astype(np.float16)
    Wq, Wk, Wv, W1, W2 = [
        (rng.standard_normal((C_GEMM, K_GEMM)) * 0.1).astype(np.float16)
        for _ in range(5)
    ]

    got = ref = None
    for i in range(_repeats):
        got = block_ane(X, Wq, Wk, Wv, W1, W2).astype(np.float32)
        ref = block_ref(X, Wq, Wk, Wv, W1, W2)
        err = np.abs(got - ref)
        print(f"run {i + 1}: shape={got.shape} max_abs_err={err.max():.4f} "
              f"mean_abs_err={err.mean():.4f} "
              f"argmax_match={np.array_equal(got.argmax(-1), ref.argmax(-1))}")

    print()
    print("out[0][:6] =", got[0, :6])
    print("ref[0][:6] =", ref[0, :6])

    # An argmax flip on 512 outputs is only meaningful if the top two
    # reference values are further apart than the observed error. Report the
    # margin so a near-tie is never mistaken for a wrong answer.
    print()
    print("argmax diagnostic, per row:")
    for t in range(got.shape[0]):
        srt = np.sort(ref[t])[::-1]
        margin = srt[0] - srt[1]
        gi, ri = int(got[t].argmax()), int(ref[t].argmax())
        verdict = "same" if gi == ri else (
            "flip within error" if margin <= np.abs(got[t] - ref[t]).max()
            else "FLIP EXCEEDS ERROR")
        print(f"  row {t}: ane_argmax={gi:>3} ref_argmax={ri:>3} "
              f"top1-top2_margin={margin:.5f} row_max_err={np.abs(got[t]-ref[t]).max():.5f} "
              f"-> {verdict}")


if __name__ == "__main__":
    main()
