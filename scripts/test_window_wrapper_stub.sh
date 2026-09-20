#!/bin/bash
# Stub test for window-compiled-calib.sh v3.1 (Main: actual GREEN stub
# test required; is-active stub MUST reflect state).
#   A producer failure   -> fd9 released before service start, restore
#                           receipt, NOT GREEN, rc=3
#   B restore failure    -> RESTORE_FAILED (timer start fails, timer
#                           stays inactive), nonzero, never RELEASE DONE
#   C precheck failure   -> units untouched (no stop, no start), rc=21
#   D partial stop fail  -> DID_STOP still routes to cleanup restore,
#                           RESTORE receipt, NOT GREEN, nonzero
#   E unset env defaults -> root assert fires cleanly (exit 20), no
#                           unbound-variable crash
# No GPU, no root: systemctl/curl/python3 are stubbed; python3 is a
# passthrough to the REAL interpreter so the wrapper's strict JSON
# completion check runs for real. No symlink chmod.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WRAPPER="${WRAPPER_UNDER_TEST:-$HERE/../receipts/2026-09-19-gated-barriers-default-t6001-test-host.d/window-compiled-calib.sh}"
TD=$(mktemp -d)
trap 'rm -rf "$TD"' EXIT
mkdir -p "$TD/bin" "$TD/gdb"
: > "$TD/lock"
echo 1 > "$TD/svc_state"
echo 1 > "$TD/timer_state"
: > "$TD/units.log"

cat > "$TD/bin/systemctl" <<EOF
#!/bin/bash
echo "\$* (fd9=\$([[ -e /proc/\$PPID/fd/9 ]] && echo HELD || echo closed))" >> "$TD/units.log"
case "\$*" in
  "is-active --quiet llm-inference")
    [[ \$(cat "$TD/svc_state") == 1 ]] && exit 0 || exit 3 ;;
  "is-active --quiet llm-benchmark-recovery.timer")
    [[ \$(cat "$TD/timer_state") == 1 ]] && exit 0 || exit 3 ;;
  "start llm-benchmark-recovery.timer")
    [[ \${RESTORE_BREAK:-0} == 1 ]] && exit 1
    echo 1 > "$TD/timer_state"; exit 0 ;;
  "start llm-inference.service")
    : # Only the timer fails in RESTORE_BREAK; service restart is still attempted.
    echo 1 > "$TD/svc_state"; exit 0 ;;
  "stop llm-benchmark-recovery.timer")
    [[ \${STOP_TIMER_FAIL:-0} == 1 ]] && exit 1
    echo 0 > "$TD/timer_state"; exit 0 ;;
  "stop llm-inference.service")
    [[ \${STOP_SERVICE_FAIL:-0} == 1 ]] && exit 1
    echo 0 > "$TD/svc_state"; exit 0 ;;
esac
exit 0
EOF
cat > "$TD/bin/curl" <<'EOF'
#!/bin/bash
if [[ $(cat "$STATE_DIR/svc_state") == 1 ]]; then
  echo '{"id":"chatcmpl-STUB","choices":[{"message":{"role":"assistant","content":"ready"}}]}'
else
  echo "curl-stub: service down" >&2
  exit 7
fi
EOF
printf '#!/bin/bash\nexec /usr/bin/python3 "$@"\n' > "$TD/bin/python3"
cat > "$TD/gdb/producer.py" <<'EOF'
#!/bin/bash
[[ ${PRODUCER_FAIL:-0} == 1 ]] && exit 3
exit 0
EOF
chmod +x "$TD/bin/systemctl" "$TD/bin/curl" "$TD/bin/python3" "$TD/gdb/producer.py"

export STATE_DIR="$TD"
export WRAPPER_TEST=1
export WRAPPER_LOCK="$TD/lock"
export WRAPPER_GDB="$TD/gdb"
export WRAPPER_PYTHON="$TD/gdb/producer.py"
export WRAPPER_SLEEP=0
export PATH="$TD/bin:$PATH"

run() { PRODUCER_FAIL=${1:-0} bash "$WRAPPER"; }
set +e   # the suite manages failure codes explicitly

echo "== case A: producer failure"
: > "$TD/units.log"; echo 1 > "$TD/svc_state"; echo 1 > "$TD/timer_state"
PRODUCER_FAIL=1 bash "$WRAPPER" > "$TD/outA" 2>&1
rcA=$?
has() { grep -q "$2" "$1" || { echo "FAIL $3: missing '$2'"; cat "$1"; exit 1; }; }
lacks() { grep -q "$2" "$1" && { echo "FAIL $3: unexpected '$2'"; cat "$1"; exit 1; } || true; }
has "$TD/outA" "FD9-RELEASED" A
has "$TD/outA" "RESTORE: units=active+timer" A
has "$TD/outA" "NOT_GREEN" A
lacks "$TD/outA" "RELEASE: state=DONE" A
assert_rc() { [[ $1 -ne 0 ]] || { echo "FAIL $2: zero rc"; exit 1; }; }
assert_rc "$rcA" A
grep -q "start llm-inference.service (fd9=closed)" "$TD/units.log" \
  || { echo "FAIL A: service started while fd9 still held"; cat "$TD/units.log"; exit 1; }
echo "case A: green (rc=$rcA, NOT_GREEN, fd9 released before service start)"

echo "== case B: restore failure (timer start fails)"
: > "$TD/units.log"; echo 1 > "$TD/timer_state"
RESTORE_BREAK=1 PRODUCER_FAIL=1 bash "$WRAPPER" > "$TD/outB" 2>&1
rcB=$?
has "$TD/outB" "RESTORE_FAILED" B
lacks "$TD/outB" "RELEASE: state=DONE" B
assert_rc "$rcB" B
echo "case B: green (rc=$rcB, RESTORE_FAILED)"

echo "== case C: precheck failure leaves units untouched"
: > "$TD/units.log"; echo 0 > "$TD/svc_state"; echo 1 > "$TD/timer_state"
bash "$WRAPPER" > "$TD/outC" 2>&1
rcC=$?
has "$TD/outC" "FAIL: service not active" C
lacks "$TD/units.log" "stop llm-inference.service" C
lacks "$TD/units.log" "start llm-inference.service" C
assert_rc "$rcC" C
assert_eq() { [[ "$1" == "$2" ]] || { echo "FAIL $3: '$1' != '$2'"; exit 1; }; }
assert_eq "$rcC" "21" "C exact rc"
echo "case C: green (rc=21, units untouched)"

echo "== case D: partial stop failure still restores"
: > "$TD/units.log"; echo 1 > "$TD/svc_state"; echo 1 > "$TD/timer_state"
STOP_SERVICE_FAIL=1 bash "$WRAPPER" > "$TD/outD" 2>&1
rcD=$?
has "$TD/outD" "RESTORE: units=active+timer" D
has "$TD/outD" "NOT_GREEN" D
lacks "$TD/outD" "RELEASE: state=DONE" D
assert_rc "$rcD" D
echo "case D: green (rc=$rcD, NOT_GREEN, restored)"

echo "== case E: unset env defaults -> clean root assert"
: > "$TD/units.log"
env -u WRAPPER_TEST -u WRAPPER_PYTHON -u WRAPPER_LOCK -u WRAPPER_GDB \
    -u WRAPPER_API_KEY -u STATE_DIR -u WRAPPER_SLEEP \
    bash "$WRAPPER" > "$TD/outE" 2>&1
rcE=$?
has "$TD/outE" "FAIL: run as root" E
assert_rc "$rcE" E
assert_eq "$rcE" "20" "E exact rc"
echo "case E: green (rc=20, root assert, no unbound crash)"

echo "PASS: A(rc=$rcA NOT_GREEN) B(rc=$rcB RESTORE_FAILED) C(rc=$rcC untouched) D(rc=$rcD restored) E(rc=$rcE root-assert)"
