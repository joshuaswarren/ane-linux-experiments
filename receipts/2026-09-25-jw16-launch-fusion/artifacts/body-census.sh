#!/usr/bin/env bash
set -uo pipefail
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*)"
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
VENV=${VENV:-/var/tmp/v072-venv-fused}
echo "census venv=$VENV wheel=$($VENV/bin/pip list 2>/dev/null | grep mlx-omarchy)"
"$VENV/bin/python" /var/tmp/levers2/census.py "$MODEL" "$PROMPTS" "$O/census" 4 2> "$O/census-$stamp.trace"
echo "trace lines: $(wc -l < "$O/census-$stamp.trace")"
cp "$MODEL/config.json" "$O/config.json"
