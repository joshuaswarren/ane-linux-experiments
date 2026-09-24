#!/usr/bin/env bash
# Full lane execution. Run once when jwm1 is mine (GPU lock available,
# ANE quiescent, M2FwStart-2 windows clear). Each phase is independently
# skippable via env flags so I can resume after a phase failure.
set -euo pipefail
LOCK=/tmp/m1-gpu.lock
DIAG_VENV=/var/tmp/m1-sdpa256/venv-diag
CAND_VENV=/var/tmp/m1-sdpa256/venv-cand
PROFILE_RAW=/var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw/profile
SDPA_RAW=/var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw/sdpa-hd256
CONTRACT_RAW=/var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw/contract
mkdir -p "${PROFILE_RAW}" "${SDPA_RAW}" "${CONTRACT_RAW}"

# Phase 0 — pre-flight (verify state).
echo "== PHASE 0: pre-flight =="
bash /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/pre_flight.sh 2>&1 | tee "${PROFILE_RAW}/preflight.log"

# Phase 1 — build the SDPA port wheel from /var/tmp/jwm1-gpu-parity-wt.
echo "== PHASE 1: build SDPA-port wheel =="
WT=/var/tmp/jwm1-gpu-parity-wt
( cd "${WT}" && DEV_RELEASE=1 MLX_OMARCHY_WORK_DIR=/dev/shm/m1-sdpabuild ./scripts/build-wheel.sh 2>&1 ) | tee "${SDPA_RAW}/build.log"
WHL=$(ls -1 "${WT}"/dist/*+f9d7bb21*.whl 2>/dev/null | head -1)
[ -z "${WHL}" ] && { echo "no SDPA wheel produced"; exit 1; }
echo "SDPA wheel: ${WHL}"

# Phase 2 — build the diagnostics wheel (same source commit, --diagnostics).
echo "== PHASE 2: build diag wheel at f9d7bb21 =="
( cd "${WT}" && MLX_OMARCHY_SOURCE_COMMIT=f9d7bb21 MLX_OMARCHY_WORK_DIR=/dev/shm/m1-profbuild ./scripts/build-wheel.sh --diagnostics 2>&1 ) | tee "${PROFILE_RAW}/diag-build.log"
DWHL=$(ls -1 "${WT}"/dist/*+diag.f9d7bb21*.whl 2>/dev/null | head -1)
[ -z "${DWHL}" ] && { echo "no diag wheel produced"; exit 1; }
echo "diag wheel: ${DWHL}"

# Phase 3 — create cand + diag venvs from the production venv's mlx-lm.
echo "== PHASE 3: venvs =="
for V in "${CAND_VENV}" "${DIAG_VENV}"; do
  if [ ! -x "${V}/bin/python" ]; then
    python3 -m venv "${V}"
    case "$V" in
      *cand*) "${V}/bin/pip" install --quiet --no-deps "${WHL}" ;;
      *diag*) "${V}/bin/pip" install --quiet --no-deps "${DWHL}" ;;
    esac
    "${V}/bin/pip" install --quiet "mlx-lm==0.31.3"
  fi
done

# Phase 4 — ctl contract (baseline).
echo "== PHASE 4: ctl contract (baseline) =="
bash /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/run_contract_window.sh /var/tmp/v072-venv-fused ctl 2>&1 | tee "${CONTRACT_RAW}/ctl.log"

# Phase 5 — cand contract (SDPA port).
echo "== PHASE 5: cand contract (SDPA port) =="
TAG="sdpa256"
(
  flock -w 1800 9
  for rep in 1 2 3 4 5 6 7 8 9 10; do
    MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG="ctl-${TAG}-r${rep}" \
      /var/tmp/v072-venv-fused/bin/python \
      $HOME/src/ane-linux-experiments/benchmarks/qwen38-mlx-bench.py \
        --model $HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/ \
        --prompts $HOME/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl \
        --limit 10 --warmup 3 --passes 1 --new-tokens 32 --prefill-tokens 512 \
        --label "ctl-${TAG}-r${rep}" \
        --out "${SDPA_RAW}/contract-ctl-${TAG}-r${rep}.json" \
        2> "${SDPA_RAW}/console-ctl-${TAG}-r${rep}.log" || true
    MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG="cand-${TAG}-r${rep}" \
      "${CAND_VENV}/bin/python" \
      $HOME/src/ane-linux-experiments/benchmarks/qwen38-mlx-bench.py \
        --model $HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/ \
        --prompts $HOME/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl \
        --limit 10 --warmup 3 --passes 1 --new-tokens 32 --prefill-tokens 512 \
        --label "cand-${TAG}-r${rep}" \
        --out "${SDPA_RAW}/contract-cand-${TAG}-r${rep}.json" \
        2> "${SDPA_RAW}/console-cand-${TAG}-r${rep}.log" || true
  done
  # 10-pass digest anchors
  MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG="ctl-${TAG}-p10" \
    /var/tmp/v072-venv-fused/bin/python \
    $HOME/src/ane-linux-experiments/benchmarks/qwen38-mlx-bench.py \
      --model $HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/ \
      --prompts $HOME/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl \
      --limit 10 --warmup 3 --passes 10 --new-tokens 32 --prefill-tokens 512 \
      --label "ctl-${TAG}-p10" \
      --out "${SDPA_RAW}/contract-ctl-${TAG}-p10.json" \
      2> "${SDPA_RAW}/console-ctl-${TAG}-p10.log" || true
  MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG="cand-${TAG}-p10" \
    "${CAND_VENV}/bin/python" \
    $HOME/src/ane-linux-experiments/benchmarks/qwen38-mlx-bench.py \
      --model $HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/ \
      --prompts $HOME/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl \
      --limit 10 --warmup 3 --passes 10 --new-tokens 32 --prefill-tokens 512 \
      --label "cand-${TAG}-p10" \
      --out "${SDPA_RAW}/contract-cand-${TAG}-p10.json" \
      2> "${SDPA_RAW}/console-cand-${TAG}-p10.log" || true
) 9>"${LOCK}"

# Phase 6 — paired-decode + logits gate.
echo "== PHASE 6: paired-decode + logits gate =="
python3 /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/paired_decode.py \
  --out-dir "${SDPA_RAW}" --tag "${TAG}" || true
python3 /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/logits_gate.py \
  --ctl "${SDPA_RAW}/contract-ctl-${TAG}-p10.json" \
  --cand "${SDPA_RAW}/contract-cand-${TAG}-p10.json" \
  --out "${SDPA_RAW}/gate-${TAG}.txt" || true

# Phase 7 — profile (decode + prefill) on the installed path.
echo "== PHASE 7: profile decode + prefill on installed path =="
(
  flock -w 1800 9
  TAG2="installed"
  MLX_DISABLE_COMPILE=1 MLX_OMARCHY_GPU_PROFILE="${PROFILE_RAW}/prof-${TAG2}.jsonl" \
    "${DIAG_VENV}/bin/python" \
    /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/prof_decode.py \
      --model $HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/ \
      --prompts $HOME/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl \
      --prompt-idx 0 --new-tokens 32 \
      --markers "${PROFILE_RAW}/markers-${TAG2}.jsonl"
  python3 /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/profile_analyze.py \
    --profile "${PROFILE_RAW}/prof-${TAG2}.jsonl" \
    --markers "${PROFILE_RAW}/markers-${TAG2}.jsonl" \
    --out-prefix "${PROFILE_RAW}/analyze-${TAG2}"
) 9>"${LOCK}"

# Phase 8 — SDPA per-shape microbench on cand.
echo "== PHASE 8: SDPA microbench (cand) =="
MLX_DISABLE_COMPILE=1 "${CAND_VENV}/bin/python" \
  /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/microbench_sdpa_hd256.py \
  --out "${SDPA_RAW}/microbench-cand.json" \
  --reps 300 || true
MLX_DISABLE_COMPILE=1 /var/tmp/v072-venv-fused/bin/python \
  /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/microbench_sdpa_hd256.py \
  --out "${SDPA_RAW}/microbench-ctl.json" \
  --reps 300 || true

# Phase 9 — family bench (per-op delta).
echo "== PHASE 9: family bench =="
bash /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/run_family_bench.sh \
  /var/tmp/v072-venv-fused \
  $HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/0867d98bfb174b042d88461c0e7c97b86b34b381 \
  /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw/families-installed-current.json \
  2>&1 | tee "${PROFILE_RAW}/family-bench.log"
python3 /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools/family_delta.py \
  --linux /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw/families-installed-current.json \
  --out /var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw/family-delta-current.md || true

echo "== done; outputs under ${PROFILE_RAW} and ${SDPA_RAW} =="
