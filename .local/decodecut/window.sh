#!/usr/bin/env bash
# Decode A/B window, m1-host : cadence identity/tok-per-s + dispatch profile.
# Usage: window.sh <tag>
set -u
TAG=${1:?tag}
OUT=/var/tmp/decodecut
STAMP=$(date +%H%M%S)
PY=/var/tmp/decodecut-venv/bin/python
MODEL=$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)
BENCH=/tmp/q38c/qwen38-mlx-bench.py
PROMPTS=/tmp/q38c/qwen38-2b-prompts.jsonl
echo "== stopping resident llama-server =="
pkill -TERM -f "llama-vulkan/llama-server" || true
sleep 3
exec 9>/tmp/m1-gpu.lock
flock -w 1800 9 || { echo "lock timeout" >&2; exit 1; }
echo "== lock held $TAG $STAMP =="
export MLX_DISABLE_COMPILE=1

"$PY" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" --limit 10 \
  --warmup 1 --passes 1 --prefill-tokens 512 \
  --label "$TAG-$STAMP" \
  --out "$OUT/cadence-$TAG.json" > "$OUT/cadence-$TAG.log" 2>&1 \
  || echo "CADENCE BENCH FAILED" >&2
grep -iE "digest|decode|prefill" "$OUT/cadence-$TAG.log" | tail -6

export MLX_OMARCHY_TRACE_DISPATCH=1
export MLX_OMARCHY_GPU_PROFILE=$OUT/prof-$TAG.jsonl
export MLX_OMARCHY_GPU_PROFILE_LABEL=$TAG
"$PY" /var/tmp/integ-wt/scripts/profile_generate.py --model "$MODEL" \
  --prompt "France France France France France France France France France France France France France France France France" \
  --max-tokens 32 --temp 0 --seed 0 --markers "$OUT/markers-$TAG.jsonl" \
  > "$OUT/gen-$TAG.log" 2>&1
unset MLX_OMARCHY_TRACE_DISPATCH MLX_OMARCHY_GPU_PROFILE MLX_OMARCHY_GPU_PROFILE_LABEL
"$PY" /var/tmp/integ-wt/scripts/profile_analyze.py "$OUT/prof-$TAG.jsonl" \
  --markers "$OUT/markers-$TAG.jsonl" \
  --compute-h /var/tmp/integ-wt/overlay/mlx/backend/omarchy/compute.h \
  > "$OUT/analyze-$TAG.txt" 2>&1 || echo "ANALYZE FAILED" >&2
grep -A40 "decode" "$OUT/analyze-$TAG.txt" | head -60

echo "== restoring resident llama-server =="
nohup /var/tmp/llama-restore.sh >/dev/null 2>&1 &
sleep 25
curl -s --max-time 8 localhost:8002/health || echo "SERVER NOT UP YET"
echo "WINDOW-DONE $TAG $STAMP"
