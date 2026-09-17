#!/bin/bash
# v0.6.3 gate-failure bisect driver (jwm1). One variable per arm.
#   Arm A: map_mode=3 clean re-run  — does the reported failure reproduce?
#   Arm B: map_mode=0               — single-variable rollback, same gate.
# Then the pinned decode leg via the exact v0.6.2 procedure (GPU path,
# mode-independent) on the v0.6.3 wheel. Never steals /tmp/m1-gpu.lock.
set -u
WHEEL=/var/tmp/v062-wt/dist/mlx_omarchy-0.32.2.dev202609171159+1ed1dab-cp314-cp314-linux_aarch64.whl
GATE=/var/tmp/v062-wt/receipts/2026-09-16-parakeet-wheel-packaging/gate-jwm1.sh
MM=/sys/module/ane/parameters/map_mode
STATUS=/var/tmp/v063-bisect.status
: > "$STATUS"

arm() {  # arm <label> <mode>
  local label=$1 mode=$2 rc out=/var/tmp/v063-bisect-$1
  echo "$mode" | sudo -n tee "$MM" >/dev/null
  echo "arm-$label map_mode=$(cat "$MM") start $(date -Iseconds)" >> "$STATUS"
  bash "$GATE" "$WHEEL" "$out" > "$out.driver.log" 2>&1
  rc=$?
  echo "arm-$label gate-exit=$rc map_mode=$(cat "$MM") end $(date -Iseconds)" >> "$STATUS"
}

arm A 3
arm B 0
echo 3 | sudo -n tee "$MM" >/dev/null
echo "restored map_mode=$(cat "$MM") $(date -Iseconds)" >> "$STATUS"

# --- pinned decode leg: v0.6.2 procedure on the v0.6.3 wheel ---
if [[ ! -x /var/tmp/V063PIN-venv/bin/python ]]; then
  python3 -m venv /var/tmp/V063PIN-venv
  /var/tmp/V063PIN-venv/bin/pip install --quiet mlx-lm==0.31.3
  /var/tmp/V063PIN-venv/bin/pip install --quiet --no-deps --force-reinstall "$WHEEL"
fi
flock -w 900 /tmp/m1-gpu.lock env HF_HUB_OFFLINE=1 MLX_DISABLE_COMPILE=1 \
  /var/tmp/V063PIN-venv/bin/python /var/tmp/v062-wt/scripts/bench_matrix.py \
  --mode run --select longctx-1024-decode-32 \
  > /var/tmp/v063-bisect-decode.json 2>/var/tmp/v063-bisect-decode.log
echo "decode-exit=$?" >> "$STATUS"
echo "bisect done $(date -Iseconds)" >> "$STATUS"
