#!/usr/bin/env bash
# Profile one decode token + one prefill pass using a fresh diagnostics
# wheel built from the current worktree at /var/tmp/jwm1-gpu-parity-wt.
# Acquire /tmp/m1-gpu.lock for the entire measurement window; service is
# not present on jwm1 (no llm-inference.service), so no service trap is
# needed.
#
# Usage: run_profile_window.sh <DIAG_VENV> <MODEL>
# DIAG_VENV is created if missing; the build dir is /var/tmp/m1-profbuild
# (kept under 2 GB; /var/tmp has 386 GB free on jwm1).
set -euo pipefail
DIAG_VENV="${1:?diag venv path}"
MODEL="${2:?model path}"

WT=/var/tmp/jwm1-gpu-parity-wt
BUILD=/var/tmp/m1-profbuild
LOCK=/tmp/m1-gpu.lock
VENVPY="${DIAG_VENV}/bin/python"

mkdir -p "${BUILD}" "$(dirname "${DIAG_VENV}")" /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw/profile

# 1. Build a diagnostics wheel in the worktree at the current HEAD.
( cd "${WT}" && DEV_RELEASE=1 MLX_OMARCHY_WORK_DIR="${BUILD}" ./scripts/build-wheel.sh --diagnostics )

WHL=$(ls -1 "${WT}"/dist/*+diag.*.whl | head -1)
[ -n "${WHL}" ] || { echo "no diag wheel produced in ${WT}/dist"; exit 1; }
echo "diag wheel: ${WHL}"

# 2. Clone the diag venv from a known-good production venv on jwm1 (we
#    reuse v072-venv-fused's mlx-lm config so the graph is identical).
if [ ! -x "${VENVPY}" ]; then
  python3 -m venv "${DIAG_VENV}"
  "${VENVPY}" -m pip install --quiet --no-deps "${WHL}"
  # install the same mlx-lm and patches that v072-venv-fused ships with
  "${VENVPY}" -m pip install --quiet "mlx-lm==0.31.3"
  # the batchbudget/vprof path wires the same mlx-lm patches via
  # apply-mlx-lm-patches.sh; copy the scripts + patches so the diag venv
  # matches the production graph.
  if [ -d /var/tmp/vp/wt/scripts ] && [ -d /var/tmp/vp/wt/patches ]; then
    rsync -a /var/tmp/vp/wt/scripts/ /var/tmp/jwm1-gpu-parity-wt/scripts/ || true
    rsync -a /var/tmp/vp/wt/patches/ /var/tmp/jwm1-gpu-parity-wt/patches/ || true
  fi
fi

OUT_DIR=/var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw/profile
TAG=$(date -u +%Y%m%dT%H%M%SZ)

# 3. Profile under flock; emit markers + GPU profile + analyzed output.
(
  flock -w 1800 9
  MLX_DISABLE_COMPILE=1 \
    MLX_OMARCHY_GPU_PROFILE="${OUT_DIR}/prof-${TAG}.jsonl" \
    "${VENVPY}" /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/prof_decode.py \
      --model "${MODEL}" \
      --prompts $HOME/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl \
      --prompt-idx 0 --new-tokens 32 \
      --markers "${OUT_DIR}/markers-${TAG}.jsonl"
  "${VENVPY}" /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/profile_analyze.py \
    --profile "${OUT_DIR}/prof-${TAG}.jsonl" \
    --markers "${OUT_DIR}/markers-${TAG}.jsonl" \
    --out-prefix "${OUT_DIR}/analyze-${TAG}"
) 9>"${LOCK}"

echo "profile written: ${OUT_DIR}/analyze-${TAG}.{kernels,timeline,prefill,summary.json,fields.txt}"
