#!/bin/bash
# ParakeetTransport: deploy the pt wheel into a fresh tree and pin libmlx.
set -euo pipefail
WHEEL=$(ls /var/tmp/pt/dist/mlx_omarchy-*.whl | tail -1)
rm -rf /var/tmp/pt-wheelx
mkdir -p /var/tmp/pt-wheelx
cd /var/tmp/pt-wheelx
python3 -m zipfile -e "$WHEEL" .
ls mlx/bin/ | head -4
ls mlx/lib/ | head -4
mkdir -p /var/tmp/jwm1-pt
sha256sum mlx/lib/libmlx.so | awk '{print $1}' > /var/tmp/jwm1-pt/expected-libmlx.sha256
echo "libmlx sha: $(cat /var/tmp/jwm1-pt/expected-libmlx.sha256)"
echo "worker smoke:"
/var/tmp/pt-wheelx/mlx/bin/mlx-omarchy-ane-worker 2>&1 | head -2 || true
