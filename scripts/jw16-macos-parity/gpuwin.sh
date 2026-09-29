#!/bin/bash
# Run ONE command inside the llm-inference discipline: stop, verify inactive + lock free, flock, restore via
# trap, verify health 200 AND a real completion probe (finish_reason). usage: gpuwin.sh 'command string'
set -u
CMD="${1:?command}"
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
flock -w 900 /tmp/m1-gpu.lock bash -c "$CMD"
