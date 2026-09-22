#!/usr/bin/env bash
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=/var/tmp/gdn-exact-probe
echo "== stopping resident llama-server (8002) =="
pkill -TERM -f "llama-vulkan/llama-server" || true
sleep 3
exec 9>/tmp/m1-gpu.lock
flock -w 600 9 || { echo "lock timeout" >&2; exit 1; }
echo "== lock held $STAMP =="
export MLX_OMARCHY_TRACE_DISPATCH=1
export MLX_OMARCHY_GPU_PROFILE=$OUT/prof-$STAMP.json
export MLX_OMARCHY_GPU_PROFILE_LABEL=${1:-prefill512}
/var/tmp/gdn-exact-venv/bin/python $OUT/profile_prefill.py $OUT/prompt512.txt > $OUT/prof-run-$STAMP.log 2>&1
tail -2 $OUT/prof-run-$STAMP.log
unset MLX_OMARCHY_TRACE_DISPATCH MLX_OMARCHY_GPU_PROFILE
echo "== restoring resident llama-server =="
nohup /var/tmp/llama-restore.sh >/dev/null 2>&1 &
sleep 25
curl -s --max-time 8 localhost:8002/health || echo "SERVER NOT UP YET"
echo "WINDOW-DONE $STAMP"
