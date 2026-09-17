#!/bin/bash
# ParakeetTransport: build instrumentation wheel from agent/parakeet-transport
# on jwm1. Proven enc-attr2 recipe; venv + tarball reused from resid build.
set -euo pipefail
COMMIT=a1b4b9ce
git -C "$HOME/src/mlx-omarchy" fetch -q origin agent/parakeet-transport
git -C "$HOME/src/mlx-omarchy" worktree add --detach /var/tmp/pt-src "$COMMIT" 2>/dev/null || true
git -C /var/tmp/pt-src checkout -q --detach "$COMMIT"
mkdir -p /var/tmp/pt-src/.work /var/tmp/pt/dist /var/tmp/pt/logs
cp "$HOME/src/mlx-omarchy-resid/.work/mlx-0.32.2-1f8e74e3f12f31365464a6867c6579f0e9b29d85.tar.gz" /var/tmp/pt-src/.work/
cd /var/tmp/pt-src
MLX_OMARCHY_WORK_DIR=/var/tmp/pt-src/.work scripts/prepare-mlx.sh > /var/tmp/pt/logs/prepare.log 2>&1
rsync -a /var/tmp/pt-src/.work/mlx/ /var/tmp/pt/mlx/
cd /var/tmp/pt/mlx
export CMAKE_ARGS="-DMLX_BUILD_OMARCHY=ON -DMLX_BUILD_CPU=ON -DMLX_BUILD_METAL=OFF -DMLX_BUILD_CUDA=OFF -DMLX_BUILD_TESTS=OFF -DMLX_BUILD_EXAMPLES=OFF -DMLX_BUILD_BENCHMARKS=OFF -DMLX_OMARCHY_ANE_SOURCE_DIR=$HOME/src/omarchy-ane-lifecycle-rebase"
export CMAKE_BUILD_PARALLEL_LEVEL=6
export CMAKE_BUILD_TYPE=Release
export DEV_RELEASE=1
export MLX_OMARCHY_LOCAL_VERSION=pt.$COMMIT
export MLX_OMARCHY_SOURCE_COMMIT=$COMMIT
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
"$HOME/src/mlx-omarchy-resid/.work/venv-build/bin/python" -m pip wheel --no-build-isolation --no-deps --wheel-dir /var/tmp/pt/dist /var/tmp/pt/mlx
shopt -s nullglob
for w in /var/tmp/pt/dist/mlx_omarchy-*.whl; do
  echo "[receipt] wheel: $w"
  echo "[receipt] sha256: $(sha256sum "$w" | awk '{print $1}')"
done
