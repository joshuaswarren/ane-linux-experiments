#!/bin/bash
# Install a tested wheel into the SERVING venv, keeping a full backup copy for rollback.
# usage: deploy_wheel.sh WHEEL [SERVING_VENV]
set -euo pipefail
WHEEL="${1:?wheel}"; VENV="${2:-/var/tmp/v072-venv-fused}"
BAK="$VENV.pre-$(date +%Y%m%dT%H%M%S)"
[ -e "$BAK" ] && { echo "backup exists: $BAK"; exit 1; }
cp -a "$VENV" "$BAK"
"$VENV/bin/python3" -m pip list 2>/dev/null | grep -i mlx-omarchy | sed 's/^/before: /'
sha256sum "$WHEEL"
"$VENV/bin/python3" -m pip install --force-reinstall --no-deps -q "$WHEEL"
"$VENV/bin/python3" -m pip list 2>/dev/null | grep -i mlx-omarchy | sed 's/^/after:  /'
echo "rollback: swap $BAK back to $VENV"
