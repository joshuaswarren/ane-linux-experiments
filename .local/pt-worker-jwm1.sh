#!/bin/bash
# ParakeetTransport: compile the tools --serve worker exe against the pt
# libmlx. The wheel build registers the backend runtime worker under the
# same target name first, so the serve CLI needs a direct compile here.
set -euo pipefail
TREE=/var/tmp/pt/mlx
OUT=/var/tmp/pt-wheelx/mlx/bin/mlx-omarchy-ane-worker
ANE=/var/tmp/omarchy-ane-6fa243a
g++ -O2 -std=c++17 -fPIC \
  -DMLX_OMARCHY_ANE_DEVICE=1 \
  -I"$TREE" -I"$ANE/libane" \
  "$TREE/tools/mlx-omarchy-ane-worker/main.cpp" \
  "$TREE/mlx/backend/omarchy/ane/worker_libane.cpp" \
  -L/var/tmp/pt-wheelx/mlx/lib -lmlx -ldl \
  -Wl,-rpath,'$ORIGIN/../lib' \
  -o "$OUT"
chmod +x "$OUT"
echo "worker built: $(sha256sum "$OUT" | awk '{print $1}')"
"$OUT" 2>&1 | head -3 || true
