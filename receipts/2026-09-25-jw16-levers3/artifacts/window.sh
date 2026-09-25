#!/usr/bin/env bash
# Jw16Levers3 GPU window: stop llm-inference, hold /tmp/m1-gpu.lock, run the
# body script, then restore the service and verify a real completion.
# usage: window.sh <name> <body.sh> [args...]
set -uo pipefail
D=/var/tmp/levers3
NAME=$1; BODY=$2; shift 2
O=$D/$NAME; mkdir -p "$O"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
L=$O/window-$stamp.log
log(){ printf "[%s] %s\n" "$(date -Is)" "$*" | tee -a "$L" >&2; }
cleanup(){
  rc=$?
  log "cleanup rc=$rc -- release flock + restart service"
  flock -u 9 2>/dev/null || true
  sudo systemctl start llm-inference.service >/dev/null 2>&1 || true
  healthy=0
  for i in $(seq 1 30); do
    sleep 5
    body=$(curl -sS --max-time 2 http://127.0.0.1:8002/health 2>/dev/null || true)
    if printf "%s" "$body" | grep -q '"status":"ok"'; then log "poll #$i: 8002 ok"; healthy=1; break; fi
  done
  if [ "$healthy" = 1 ]; then
    kkey=$(sudo cat /etc/llm-inference/api-key 2>/dev/null | tr -d '\n' || true)
    comp=$(curl -sS --max-time 90 http://127.0.0.1:8002/v1/chat/completions \
      -H 'Content-Type: application/json' -H "Authorization: Bearer $kkey" \
      -d '{"model":"qwen3.8-27b","messages":[{"role":"user","content":"Say OK."}],"max_tokens":8,"temperature":0}' 2>/dev/null || true)
    log "completion probe: ${comp:-<empty>}"
    printf "%s\n" "$comp" > "$O/completion-$stamp.json"
  fi
  log "service healthy=$healthy"
  exit $rc
}
trap cleanup EXIT INT TERM
log "window $NAME begin stamp=$stamp body=$BODY args=$*"
sudo systemctl stop llm-inference.service
exec 9>/tmp/m1-gpu.lock
flock 9
log "flock held by $$"
log "icd: $(tr -d ' \n' < /usr/share/vulkan/icd.d/asahi_icd.aarch64.json)"
export O L stamp
bash "$BODY" "$@" 2>&1 | tee -a "$L" >&2
log "WINDOW_BODY_DONE rc=${PIPESTATUS[0]}"
