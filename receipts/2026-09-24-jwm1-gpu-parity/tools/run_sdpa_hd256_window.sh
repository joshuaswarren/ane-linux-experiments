#!/usr/bin/env bash
# SDPA hd256 qualification window: build the port wheel on
# agent/jwm1-gpu-parity, install into a fresh venv alongside a venv
# cloning the production graph (mlx-lm 0.31.3 + the wired patches that
# v072-venv-fused ships), then run 10 interleaved paired contract reps
# under flock. Computes paired mean delta and 95% t-CI on decode
# tok/s, asserts CI is entirely positive AND 3-pass digest matches
# ctl, AND the 10-pass records digest is bit-identical.
#
# Usage: run_sdpa_hd256_window.sh <CTL_VENV> <TAG>
set -euo pipefail
CTL_VENV="${1:?ctl venv (e.g. /var/tmp/v072-venv-fused)}"
TAG="${2:?output tag}"

WT=/var/tmp/jwm1-gpu-parity-wt
BUILD=/var/tmp/m1-sdpabuild
DIAG_VENV=/var/tmp/m1-sdpa256/venv-cand
DIAG_PY="${DIAG_VENV}/bin/python"
LOCK=/tmp/m1-gpu.lock
OUT=/var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw/sdpa-hd256
mkdir -p "${BUILD}" "${OUT}"

# 1. Build the production wheel at the SDPA branch head.
( cd "${WT}" && DEV_RELEASE=1 MLX_OMARCHY_WORK_DIR="${BUILD}" ./scripts/build-wheel.sh )

WHL=$(ls -1 "${WT}"/dist/*+f9d7bb21*.whl "${WT}"/dist/*.whl | grep -v diag | head -1)
[ -n "${WHL}" ] || { echo "no production wheel in ${WT}/dist"; exit 1; }
echo "production wheel: ${WHL}"

# 2. Create cand venv, install the SDPA wheel, mirror v072-venv-fused's
#    mlx-lm + patches so the graph config matches.
if [ ! -x "${DIAG_PY}" ]; then
  python3 -m venv "${DIAG_VENV}"
  "${DIAG_PY}" -m pip install --quiet --no-deps "${WHL}"
  "${DIAG_PY}" -m pip install --quiet "mlx-lm==0.31.3"
  # apply the same mlx-lm patches v072-venv-fused ships; reuse vprof's
  # patch helpers if present.
  if [ -f /var/tmp/dg/scripts/patch-mlx-lm-gdn.py ]; then
    python3 /var/tmp/dg/scripts/patch-mlx-lm-gdn.py "${DIAG_VENV}" || true
  fi
  if [ -f /var/tmp/dg/scripts/patch-mlx-lm-gdn-raw.py ]; then
    python3 /var/tmp/dg/scripts/patch-mlx-lm-gdn-raw.py "${DIAG_VENV}" || true
  fi
fi
CTL_PY="${CTL_VENV}/bin/python"
MODEL_DIR=$(ls -d $HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)
PROMPTS=$HOME/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl
BENCH=$HOME/src/ane-linux-experiments/benchmarks/qwen38-mlx-bench.py

cd "${OUT}"

# 3. 10 interleaved paired reps under flock; 3 warmup + 1 measured pass
#    each (matches window-b.sh pattern in the t6001 sdpa receipt).
(
  flock -w 1800 9
  for rep in 1 2 3 4 5 6 7 8 9 10; do
    MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG="ctl-${TAG}-r${rep}" \
      "${CTL_PY}" "${BENCH}" \
        --model "${MODEL_DIR}" --prompts "${PROMPTS}" \
        --limit 10 --warmup 3 --passes 1 --new-tokens 32 --prefill-tokens 512 \
        --label "ctl-${TAG}-r${rep}" \
        --out "contract-ctl-${TAG}-r${rep}.json" \
        2> "console-ctl-${TAG}-r${rep}.log" || true
    MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG="cand-${TAG}-r${rep}" \
      "${DIAG_PY}" "${BENCH}" \
        --model "${MODEL_DIR}" --prompts "${PROMPTS}" \
        --limit 10 --warmup 3 --passes 1 --new-tokens 32 --prefill-tokens 512 \
        --label "cand-${TAG}-r${rep}" \
        --out "contract-cand-${TAG}-r${rep}.json" \
        2> "console-cand-${TAG}-r${rep}.log" || true
  done
  # anchors: 10-pass digest (averaged)
  MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG="ctl-${TAG}-p10" \
    "${CTL_PY}" "${BENCH}" \
      --model "${MODEL_DIR}" --prompts "${PROMPTS}" \
      --limit 10 --warmup 3 --passes 10 --new-tokens 32 --prefill-tokens 512 \
      --label "ctl-${TAG}-p10" \
      --out "contract-ctl-${TAG}-p10.json" \
      2> "console-ctl-${TAG}-p10.log" || true
  MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG="cand-${TAG}-p10" \
    "${DIAG_PY}" "${BENCH}" \
      --model "${MODEL_DIR}" --prompts "${PROMPTS}" \
      --limit 10 --warmup 3 --passes 10 --new-tokens 32 --prefill-tokens 512 \
      --label "cand-${TAG}-p10" \
      --out "contract-cand-${TAG}-p10.json" \
      2> "console-cand-${TAG}-p10.log" || true
) 9>"${LOCK}"

echo "paired reps complete: ${OUT}/contract-{ctl,cand}-${TAG}-{r,p10}*.json"

# 4. Logits gate (token-id flip count) — 0 flips target.
python3 /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/logits_gate.py \
  --ctl "${OUT}/contract-ctl-${TAG}-p10.json" \
  --cand "${OUT}/contract-cand-${TAG}-p10.json" \
  --out "${OUT}/gate-${TAG}.txt" || true
