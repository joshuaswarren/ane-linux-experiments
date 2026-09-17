#!/bin/bash
# run-mapmode-window-jwm1.sh — the whole jwm1 map_mode qualification inside
# one device window: byte-identity matrix, then pin-gated E2E A/B
# (orig 96d5a88 vs variant 82a18af @ map_mode=3). Trap restores the original
# module even on failure and verifies the version stamp. No service owns the
# lock on jwm1; flock -w 900, never stolen, never unlinked.
set -uo pipefail
LOG=/var/tmp/ane-submit-probe/mapmode-window.log
P=/var/tmp/ane-submit-probe
ORIG_KO=/home/joshuawarren/src/omarchy-ane-lifecycle-rebase/ane/ane.ko
VARIANT_KO=$P/ane-82a18af.ko
exec >> "$LOG" 2>&1
echo "==== map_mode window start $(date -Is) lock=$(stat -c 'inode %i' /tmp/m1-gpu.lock)"

restore() {
  echo "== restore begin $(date -Is)"
  if [ -e /sys/module/ane/parameters/map_mode ]; then
    echo 0 | sudo -n tee /sys/module/ane/parameters/map_mode >/dev/null 2>&1 || true
    sudo -n rmmod ane 2>&1 || true
    sudo -n insmod "$ORIG_KO" 2>&1 || true
    sleep 1
  fi
  echo "module: /sys/module/ane/version=$(cat /sys/module/ane/version 2>/dev/null) refcnt=$(grep '^ane ' /proc/modules)"
  echo "map_mode present: $([ -e /sys/module/ane/parameters/map_mode ] && echo yes || echo no)"
  echo "== restore end"
}
trap restore EXIT

echo "preflight: refcnt=$(grep '^ane ' /proc/modules) version=$(cat /sys/module/ane/version 2>/dev/null)"
[ "$(cat /sys/module/ane/version 2>/dev/null)" = "96d5a88" ] || { echo "unexpected starting module"; exit 41; }

echo "== phase A: byte-identity matrix"
flock -w 900 /tmp/m1-gpu.lock $P/run-cachedread-matrix-jwm1.sh
echo "== matrix exit: $?"

echo "== phase B: pin-gated E2E A/B"
echo "-- B1: pins-orig on original module"
flock -w 900 /tmp/m1-gpu.lock $P/run-pins-e2e-jwm1.sh pins-orig

echo "-- B2: swap variant, map_mode=3"
sudo -n rmmod ane
sudo -n insmod "$VARIANT_KO"
echo 3 | sudo -n tee /sys/module/ane/parameters/map_mode >/dev/null
echo "map_mode=$(cat /sys/module/ane/parameters/map_mode) version=$(cat /sys/module/ane/version 2>/dev/null)"

flock -w 900 /tmp/m1-gpu.lock $P/run-pins-e2e-jwm1.sh pins-mode3
echo "==== map_mode phases complete $(date -Is)"
