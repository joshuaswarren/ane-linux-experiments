#!/usr/bin/env bash
# gpu-host GDN-exact measurement window: stops the resident llama-server,
# holds /tmp/m1-gpu.lock, runs the leg probe + prefill-512 model bench
# on the gdn-exact candidate wheel, restores the server after.
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=/var/tmp/gdn-exact-probe
MODEL=$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)
BENCH=~/bench-scripts/qwen38-mlx-bench.py
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
VENV=/var/tmp/gdn-exact-venv/bin/python

echo "== stopping resident llama-server (8002) =="
pkill -TERM -f "flock --nonblock /tmp/m1-gpu.lock ~/opt/llama-vulkan/llama-server" || true
pkill -TERM -f "llama-vulkan/llama-server" || true
sleep 3

exec 9>/tmp/m1-gpu.lock
flock -w 600 9 || { echo "lock timeout" >&2; exit 1; }
echo "== lock held $STAMP =="

echo "== leg probe =="
"$VENV" "$OUT/leg_probe.py" > "$OUT/leg-$STAMP.log" 2>&1 \
  || echo "LEG PROBE FAILED" >&2
tail -5 "$OUT/leg-$STAMP.log"

echo "== model bench (candidate gdn-exact) =="
"$VENV" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" --limit 10 \
  --warmup 2 --passes 3 --prefill-tokens 512 \
  --label "gpu-host-gdn-exact-$(git -C /var/tmp/gdn-exact-wt rev-parse --short=7 HEAD 2>/dev/null || echo unknown)-$STAMP" \
  --out "$OUT/candidate.json" > "$OUT/candidate-$STAMP.log" 2>&1 \
  || echo "MODEL BENCH FAILED" >&2
grep -i "digest\|tok/s\|prefill" "$OUT/candidate-$STAMP.log" | tail -8

echo "== restoring resident llama-server =="
nohup /var/tmp/llama-restore.sh >/dev/null 2>&1 &
sleep 25
curl -s --max-time 8 localhost:8002/health || echo "SERVER NOT UP YET"
echo "WINDOW-DONE $STAMP"
