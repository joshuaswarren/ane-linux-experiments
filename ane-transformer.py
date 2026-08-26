#!/usr/bin/env python3
"""Run one transformer block's tensor work on the Apple Neural Engine.

Two variants, both verified against a numpy reference:

  transformer_block_ane          - QKV + FFN on the ANE, softmax on CPU
  transformer_block_ane_softmax  - the same, but softmax also runs on the
                                    ANE (scripts/ane-softmax.py), built
                                    from composed add/mul/max/sq ops since no
                                    exp/reciprocal primitive has been found

What still runs on CPU in the softmax variant, and why: the two matrix
products QK^T and attn@V multiply two activations together, but the ANE
gemm sources its weights from the kernel-weight DMA blob decoded in
ane-network.py, not from a second activation buffer. Doing an
activation-by-activation product on the ANE needs a CPU re-layout of one
activation into that blob's tile format on every step - a materially larger,
undone engineering task, not a limitation of the softmax work.

Block structure (per token t of a 4-token sequence, d=256, per-head style):

    q_t, k_t, v_t = Wq @ x_t, Wk @ x_t, Wv @ x_t     (ANE gemm, 3 x 4)
    scores        = (Q K^T) / sqrt(d)                 (CPU numpy)
    attn          = softmax(scores) @ V               (ANE softmax, CPU matmul)
    ff            = W2 @ relu(W1 @ attn_t)            (ANE gemm x2 + relu)

Weight placement uses the probe-decoded tiled layout from
scripts/ane-network.py: 16 tiles x 16384 fp16, tile t feeding output
channels 32t..32t+31, W[o][i] at intra-tile offset 6 + i*32 + (o % 32).

  usage: python3 ane-transformer.py            # run + verify both variants
         python3 ane-transformer.py --repeat 3 # stability
"""
import runpy
import sys

import numpy as np

# Parse our own args before importing NET: the import chain runs
# examples/elementwise.py, which reads sys.argv[1] as its own mode selector.
# Leaving --repeat on argv makes it try to run as mode "--repeat" and fail.
_repeats = 1
if "--repeat" in sys.argv:
    _repeats = int(sys.argv[sys.argv.index("--repeat") + 1])
_saved_argv, sys.argv = sys.argv, [sys.argv[0]]

# The proven gemm/elementwise machinery from the MLP runner, plus softmax
# built from composed ANE primitives (no exp/reciprocal primitive exists;
# see scripts/ane-softmax.py for how it's built and validated).
import os as _os
_net_candidates = [
    _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "ane-network.py"),
    os.path.expanduser("~/ane-boot/ane-network.py"),
    os.path.expanduser("~/src/ane-linux-experiments/ane-network.py"),
]
_net_path = next((p_ for p_ in _net_candidates if _os.path.exists(p_)), None)
if _net_path is None:
    sys.exit("ane-network.py not found next to this script or in ane-boot/")
NET = runpy.run_path(_net_path, run_name="network_harvest")

_sm_candidates = [
    _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "ane-softmax.py"),
    os.path.expanduser("~/ane-boot/ane-softmax.py"),
    os.path.expanduser("~/src/ane-linux-experiments/ane-softmax.py"),
]
_sm_path = next((p_ for p_ in _sm_candidates if _os.path.exists(p_)), None)
if _sm_path is None:
    sys.exit("ane-softmax.py not found next to this script or in ane-boot/")
SM = runpy.run_path(_sm_path, run_name="softmax_harvest")
sys.argv = _saved_argv

run_gemm = NET["run_gemm"]
relu_ane = NET["relu_ane"]
C_GEMM = NET["C_GEMM"]   # 512
K_GEMM = NET["K_GEMM"]   # 256
N_WEIGHTS = NET["N_WEIGHTS"]
softmax_ane_row = SM["softmax_ane_row"]

def to_blob(W):
    blob = np.zeros(N_WEIGHTS, dtype=np.float16)
    for t in range(16):
        base = t * 16384 + 6
        blob[base:base + K_GEMM * 32] = W[32 * t:32 * t + 32].T.reshape(-1)
    return blob


def gemm(W, x):
    """W: (512,256) fp16, x: (256,) fp16 -> (512,) fp16, computed by the ANE."""
    return run_gemm(to_blob(W), x)


def transformer_block_ane(X, Wq, Wk, Wv, W1, W2):
    """X: (T,256). Returns (T,512) outputs with ANE matmuls, CPU softmax."""
    T = X.shape[0]
    Q = np.stack([gemm(Wq, X[t]) for t in range(T)])
    K = np.stack([gemm(Wk, X[t]) for t in range(T)])
    V = np.stack([gemm(Wv, X[t]) for t in range(T)])

    # Attention over the first 256 dims (the gemm's live output window).
    d = K_GEMM
    Qa, Ka, Va = Q[:, :d].astype(np.float32), K[:, :d].astype(np.float32), V[:, :d].astype(np.float32)
    scores = Qa @ Ka.T / np.sqrt(d)
    scores -= scores.max(axis=-1, keepdims=True)
    exp = np.exp(scores)
    attn = (exp / exp.sum(axis=-1, keepdims=True)) @ Va  # (T, d)

    # Feed-forward network back on the ANE.
    attn16 = attn.astype(np.float16)
    out = np.stack([gemm(W2, relu_ane(gemm(W1, attn16[t]))[:d]) for t in range(T)])
    return out


def transformer_block_ane_softmax(X, Wq, Wk, Wv, W1, W2):
    """Same block, but softmax itself runs on the ANE (scripts/ane-softmax.py).

    QK^T and attn@V still run on CPU: gemm sources its weights from the
    kernel-weight DMA blob, not from a second activation buffer, so an
    activation-by-activation product needs a CPU re-layout of one activation
    into that blob's tile format per step - a materially larger, undone
    engineering task, not a limit of the softmax work itself.
    """
    T = X.shape[0]
    Q = np.stack([gemm(Wq, X[t]) for t in range(T)])
    K = np.stack([gemm(Wk, X[t]) for t in range(T)])
    V = np.stack([gemm(Wv, X[t]) for t in range(T)])

    d = K_GEMM
    Qa, Ka, Va = Q[:, :d].astype(np.float32), K[:, :d].astype(np.float32), V[:, :d].astype(np.float32)
    scores = Qa @ Ka.T / np.sqrt(d)
    probs = np.stack([softmax_ane_row(scores[t]) for t in range(T)])  # ANE
    attn = probs @ Va

    attn16 = attn.astype(np.float16)
    out = np.stack([gemm(W2, relu_ane(gemm(W1, attn16[t]))[:d]) for t in range(T)])
    return out


def transformer_block_ref(X, Wq, Wk, Wv, W1, W2):
    Q = (Wq @ X.T).T.astype(np.float32)
    K = (Wk @ X.T).T.astype(np.float32)
    V = (Wv @ X.T).T.astype(np.float32)
    d = K_GEMM
    scores = Q[:, :d] @ K[:, :d].T / np.sqrt(d)
    scores -= scores.max(axis=-1, keepdims=True)
    exp = np.exp(scores)
    attn = (exp / exp.sum(axis=-1, keepdims=True)) @ V[:, :d]
    h = np.maximum(W1.astype(np.float32) @ attn.T, 0).T   # (T, 512)
    return (W2.astype(np.float32) @ h[:, :d].T).T          # slice to d=256, matching the ANE path


def main():
    rng = np.random.default_rng(7)
    T = 4
    X = (rng.standard_normal((T, K_GEMM)) * 0.5).astype(np.float16)
    Wq, Wk, Wv = [(rng.standard_normal((C_GEMM, K_GEMM)) * 0.1).astype(np.float16)
                  for _ in range(3)]
    W1 = (rng.standard_normal((C_GEMM, K_GEMM)) * 0.1).astype(np.float16)
    W2 = (rng.standard_normal((C_GEMM, K_GEMM)) * 0.1).astype(np.float16)

    repeats = _repeats
    got = ref = None
    for i in range(repeats):
        got = transformer_block_ane(X, Wq, Wk, Wv, W1, W2).astype(np.float32)
        ref = transformer_block_ref(X, Wq, Wk, Wv, W1, W2)
        err = np.abs(got - ref)
        print(f"cpu-softmax run {i + 1}: shape={got.shape} max_abs_err={err.max():.4f} "
              f"mean_abs_err={err.mean():.4f} argmax_match={np.argmax(got) == np.argmax(ref)}")
    print("out[0][:6] =", got[0, :6])
    print("ref[0][:6] =", ref[0, :6])

    print()
    print("--- softmax computed on the ANE (composed from add/mul/max/sq) ---")
    got2 = None
    for i in range(repeats):
        got2 = transformer_block_ane_softmax(X, Wq, Wk, Wv, W1, W2).astype(np.float32)
        err2 = np.abs(got2 - ref)
        print(f"ane-softmax run {i + 1}: shape={got2.shape} max_abs_err={err2.max():.4f} "
              f"mean_abs_err={err2.mean():.4f} argmax_match={np.argmax(got2) == np.argmax(ref)}")
    print("out2[0][:6] =", got2[0, :6])
    print("ref [0][:6] =", ref[0, :6])


if __name__ == "__main__":
    main()
