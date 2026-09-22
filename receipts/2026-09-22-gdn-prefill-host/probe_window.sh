#!/usr/bin/env bash
set -u
pkill -TERM -f "llama-vulkan/llama-server" || true
sleep 3
exec 9>/tmp/m1-gpu.lock
flock -w 600 9 || { echo "lock timeout" >&2; exit 1; }
/var/tmp/gdn-exact-venv/bin/python /var/tmp/gdn-exact-probe/nc_probe.py 2>&1 | tail -10
nohup /var/tmp/llama-restore.sh >/dev/null 2>&1 &
sleep 25
curl -s --max-time 8 localhost:8002/health || echo "SERVER NOT UP YET"
echo PROBE-WINDOW-DONE
