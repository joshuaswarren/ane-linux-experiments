#!/bin/bash
# build_lever_worker.sh — Compile the mlx-omarchy-ane-worker TOOLS binary
# with the _IONBF + dropped per-output fflush LEVER.
set -e
cd /tmp/parakeet-perf-resident/build-lever
OUT=/tmp/parakeet-perf-resident/mlx-omarchy-ane-worker-lever
SRC=/tmp/parakeet-perf-resident/main_lever.cpp
WORKER_LIBANE=/var/tmp/ane-runtime/ane-v064-wt/.work/mlx/mlx/backend/omarchy/ane/worker_libane.cpp
INCLUDES=(
  -I/var/tmp/ane-runtime/ane-v064-wt/.work/mlx
  -I/tmp/omarchy-ane-pinned/libane
  -I/tmp/parakeet-perf-resident/build-lever
)
echo "=== BUILD $OUT ==="
g++ -O2 -std=c++17 -o "$OUT" \
  "${INCLUDES[@]}" \
  -DMLX_OMARCHY_ANE_DEVICE=1 \
  "$SRC" "$WORKER_LIBANE" \
  -L/tmp/parakeet-perf-resident/build-lever -lmlx -ldl
echo "=== BUILT ==="
sha256sum "$OUT"
