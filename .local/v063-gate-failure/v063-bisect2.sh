#!/bin/bash
# v0.6.3 gate-failure bisect driver v2 (jwm1).
#   Arm A: map_mode=3 clean re-run  — gate must PASS end to end.
#   Arm B: map_mode=0               — single-variable A/B, pins must be identical.
# Run under a persistent supervisor (hub), NOT a dying ssh parent: the
# map_mode write needs sudo -n and v1 lost it. Restores map_mode=3.
set -u
WHEEL=/var/tmp/v062-wt/dist/mlx_omarchy-0.32.2.dev202609171159+1ed1dab-cp314-cp314-linux_aarch64.whl
GATE=/var/tmp/v062-wt/receipts/2026-09-16-parakeet-wheel-packaging/gate-jwm1.sh
MM=/sys/module/ane/parameters/map_mode
STATUS=/var/tmp/v063-bisect2.status
: > "$STATUS"

mode_set() {  # mode_set <value> — write + readback assert
  echo "$1" | sudo -n tee "$MM" >/dev/null
  local got; got=$(cat "$MM")
  if [[ "$got" != "$1" ]]; then
    echo "FATAL: map_mode write failed (wanted $1 got $got) $(date -Iseconds)" >> "$STATUS"
    exit 9
  fi
}

# /tmp is a 7.6G tmpfs; the gate mktemps ~2G there. Guard + clean only
# gate-owned scratch (we are the sole gate runner; GPU lock is unheld).
avail=$(df --output=avail -BG /tmp | tail -1 | tr -dc 0-9)
echo "tmp avail ${avail}G before cleanup $(date -Iseconds)" >> "$STATUS"
if pgrep -f "mlx-omarchy-parakeet|gate-jwm1" >/dev/null; then
  echo "FATAL: a gate process is live; not cleaning scratch" >> "$STATUS"
  exit 9
fi
rm -rf /tmp/parakeet-gate.*
avail=$(df --output=avail -BG /tmp | tail -1 | tr -dc 0-9)
echo "tmp avail ${avail}G after cleanup $(date -Iseconds)" >> "$STATUS"
if (( avail < 3 )); then
  echo "FATAL: /tmp below 3G after cleanup; gate cannot fit" >> "$STATUS"
  exit 9
fi

arm() {  # arm <label> <mode>
  local label=$1 mode=$2 rc out=/var/tmp/v063-bisect2-$1
  mode_set "$mode"
  echo "arm-$label map_mode=$(cat "$MM") start $(date -Iseconds)" >> "$STATUS"
  bash "$GATE" "$WHEEL" "$out" > "$out.driver.log" 2>&1
  rc=$?
  echo "arm-$label gate-exit=$rc map_mode=$(cat "$MM") end $(date -Iseconds)" >> "$STATUS"
}

arm A 3
arm B 0
mode_set 3
echo "restored map_mode=$(cat "$MM") $(date -Iseconds)" >> "$STATUS"
echo "bisect2 done $(date -Iseconds)" >> "$STATUS"
