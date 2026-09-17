#!/bin/bash
# ParakeetTransport: full jwm1 cycle for one pt commit — fetch, re-prepare,
# rebuild wheel, redeploy tree, recompile the serve worker, re-pin libmlx.
# Usage: pt-rebuild-jwm1.sh <commit-sha>
set -euo pipefail
COMMIT=$1
git -C "$HOME/src/mlx-omarchy" fetch -q origin agent/parakeet-transport
git -C "$HOME/src/mlx-omarchy" worktree remove --force /var/tmp/pt-src 2>/dev/null || true
git -C "$HOME/src/mlx-omarchy" worktree add --detach /var/tmp/pt-src "$COMMIT" 2>&1 | tail -1
mkdir -p /var/tmp/pt/dist /var/tmp/pt/logs /var/tmp/pt-src/.work
cp "$HOME/src/mlx-omarchy-resid/.work/mlx-0.32.2-1f8e74e3f12f31365464a6867c6579f0e9b29d85.tar.gz" /var/tmp/pt-src/.work/
cd /var/tmp/pt-src
MLX_OMARCHY_WORK_DIR=/var/tmp/pt-src/.work scripts/prepare-mlx.sh > /var/tmp/pt/logs/prepare.log 2>&1
rm -rf /var/tmp/pt/mlx
rsync -a /var/tmp/pt-src/.work/mlx/ /var/tmp/pt/mlx/
cd /var/tmp/pt/mlx
export CMAKE_ARGS="-DMLX_BUILD_OMARCHY=ON -DMLX_BUILD_CPU=ON -DMLX_BUILD_METAL=OFF -DMLX_BUILD_CUDA=OFF -DMLX_BUILD_TESTS=OFF -DMLX_BUILD_EXAMPLES=OFF -DMLX_BUILD_BENCHMARKS=OFF -DMLX_OMARCHY_ANE_SOURCE_DIR=/var/tmp/omarchy-ane-6fa243a"
export CMAKE_BUILD_PARALLEL_LEVEL=6
export CMAKE_BUILD_TYPE=Release
export DEV_RELEASE=1
export MLX_OMARCHY_LOCAL_VERSION=pt.$COMMIT
export MLX_OMARCHY_SOURCE_COMMIT=$COMMIT
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
"$HOME/src/mlx-omarchy-resid/.work/venv-build/bin/python" -m pip wheel --no-build-isolation --no-deps --wheel-dir /var/tmp/pt/dist /var/tmp/pt/mlx
shopt -s nullglob
WHEEL=$(ls -t /var/tmp/pt/dist/mlx_omarchy-*.whl | head -1)
echo "[receipt] wheel: $WHEEL"
echo "[receipt] sha256: $(sha256sum "$WHEEL" | awk '{print $1}')"
# deploy fresh tree
rm -rf /var/tmp/pt-wheelx
mkdir -p /var/tmp/pt-wheelx
cd /var/tmp/pt-wheelx
python3 -m zipfile -e "$WHEEL" .
chmod +x mlx/bin/* 2>/dev/null || true
# serve worker exe (wheel target collision: backend runtime worker wins the name)
g++ -O2 -std=c++17 -fPIC \
  -DMLX_OMARCHY_ANE_DEVICE=1 \
  -I/var/tmp/pt/mlx -I/var/tmp/omarchy-ane-6fa243a/libane \
  /var/tmp/pt/mlx/tools/mlx-omarchy-ane-worker/main.cpp \
  /var/tmp/pt/mlx/mlx/backend/omarchy/ane/worker_libane.cpp \
  -L/var/tmp/pt-wheelx/mlx/lib -lmlx -ldl \
  -Wl,-rpath,'$ORIGIN/../lib' \
  -o /var/tmp/pt-wheelx/mlx/bin/mlx-omarchy-ane-worker
chmod +x /var/tmp/pt-wheelx/mlx/bin/mlx-omarchy-ane-worker
sha256sum /var/tmp/pt-wheelx/mlx/lib/libmlx.so | awk '{print $1}' > /var/tmp/jwm1-pt/expected-libmlx.sha256
echo "[receipt] libmlx: $(cat /var/tmp/jwm1-pt/expected-libmlx.sha256)"
echo "[receipt] worker: $(sha256sum /var/tmp/pt-wheelx/mlx/bin/mlx-omarchy-ane-worker | awk '{print $1}')"
