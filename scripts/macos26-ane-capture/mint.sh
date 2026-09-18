#!/usr/bin/env bash
# Mint h14g/h13 ANE oracle bundles for one geometry (t602x oracle mints).
# Usage: mint.sh GEOMETRY TARGET_ARCH WORKDIR
# Requires ./ane-compile-hwx (built from ane-compile-hwx.mm) and
# python3 (stdlib only) in the same dir as make_capture.py.
set -uo pipefail
GEOM="$1"; TARGET="$2"; WORK="$3"
cd "$WORK"
echo "=== geometry=$GEOM target=$TARGET $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 make_capture.py "$GEOM" "capture-$GEOM" || exit 2
mkdir -p "hwx-$GEOM-$TARGET"
./ane-compile-hwx "capture-$GEOM" "hwx-$GEOM-$TARGET" "$TARGET" 2>&1
STATUS=$?
echo "bridge_exit=$STATUS"
HWX="hwx-$GEOM-$TARGET/model.hwx"
if [ -f "$HWX" ]; then
  echo "hwx_bytes=$(stat -f %z "$HWX" 2>/dev/null || stat -c %s "$HWX")"
  shasum -a 256 "$HWX"
  ls -la "hwx-$GEOM-$TARGET" | sed -n '1,12p'
else
  echo "NO_HWX_EMitted"
  ls -la "hwx-$GEOM-$TARGET" 2>/dev/null | sed -n '1,12p'
fi
