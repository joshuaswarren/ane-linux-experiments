#!/bin/bash
# Run ONE command inside the llm-inference discipline: stop, verify inactive + lock free, flock, restore via
# trap, verify health 200 AND a real completion probe (finish_reason). usage: gpuwin.sh 'command string'
set -u
CMD="${1:?command}"
# Serialize windows: the service holds /tmp/m1-gpu.lock itself, so we must stop it before flocking that lock.
# Take this outer mutex FIRST so a contending window cannot stop/restart the service under a running one.
exec 9>/tmp/gpuwin.mutex; flock -w 7200 9 || { echo "gpuwin mutex timeout"; exit 1; }
# Maintenance gate: while /var/tmp/JW16_MAINTENANCE exists (kernel work / reboot), no GPU window may start.
while [ -e /var/tmp/JW16_MAINTENANCE ]; do echo "maintenance: $(cat /var/tmp/JW16_MAINTENANCE 2>/dev/null | head -1) - waiting"; sleep 30; done
restore () {
  sudo systemctl start llm-inference.service
  local ok="" key rc
  for _ in $(seq 1 60); do
    if curl -sf -m 3 http://127.0.0.1:8002/health >/dev/null 2>&1; then ok=1; break; fi
    sleep 3
  done
  key=$(sudo cat /etc/llm-inference/api-key)
  rc=$(curl -sS -m 90 http://127.0.0.1:8002/v1/chat/completions -H "Authorization: Bearer $key" \
    -H 'Content-Type: application/json' \
    -d '{"model":"default","messages":[{"role":"user","content":"Say Pacific"}],"max_tokens":8}' \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['finish_reason'])" 2>/dev/null)
  echo "RESTORE health_ok=${ok:-0} probe_finish=${rc:-FAILED} active=$(systemctl is-active llm-inference.service)"
}
trap restore EXIT
sudo systemctl stop llm-inference.service; sleep 2
echo "STOP svc=$(systemctl is-active llm-inference.service) lock_holders=[$(fuser /tmp/m1-gpu.lock 2>&1 || true)]"
GPUWIN_HELD=1 flock -w 900 /tmp/m1-gpu.lock bash -c "$CMD"
