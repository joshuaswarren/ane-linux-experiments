#!/usr/bin/env bash
# Run the frozen contract (benchmarks/qwen38-2b-contract.json) under
# flock. --limit 10 (10 prompts per pass) x --passes 10 = n=100;
# warmup 3, 32 new tokens greedy, --prefill-tokens 512. Mirrors the
# pattern in /var/tmp/vprof/window-umalimit.sh.
#
# Usage: run_contract_window.sh <VENV> <MODEL_DIR> <TAG>
set -euo pipefail
VENV="${1:?venv path}"
MODEL_DIR="${2:?hf snapshot dir}"
TAG="${3:?output tag}"
VENVPY="${VENV}/bin/python"
LOCK=/tmp/m1-gpu.lock
BENCH=$HOME/src/ane-linux-experiments/benchmarks/qwen38-mlx-bench.py
PROMPTS=$HOME/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl
OUT=/var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw/contract
mkdir -p "${OUT}"
(
  flock -w 1800 9
  MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG="${TAG}" "${VENVPY}" "${BENCH}" \
    --model "${MODEL_DIR}" --prompts "${PROMPTS}" \
    --limit 10 --warmup 3 --passes 10 --new-tokens 32 --prefill-tokens 512 \
    --label "${TAG}" \
    --out "${OUT}/contract-${TAG}.json" \
    2> "${OUT}/console-${TAG}.log"
) 9>"${LOCK}"
echo "contract: ${OUT}/contract-${TAG}.json"
