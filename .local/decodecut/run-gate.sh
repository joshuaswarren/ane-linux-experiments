#!/usr/bin/env bash
set -u
exec 9>/tmp/m1-gpu.lock
flock -w 1800 9 || exit 1
export MLX_DISABLE_COMPILE=1
MODEL=$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)
PY=/var/tmp/decodecut-venv/bin/python
$PY /tmp/q38c/logits.py "$MODEL" /var/tmp/decodecut/logits-fix.json rawfix > /var/tmp/decodecut/logits-fix.log 2>&1
echo "== gate =="
$PY /var/tmp/decodecut/compare_logits.py /var/tmp/decodecut/logits-fix.json /tmp/q38c/logits-integ-m1-host.json 2>&1 | grep -v rtmod
