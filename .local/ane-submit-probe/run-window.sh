#!/bin/bash
# run-window.sh — full A0 cached-read device window on jw16.
# Caller has already stopped llm-inference. Everything below runs under
# per-phase `flock /tmp/m1-gpu.lock`; restore is trap-protected (runs on any
# exit path) per the hand-back contract: original module stamp, service
# active, lock inode reported.
set -uo pipefail
P=/var/tmp/ane-submit-probe
LOG=$P/window.log
exec >> "$LOG" 2>&1
echo "==== window start $(date -Is) lock_inode=$(ls -i /tmp/m1-gpu.lock | awk '{print $1}')"

restore() {
  echo "== restore begin $(date -Is)"
  if [ -e /sys/module/ane/parameters/map_mode ]; then
    echo 0 | sudo -n tee /sys/module/ane/parameters/map_mode >/dev/null 2>&1
    sudo -n rmmod ane 2>&1 || true
    sudo -n insmod /usr/local/lib/omarchy-ane/ane.ko 2>&1 || true
    sleep 1
  fi
  echo "module: /sys/module/ane/version=$(cat /sys/module/ane/version 2>/dev/null) proc:$(grep '^ane ' /proc/modules)"
  sudo -n systemctl start llm-inference.service || true
  sleep 2
  echo "service: $(systemctl is-active llm-inference.service)"
  echo "lock: $(ls -i /tmp/m1-gpu.lock)"
  fuser -v /tmp/m1-gpu.lock 2>&1 || true
  echo "== restore end"
}
trap restore EXIT

# Phase A: e2e BEFORE on the original module (resident-batch + launch)
flock -w 900 /tmp/m1-gpu.lock $P/run-roundtrip-e2e.sh base-resident resident-batch
echo "---- phase A1 done $(date -Is)"
flock -w 900 /tmp/m1-gpu.lock $P/run-roundtrip-e2e.sh base-launch launch
echo "---- phase A2 done $(date -Is)"

# Phase B: mapping-mode matrix; HOLD=1 leaves variant loaded at map_mode=3
HOLD=1 flock -w 900 /tmp/m1-gpu.lock $P/run-cachedread-matrix.sh
echo "---- phase B done $(date -Is) map_mode=$(cat /sys/module/ane/parameters/map_mode 2>/dev/null)"

# Phase C: e2e AFTER on the variant at map_mode=3
flock -w 900 /tmp/m1-gpu.lock $P/run-roundtrip-e2e.sh cached-resident resident-batch
echo "---- phase C1 done $(date -Is)"
flock -w 900 /tmp/m1-gpu.lock $P/run-roundtrip-e2e.sh cached-launch launch
echo "---- phase C2 done $(date -Is)"

echo "==== phases complete $(date -Is) (trap restores module + service)"
