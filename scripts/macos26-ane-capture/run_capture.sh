#!/usr/bin/env bash
# Local driver: stage the kit on the Mac, run capture.sh, fetch artifacts.
# Usage: bash run_capture.sh [HOST] [OUT_DIR]
#   HOST defaults to t6021-test-host (BatchMode only — never interactive).
#   OUT_DIR defaults to receipts/2026-09-18-t6021-test-host-macos26-capture/
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$KIT/../.." && pwd)"
HOST="${1:-t6021-test-host}"
OUT="${2:-$REPO/receipts/2026-09-18-t6021-test-host-macos26-capture}"

ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" \
  'rm -rf /tmp/t6021-test-host-macos26-capture && mkdir -p /tmp/t6021-test-host-macos26-capture'
scp -q -o BatchMode=yes "$KIT"/ane_probe.py "$KIT"/mint_probe.sh \
    "$KIT"/capture.sh "$KIT"/ane-compile-hwx.mm "$KIT"/make_capture.py \
    "$KIT"/mint_aneforge.py "$KIT"/mint.sh "$HOST:/tmp/t6021-test-host-macos26-capture/"
ssh -o BatchMode=yes "$HOST" 'bash /tmp/t6021-test-host-macos26-capture/capture.sh'
scp -q -o BatchMode=yes "$HOST:/tmp/t6021-test-host-macos26-capture.tar.gz" /tmp/
mkdir -p "$OUT"
tar -xzf /tmp/t6021-test-host-macos26-capture.tar.gz -C "$OUT"
mv "$OUT/artifacts"/* "$OUT"/ && rmdir "$OUT/artifacts"
rm -f /tmp/t6021-test-host-macos26-capture.tar.gz
echo "ARTIFACTS_IN $OUT"
