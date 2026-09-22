#!/usr/bin/env bash
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=/var/tmp/gdn-hostfix-m1-host
mkdir -p $OUT
MODEL=$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)
BENCH=~/bench-scripts/qwen38-mlx-bench.py
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
VENV=/var/tmp/bf16-prefill-venv/bin/python
exec 9>/tmp/m1-gpu.lock
flock -w 600 9 || { echo "lock timeout" >&2; exit 1; }
echo "== lock held $STAMP =="
"$VENV" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" --limit 10 \
  --warmup 2 --passes 3 --prefill-tokens 512 \
  --label "m1-host-gdn-hostfix-$(git -C /var/tmp/bf16-prefill-wt rev-parse --short=7 HEAD 2>/dev/null || echo wheel117133d0)-$STAMP" \
  --out "$OUT/candidate-hostfix.json" > "$OUT/candidate-hostfix-$STAMP.log" 2>&1 \
  || echo "MODEL BENCH FAILED" >&2
grep -i "digest\|sha256\|prefill" "$OUT/candidate-hostfix-$STAMP.log" | tail -5
echo "WINDOW-DONE $STAMP"
