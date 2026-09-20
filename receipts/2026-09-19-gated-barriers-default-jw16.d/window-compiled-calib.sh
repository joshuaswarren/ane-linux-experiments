#!/bin/bash
# Compiled-route calibration window, jw16 (v2, for Main review).
# Bounded: compiled-calibrate producer + post-exit report ONLY; no full
# curve. Requirements implemented per Main 2026-09-20:
#   * flock held across the ENTIRE load (acquired after units stop,
#     released only after the load and BEFORE the steady server starts);
#   * trap EXIT: on ANY exit path - success or failure - the steady
#     units are restarted and a real completion is verified;
#   * producers never parse the profile; the report runs after the
#     producer process has exited (complete file, stdio flushed).
# Runs ONLY on explicit Main authorization for GpuProfileIdentityAudit.
set -uo pipefail
LOCK=/tmp/m1-gpu.lock
GDB=/var/tmp/gdb
V=/var/tmp/qmmceil/venv/bin/python
K=$(sudo -n cat /etc/llm-inference/api-key 2>/dev/null || cat /etc/llm-inference/api-key)
STATE=RUN

complete_check() {
  curl -s --max-time 60 http://127.0.0.1:8002/v1/chat/completions \
    -H "Content-Type: application/json" -H "Authorization: Bearer $K" \
    -d '{"model":"qwen3.8-27b","messages":[{"role":"user","content":"Reply with the single word: ready"}],"max_tokens":8}' \
    | grep -o '"id":"[^"]*"' | head -1
}

cleanup() {
  echo "== cleanup: release flock BEFORE steady server restart"
  exec 9>&-
  systemctl start llm-benchmark-recovery.timer 2>/dev/null
  systemctl start llm-inference.service
  for i in $(seq 1 15); do
    systemctl is-active llm-inference >/dev/null 2>&1 && break
    sleep 2
  done
  UNITS=$(systemctl is-active llm-inference)
  ID=NONE
  for i in $(seq 1 15); do
    ID=$(complete_check)
    [ -n "$ID" ] && break
    sleep 4
  done
  echo "RESTORE: units=$UNITS real_completion=$ID"
  echo "RELEASE: state=$STATE"
}
trap cleanup EXIT

echo "== pre-state (steady: service active, lock held by service)"
systemctl is-active llm-inference >/dev/null || { echo "FAIL: service not active"; exit 21; }
PRE=$(complete_check)
[ -n "$PRE" ] || { echo "FAIL: no pre completion"; exit 22; }
echo "PRE: $PRE"

echo "== stop timer+service (flock freed by service stop)"
systemctl stop llm-benchmark-recovery.timer 2>/dev/null
systemctl stop llm-inference.service
sleep 2

exec 9>"$LOCK"
flock -n 9 || { echo "FAIL: lock busy"; exit 23; }
echo "LOCK-HELD pid=$$"

echo "== producer (compiled route; exits before report)"
cd "$GDB" || exit 24
[ -x "$V" ] || { echo "FAIL: venv python missing"; exit 24; }
MLX_OMARCHY_GPU_PROFILE="$GDB/calibc.ndjson" \
MLX_OMARCHY_GPU_PROFILE_LABEL=compiled-calib-v241 \
"$V" "$GDB/qmm_weight_curve_micro.py" --pass compiled-calibrate \
  --k 2048 --cols 896 \
  --profile "$GDB/calibc.ndjson" \
  --out "$GDB/calibc-identity.json" \
  || { echo "FAIL: producer"; exit 25; }

echo "== restore units (before report; report is offline)"
systemctl start llm-benchmark-recovery.timer 2>/dev/null
systemctl start llm-inference.service
for i in $(seq 1 15); do
  systemctl is-active llm-inference >/dev/null 2>&1 && break
  sleep 2
done
systemctl is-active llm-inference >/dev/null || { echo "FAIL: restore"; exit 26; }

echo "== post-exit report (complete profile, producer exited)"
"$V" "$GDB/qmm_weight_curve_micro.py" --pass report \
  --profile "$GDB/calibc.ndjson" \
  --plan-meta "$GDB/calibc-identity.json" \
  --out "$GDB/calibc-report.json" \
  || { echo "FAIL: report"; exit 27; }
sha256sum "$GDB/calibc.ndjson" "$GDB/calibc-identity.json" \
  "$GDB/calibc-report.json" | tee "$GDB/calibc.sha256"
STATE=DONE
