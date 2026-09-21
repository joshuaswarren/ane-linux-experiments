#!/bin/bash
# build_tools_worker.sh — Compile the mlx-omarchy-ane-worker TOOLS binary
# (the CLI with serve_resident) directly with g++, bypassing the CMake
# NOT TARGET guard that prevented the tools variant from building.
set -e
cd /tmp/parakeet-perf-resident/build-lever
OUT=/tmp/parakeet-perf-resident/mlx-omarchy-ane-worker-tools
SRC=/var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx/tools/mlx-omarchy-ane-worker/main.cpp
WORKER_LIBANE=/var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx/mlx/backend/omarchy/ane/worker_libane.cpp
INCLUDES=(
  -I/var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx
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
