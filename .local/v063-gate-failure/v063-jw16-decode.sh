#!/bin/bash
# v0.6.3 jw16 pinned decode leg, retry after shipping the repo-local helper
# modules (caps_sim_guard, mlx_provenance). Same service stop/start
# discipline; never steals the lock; ALWAYS restarts the service.
set -u
ROOT=/var/tmp/v063-jw16
WHEEL=$(ls "$ROOT"/*.whl)
STATUS=/var/tmp/v063-jw16.status
restore_service() { sudo -n systemctl start llm-inference.service; }
trap restore_service EXIT

sudo -n systemctl stop llm-inference.service
locked=1
for i in $(seq 1 10); do
  if flock -n /tmp/m1-gpu.lock true; then locked=0; break; fi
  sleep 1
done
if (( locked )); then
  echo "FATAL: lock still held $(date -Iseconds)" >> "$STATUS"
  exit 9
fi
echo "decode-retry lock-free $(date -Iseconds)" >> "$STATUS"

cd "$ROOT"
flock -w 900 /tmp/m1-gpu.lock env HF_HUB_OFFLINE=1 MLX_DISABLE_COMPILE=1 \
  /var/tmp/V063PIN-venv/bin/python scripts/bench_matrix.py \
  --mode run --select longctx-1024-decode-32 \
  > /var/tmp/v063-jw16-decode.json 2>/var/tmp/v063-jw16-decode.log
echo "decode-exit=$? $(date -Iseconds)" >> "$STATUS"

restore_service
trap - EXIT
sleep 2
echo "service=$(systemctl is-active llm-inference.service) final $(date -Iseconds)" >> "$STATUS"
flock -n /tmp/m1-gpu.lock true && echo "final-lock-FREE-UNEXPECTED" >> "$STATUS" \
  || echo "final-lock-held-service-rearmed $(date -Iseconds)" >> "$STATUS"
