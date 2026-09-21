#!/bin/bash
# restore-pinned-and-verify.sh — restore the pinned venv to the 5b18306 wheel,
# verify (dist tag + libmlx + core binding + on-disk driver map), record the
# mapped driver state. Main-directed, fires only on EncoderFloor RELEASE.
set -uo pipefail

VENV=/var/tmp/jwm1-v072rc1/venv
SP=$VENV/lib/python3.14/site-packages
OLDWHL=/var/tmp/jwm1-v072rc1/mlx_omarchy-0.32.3.dev202609201440+5b18306-cp314-cp314-linux_aarch64.whl
E167=/tmp/mesa-sin-ftz-jwm1/drivers/libvulkan_asahi-e167.so
STOCK=/usr/lib/libvulkan_asahi.so
OUT=/var/tmp/jwm1-ane-step2/restore-verification.log

{
  echo "=== restore-pinned-and-verify $(date -Ins) $(hostname) ==="
  echo "--- step 1: pip install (entire old wheel, no rm) ---"
  $VENV/bin/pip install --force-reinstall --no-deps "$OLDWHL" 2>&1 | tail -2
  echo "--- step 2: pinned state ---"
  $VENV/bin/python -c "import importlib.metadata as M; print('dist:', M.version('mlx-omarchy'))"
  echo "libmlx.so  : $(sha256sum $SP/mlx/lib/libmlx.so | cut -c1-16)  expected c28a485f98b55aad"
  echo "core cpython: $(sha256sum $SP/mlx/core.cpython-314-aarch64-linux-gnu.so | cut -c1-16)"
  echo "--- step 3: on-disk driver inventory ---"
  echo "e167 sha  : $(sha256sum $E167  | cut -c1-16)  (BuildID ac55e1bc)"
  echo "stock sha : $(sha256sum $STOCK | cut -c1-16)  (BuildID 048ae888)  cataloged SEGV on mlx-omarchy custom kernels"
  echo "--- step 4: live process driver map (no python expected at idle) ---"
  hits=$(ps -eo pid,comm | awk '$2~/python/{print $1}' | while read p; do grep -oE '/[A-Za-z0-9_./-]*libvulkan_asahi[^ ]*' /proc/$p/maps 2>/dev/null; done | sort -u)
  if [ -z "$hits" ]; then echo "no live python process mapping libvulkan_asahi (lane idle)"; else echo "$hits"; fi
  echo "--- step 5: import smoke ---"
  $VENV/bin/python -c "import mlx.core, mlx.omarchy; print('mlx import OK')"
  echo "--- step 6: pass condition ---"
  d=$($VENV/bin/python -c "import importlib.metadata as M; print(M.version('mlx-omarchy'))")
  l=$(sha256sum $SP/mlx/lib/libmlx.so | cut -c1-16)
  if [[ "$d" == *5b18306* ]] && [[ "$l" == c28a485f* ]]; then echo PASS; else echo FAIL; fi
} > "$OUT" 2>&1

cat "$OUT"
