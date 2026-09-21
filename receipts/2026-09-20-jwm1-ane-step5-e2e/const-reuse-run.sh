#!/bin/bash
# const-reuse-run.sh — single-pass const-reuse + boundary run via the overlay lane.
set -uo pipefail

RUN=/var/tmp/jwm1-ane-step2/fused-e2e/const-reuse-lane
PY=/var/tmp/jwm1-v072rc1/venv/bin/python3
RUNNER=/var/tmp/jwm1-ane-step2/fused-e2e/const-reuse-lane/vulkan_encoder.py
MODEL=/home/joshuawarren/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
WORKER=/var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=/var/tmp/jwm1-ane-step2/libane.so
ICD=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json
TS=$(date +%Y%m%dT%H%M%S)
OUT=/var/tmp/jwm1-ane-step2/fused-e2e/const-reuse-run-$TS
SCRATCH=/var/tmp/jwm1-ane-step2/fused-e2e/scratch-const-reuse-$TS
mkdir -p "$OUT" "$SCRATCH"

export VK_DRIVER_FILES=$ICD
export MLX_OMARCHY_PLACED=AC
export MLX_OMARCHY_ENCODER_CONST_CACHE=1
unset PYTHONPATH LD_LIBRARY_PATH ANE_ISLAND_MODE MLX_OMARCHY_SPIRV_CACHE HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL || true

"$PY" "$RUN/fused_e2e.py" \
  --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
  --golden /var/tmp/EncoderParityAne/capture \
  --model "$MODEL" \
  --pkg /var/tmp/TdtLoopDefault/pkg \
  --encoder-runner "$RUNNER" \
  --source /var/tmp/IslandsExecJwm1/encoder-source \
  --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
  --bundles /var/tmp/jwm1-ane-step2/bundles \
  --worker "$WORKER" \
  --libane "$LIBANE" \
  --scratch "$SCRATCH" --out "$OUT" \
  --deadline-ms 20000 > "$OUT/stdout.log" 2>&1
RC=$?
echo "rc=$RC out=$OUT"
echo "=== const-reuse-result ==="
cat "$OUT/const-reuse-result.json" 2>/dev/null || tail -12 "$OUT/stdout.log"
