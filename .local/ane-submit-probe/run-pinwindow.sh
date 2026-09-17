#!/bin/bash
# run-pinwindow.sh — pin-gated A/B of the A0 cached-read on the certified
# green configuration (WheelR4V062's invocation, PLACED=ABC, resident-batch).
# Caller has stopped llm-inference. Trap restores module + service.
set -uo pipefail
LOG=/var/tmp/ane-submit-probe/pinwindow.log
exec >> "$LOG" 2>&1
echo "==== pin window start $(date -Is)"

restore() {
  echo "== restore begin"
  if [ -e /sys/module/ane/parameters/map_mode ]; then
    echo 0 | sudo -n tee /sys/module/ane/parameters/map_mode >/dev/null 2>&1
    sudo -n rmmod ane 2>&1 || true
    sudo -n insmod /usr/local/lib/omarchy-ane/ane.ko 2>&1 || true
    sleep 1
  fi
  echo "module: /sys/module/ane/version=$(cat /sys/module/ane/version 2>/dev/null)"
  sudo -n systemctl start llm-inference.service || true
  sleep 2
  echo "service: $(systemctl is-active llm-inference.service) lock: $(ls -i /tmp/m1-gpu.lock)"
  echo "== restore end"
}
trap restore EXIT

PINRUN=/var/tmp/ane-submit-probe/run-pins-e2e.sh

echo "== pin run on ORIGINAL module"
flock -w 900 /tmp/m1-gpu.lock $PINRUN pins-orig
[ "$(cat /sys/module/ane/version 2>/dev/null)" = "96d5a88" ] || { echo "module state unexpected"; }

echo "== swap variant, map_mode=3"
sudo -n rmmod ane
sudo -n insmod /home/joshuawarren/src/ane-cachedread-wt/ane/ane.ko
echo 3 | sudo -n tee /sys/module/ane/parameters/map_mode >/dev/null
echo "map_mode=$(cat /sys/module/ane/parameters/map_mode)"

echo "== pin run on variant mode3"
flock -w 900 /tmp/m1-gpu.lock $PINRUN pins-mode3
echo "==== pin phases complete $(date -Is)"
