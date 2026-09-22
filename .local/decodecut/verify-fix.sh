#!/usr/bin/env bash
# Post-build: install fixed wheel, rerun probes + logits gate on m1-host.
set -eu
WHEEL=$(ls -t /var/tmp/integ-wt/dist/mlx_omarchy-*diag*.whl | head -1)
PY=/var/tmp/decodecut-venv/bin/python
echo "installing $WHEEL"
"$PY" -m pip install --force-reinstall --no-deps -q "$WHEEL"
exec 9>/tmp/m1-gpu.lock
flock -w 1800 9
echo "== ref_check =="
"$PY" /var/tmp/decodecut/ref_check.py 2>&1 | grep -v rtmod
echo "== gate_probe =="
"$PY" /var/tmp/decodecut/gate_probe.py 2>&1 | grep -v rtmod
echo "== logits gate =="
export MLX_DISABLE_COMPILE=1
"$PY" /tmp/q38c/logits.py --out /var/tmp/decodecut/logits-fix.json > /var/tmp/decodecut/logits-fix.log 2>&1 || echo "LOGITS DRIVER FAILED"
"$PY" /var/tmp/decodecut/compare_logits.py /var/tmp/decodecut/logits-fix.json /tmp/q38c/logits-integ-m1-host.json 2>&1 | grep -v rtmod
