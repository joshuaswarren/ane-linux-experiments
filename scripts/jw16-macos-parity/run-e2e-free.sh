#!/bin/bash
# Launch e2e_free.py with the environment of run-contract-resident.sh (whole-encoder ANE via the in-process shim).
# Call from inside gpuwin.sh (GPU lock/service discipline). usage: run-e2e-free.sh OUT.jsonl [--valid-frames mask|full] [--reps N] [--only STR]
set -u
OUT="${1:?out jsonl}"; shift
R=/var/tmp/parakeet-recover
PY=${PY:-/var/tmp/v072-venv-fused/bin/python3}
MODEL=$(echo "$HOME"/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c*)
W_ENC=/var/tmp/encoder-whole
SCRATCH=$(mktemp -d /var/tmp/e2e-free-scratch.XXXXXX)
exec env -u PYTHONPATH -u LD_LIBRARY_PATH -u MLX_OMARCHY_GPU_PROFILE -u ANE_OP_WALL -u MLX_OMARCHY_SPIRV_CACHE \
  MLX_OMARCHY_PLACED=AC ANE_ISLAND_MODE=inprocess ANE_INPROC_SHIM="$R/libane_inproc.so" \
  MLX_OMARCHY_FUSED_AB=0 MLX_OMARCHY_PIPE_OPS= MLX_OMARCHY_DEFER_COMMIT=1 \
  "$PY" /var/tmp/appbar/e2e_free.py --corpus /var/tmp/parakeet-corpus --out "$OUT" --model "$MODEL" --pkg "$R/pkg" \
    --encoder-runner "$R/ane_whole_worker_resident.py" --source "$R/encoder-source" --bundles "$R/bundles" \
    --worker "$W_ENC/build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker" --libane "$W_ENC/libane-strict.so" \
    --scratch "$SCRATCH" "$@"
