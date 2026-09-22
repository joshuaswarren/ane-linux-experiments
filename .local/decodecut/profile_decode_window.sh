#!/usr/bin/env bash
# Decode dispatch/identity profile window, m1-host .
# Usage: profile_decode_window.sh <tag>
set -u
TAG=${1:?tag}
OUT=/var/tmp/decodecut
STAMP=$(date +%H%M%S)
PY=/var/tmp/decodecut-venv/bin/python
echo "== stopping resident llama-server =="
pkill -TERM -f "llama-vulkan/llama-server" || true
sleep 3
exec 9>/tmp/m1-gpu.lock
flock -w 1800 9 || { echo "lock timeout" >&2; exit 1; }
echo "== lock held $TAG $STAMP =="
export MLX_DISABLE_COMPILE=1
export MLX_OMARCHY_TRACE_DISPATCH=1
export MLX_OMARCHY_GPU_PROFILE=$OUT/prof-$TAG.jsonl
export MLX_OMARCHY_GPU_PROFILE_LABEL=$TAG
"$PY" $OUT/profile_decode.py > $OUT/run-$TAG.log 2>&1
unset MLX_OMARCHY_TRACE_DISPATCH MLX_OMARCHY_GPU_PROFILE MLX_OMARCHY_GPU_PROFILE_LABEL
grep -E "PREFILL|DECODE|TOKENS" $OUT/run-$TAG.log
echo "== restoring resident llama-server =="
nohup /var/tmp/llama-restore.sh >/dev/null 2>&1 &
sleep 20
curl -s --max-time 8 localhost:8002/health || echo "SERVER NOT UP YET"
echo "WINDOW-DONE $TAG $STAMP"
