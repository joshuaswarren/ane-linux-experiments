#!/bin/bash
# add_rpath.sh — Patch RUNPATH into the built worker binaries so they find
# libmlx.so without LD_LIBRARY_PATH (which breaks the venv's own mlx module).
set -e
for BIN in /tmp/parakeet-perf-resident/mlx-omarchy-ane-worker-tools /tmp/parakeet-perf-resident/mlx-omarchy-ane-worker-lever; do
  echo "=== patchelf $BIN ==="
  if command -v patchelf >/dev/null 2>&1; then
    patchelf --set-rpath /tmp/parakeet-perf-resident/build-lever "$BIN"
    patchelf --print-rpath "$BIN"
  else
    echo "patchelf not found; trying chrpath"
    chrpath -r /tmp/parakeet-perf-resident/build-lever "$BIN"
  fi
done
echo "=== DONE ==="
