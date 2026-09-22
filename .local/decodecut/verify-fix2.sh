#!/usr/bin/env bash
set -eu
WHEEL=$(ls -t /var/tmp/integ-wt/dist/mlx_omarchy-*diag*.whl | head -1)
PY=/var/tmp/decodecut-venv/bin/python
echo "installing $WHEEL"
"$PY" -m pip install --force-reinstall --no-deps -q "$WHEEL"
exec 9>/tmp/m1-gpu.lock
flock -w 1800 9
echo "== in-model fallback check (want fallback lines: 0) =="
bash /var/tmp/decodecut/run-spy2.sh || true
echo "== degenerate g probes (dt now bf16 in probes? skip) =="
echo "== logits gate =="
export MLX_DISABLE_COMPILE=1
MODEL=$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)
"$PY" /tmp/q38c/logits.py "$MODEL" /var/tmp/decodecut/logits-fix2.json rawfix2 > /var/tmp/decodecut/logits-fix2.log 2>&1
"$PY" /var/tmp/decodecut/compare_logits.py /var/tmp/decodecut/logits-fix2.json /tmp/q38c/logits-integ-m1-host.json 2>&1 | grep -v rtmod | head -8
"$PY" /var/tmp/decodecut/gate_class.py 2>/dev/null | tail -3
