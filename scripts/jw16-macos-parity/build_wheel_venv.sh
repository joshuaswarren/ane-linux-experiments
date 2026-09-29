#!/bin/bash
# Build the mlx-omarchy wheel from a shipped source tree and stage a TEST venv (production venv untouched).
# usage: build_wheel_venv.sh BUILD_DIR COMMIT_TAG NEW_VENV [BASE_VENV]
set -euo pipefail
BUILD="${1:?build dir}"; TAG="${2:?commit tag}"; VENV="${3:?new venv dir}"; BASE="${4:-/var/tmp/ew-venv}"
cd "$BUILD"
DEV_RELEASE=1 MLX_OMARCHY_SOURCE_COMMIT="$TAG" MLX_OMARCHY_WHOLE_BUNDLE_DIR=/var/tmp/encoder-whole/bundle \
  bash scripts/build-wheel.sh ${DIAG:+--diagnostics} 2>&1 | tail -4
[ -d "$VENV" ] || cp -a "$BASE" "$VENV"
"$VENV/bin/python3" -m pip install --force-reinstall --no-deps -q "$BUILD"/dist/*.whl
"$VENV/bin/python3" -m pip list 2>/dev/null | grep -i mlx-omarchy
