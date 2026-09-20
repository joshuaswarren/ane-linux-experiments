#!/bin/bash
# Compiled-route calibration window, jw16 (v3.1, rewritten per Main
# review). Bounded: compiled-calibrate producer + post-exit report
# ONLY; no full curve; no performance conclusions.
#
# Contract (Main-reviewed):
#   * set -euo pipefail; every optional env via ${VAR:-default};
#     root asserted upfront in production (WRAPPER_TEST=1 stub-only).
#   * flock held across the ENTIRE load; released in cleanup BEFORE the
#     steady server starts (its own flock -n needs the lock free).
#   * DID_STOP=1 set BEFORE the first stop: a partial stop failure
#     still routes through cleanup, which restores BOTH units.
#   * cleanup is the SOLE restorer: captures the original rc, disables
#     traps, releases fd9, attempts BOTH unit starts independently
#     (a timer-start failure never skips the service start), verifies
#     BOTH active, verifies a real completion by parsing the JSON
#     (id + non-empty choices + non-empty message content); any failure
#     exits nonzero with RESTORE_FAILED (never a false RELEASE).
#   * report failure is always nonzero via NOT_GREEN.
#   * TERM/INT route through the same cleanup.
#   * timestamp-unique artifacts; refuses to overwrite existing.
set -euo pipefail
LOCK=${WRAPPER_LOCK:-/tmp/m1-gpu.lock}
GDB=${WRAPPER_GDB:-/var/tmp/gdb}
V=${WRAPPER_PYTHON:-/var/tmp/qmmceil/venv/bin/python}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
SLEEP_UNIT=${WRAPPER_SLEEP:-2}   # retry-poll interval; stub tests set 0
SLEEP_CALL=${WRAPPER_SLEEP:-4}
K=${WRAPPER_API_KEY:-}
if [[ ${WRAPPER_TEST:-0} != 1 ]]; then
  [[ $EUID -eq 0 ]] || { echo "FAIL: run as root"; exit 20; }
  K=$(cat /etc/llm-inference/api-key)
fi
STATE=RUN
DID_STOP=0

complete_check() {
  curl -fsS --max-time 60 http://127.0.0.1:8002/v1/chat/completions \
    -H "Content-Type: application/json" -H "Authorization: Bearer $K" \
    -d '{"model":"qwen3.8-27b","messages":[{"role":"user","content":"Reply with the single word: ready"}],"max_tokens":200}' \
  | python3 -c 'import json,sys
d = json.load(sys.stdin)
choices = d.get("choices") or []
content = (choices[0].get("message") or {}).get("content", "") if choices else ""
did = d.get("id", "")
if not choices or not content or not did:
    sys.exit(1)
print(did)'
}

cleanup() {
  local rc=$?
  trap - EXIT TERM INT
  echo "== cleanup (rc=$rc)"
  if [[ $DID_STOP -eq 1 ]]; then
    exec 9>&- || true
    echo "FD9-RELEASED"
    local t_ok=0 s_ok=0
    systemctl start llm-benchmark-recovery.timer && t_ok=1
    systemctl start llm-inference.service && s_ok=1
    local i
    for i in $(seq 1 15); do
      [[ $t_ok -eq 1 && $s_ok -eq 1 ]] \
        && systemctl is-active --quiet llm-inference \
        && systemctl is-active --quiet llm-benchmark-recovery.timer \
        && break
      sleep "$SLEEP_UNIT"
    done
    if [[ $t_ok -ne 1 || $s_ok -ne 1 ]] \
       || ! systemctl is-active --quiet llm-inference \
       || ! systemctl is-active --quiet llm-benchmark-recovery.timer; then
      echo "RESTORE_FAILED: units not active (timer_ok=$t_ok service_ok=$s_ok)"
      exit 31
    fi
    local id=""
    for i in $(seq 1 15); do
      id=$(complete_check || true)
      [[ -n "$id" ]] && break
      sleep "$SLEEP_CALL"
    done
    if [[ -z "$id" ]]; then
      echo "RESTORE_FAILED: no real completion"
      exit 32
    fi
    echo "RESTORE: units=active+timer completion=$id"
  fi
  if [[ $STATE == DONE && $rc -eq 0 ]]; then
    echo "RELEASE: state=DONE"
  else
    echo "NOT_GREEN: state=$STATE rc=$rc"
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "== pre-state"
systemctl is-active --quiet llm-inference \
  || { echo "FAIL: service not active; nothing was stopped by me"; exit 21; }
PRE=$(complete_check)
[[ -n "$PRE" ]] || { echo "FAIL: no pre completion"; exit 22; }
echo "PRE: $PRE"

NDJSON="$GDB/calibc-$STAMP.ndjson"
IDENT="$GDB/calibc-$STAMP.identity.json"
REPORT="$GDB/calibc-$STAMP.report.json"
SUMS="$GDB/calibc-$STAMP.sha256"
for f in "$NDJSON" "$IDENT" "$REPORT" "$SUMS"; do
  [[ -e $f ]] && { echo "FAIL: artifact $f exists; refusing overwrite"; exit 28; }
done

echo "== stop timer+service"
DID_STOP=1
systemctl stop llm-benchmark-recovery.timer
systemctl stop llm-inference.service
sleep "$SLEEP_UNIT"

exec 9>"$LOCK"
flock -n 9 || { echo "FAIL: lock busy"; exit 23; }
echo "LOCK-HELD pid=$$"

echo "== producer (compiled route)"
cd "$GDB"
[ -x "$V" ] || { echo "FAIL: venv python missing"; exit 24; }
MLX_OMARCHY_GPU_PROFILE="$NDJSON" \
MLX_OMARCHY_GPU_PROFILE_LABEL=compiled-calib-v241 \
"$V" "$GDB/qmm_weight_curve_micro.py" --pass compiled-calibrate \
  --k 2048 --cols 896 \
  --profile "$NDJSON" \
  --out "$IDENT"

echo "== report (offline; producer exited; units restored by cleanup)"
"$V" "$GDB/qmm_weight_curve_micro.py" --pass report \
  --profile "$NDJSON" \
  --plan-meta "$IDENT" \
  --out "$REPORT"

sha256sum "$NDJSON" "$IDENT" "$REPORT" | tee "$SUMS"
STATE=DONE
