#!/usr/bin/env bash
# Install the SDPA-port wheel into v072-venv-fused, with btrfs-ENOSPC
# fallback (manual libmlx.so copy) following the proven t6001 sdpa
# receipt's repair procedure (receipts/2026-09-24-t6001-sdpa-decode-hd256
# §4).
#
# Usage: install_sdpa_wheel.sh <WHL>
# Rolls back to the original venv on failure.
set -euo pipefail
WHL="${1:?wheel path}"
TARGET=/var/tmp/v072-venv-fused
LIBMLX_SRC="${TARGET}/lib/python3.14/site-packages/mlx/lib/libmlx.so"
SHA_BEFORE=$(sha256sum "$LIBMLX_SRC" | cut -c1-16)
echo "installed libmlx.so sha before: $SHA_BEFORE"

# Snapshot for rollback
ROLLBACK=/var/tmp/v072-venv-fused.rollback
if [ ! -d "$ROLLBACK" ]; then
  mkdir -p "$ROLLBACK"
  cp "$LIBMLX_SRC" "$ROLLBACK/libmlx.so.before"
  cp "${TARGET}/lib/python3.14/site-packages/mlx_omarchy"*.dist-info/METADATA \
     "$ROLLBACK/METADATA.before" 2>/dev/null || true
fi

# Attempt pip install
if ! "${TARGET}/bin/pip" install --force-reinstall --no-deps "$WHL" 2>&1 | tee /tmp/pip-install.log; then
  echo "pip install failed; attempting manual libmlx.so copy (btrfs ENOSPC workaround)"
  TMPD=$(mktemp -d /dev/shm/mlx-extract-XXXXX)
  unzip -q -o "$WHL" -d "$TMPD"
  cp "$TMPD/mlx/lib/libmlx.so" "$LIBMLX_SRC"
  # update dist-info to match
  WHEEL_DIST=$(ls -d "$TMPD"/mlx_omarchy*.dist-info)
  SITE_DIST="${TARGET}/lib/python3.14/site-packages/$(basename $WHEEL_DIST)"
  rm -rf "$SITE_DIST"
  cp -r "$WHEEL_DIST" "${TARGET}/lib/python3.14/site-packages/"
  rm -rf "$TMPD"
fi

# Verify
SHA_AFTER=$(sha256sum "$LIBMLX_SRC" | cut -c1-16)
echo "installed libmlx.so sha after:  $SHA_AFTER"
WHEEL_SHA=$(unzip -p "$WHL" mlx/lib/libmlx.so | sha256sum | cut -c1-16)
echo "wheel libmlx.so sha:            $WHEEL_SHA"
if [ "$SHA_AFTER" != "$WHEEL_SHA" ]; then
  echo "SHA MISMATCH — rolling back"
  cp "$ROLLBACK/libmlx.so.before" "$LIBMLX_SRC"
  exit 1
fi
echo "install verified: libmlx.so on disk matches wheel"
