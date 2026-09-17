#!/bin/bash
# v0.6.3 both-host verification (jw16 / M1 Max). Stops llm-inference.service
# to release /tmp/m1-gpu.lock (ExecStart flock --nonblock exec), runs the
# clean-install parakeet gate and the pinned ctx1024 decode leg, ALWAYS
# restarts the service and confirms active. Never steals the lock.
set -u
ROOT=/var/tmp/v063-jw16
WHEEL=$(ls "$ROOT"/*.whl)
GATE=$ROOT/receipts/2026-09-16-parakeet-wheel-packaging/gate-jwm1.sh
STATUS=/var/tmp/v063-jw16.status
: > "$STATUS"
echo "module=$(cat /sys/module/ane/version) map_mode=$(cat /sys/module/ane/parameters/map_mode)" >> "$STATUS"

restore_service() { sudo -n systemctl start llm-inference.service; }
trap restore_service EXIT

sudo -n systemctl stop llm-inference.service
echo "service=$(systemctl is-active llm-inference.service) $(date -Iseconds)" >> "$STATUS"
locked=1
for i in $(seq 1 10); do
  if flock -n /tmp/m1-gpu.lock true; then locked=0; break; fi
  sleep 1
done
if (( locked )); then
  echo "FATAL: lock still held after service stop" >> "$STATUS"
  exit 9
fi
echo "lock-free $(date -Iseconds)" >> "$STATUS"

bash "$GATE" "$WHEEL" /var/tmp/v063-jw16-gate > /var/tmp/v063-jw16-gate.driver.log 2>&1
echo "gate-exit=$? $(date -Iseconds)" >> "$STATUS"

if [[ ! -x /var/tmp/V063PIN-venv/bin/python ]]; then
  python3 -m venv /var/tmp/V063PIN-venv
  /var/tmp/V063PIN-venv/bin/pip install --quiet mlx-lm==0.31.3
  /var/tmp/V063PIN-venv/bin/pip install --quiet --no-deps --force-reinstall "$WHEEL"
fi
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
if flock -n /tmp/m1-gpu.lock true; then
  echo "final-lock-FREE-UNEXPECTED $(date -Iseconds)" >> "$STATUS"
else
  echo "final-lock-held-service-rearmed $(date -Iseconds)" >> "$STATUS"
fi
echo "jw16 done $(date -Iseconds)" >> "$STATUS"
