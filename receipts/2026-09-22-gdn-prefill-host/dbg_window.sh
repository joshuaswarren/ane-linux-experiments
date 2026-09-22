#!/usr/bin/env bash
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=/var/tmp/gdn-exact-probe
pkill -TERM -f "llama-vulkan/llama-server" || true
sleep 3
exec 9>/tmp/m1-gpu.lock
flock -w 600 9 || { echo "lock timeout" >&2; exit 1; }
echo "== lock held $STAMP =="
export GDN_FALLBACK_DEBUG=1
/var/tmp/gdn-exact-venv/bin/python $OUT/profile_prefill.py $OUT/prompt512.txt > $OUT/dbg-$STAMP.log 2>&1
grep -m4 "GDN-FALLBACK" $OUT/dbg-$STAMP.log
tail -1 $OUT/dbg-$STAMP.log
nohup /var/tmp/llama-restore.sh >/dev/null 2>&1 &
sleep 25
curl -s --max-time 8 localhost:8002/health || echo "SERVER NOT UP YET"
echo "WINDOW-DONE $STAMP"
