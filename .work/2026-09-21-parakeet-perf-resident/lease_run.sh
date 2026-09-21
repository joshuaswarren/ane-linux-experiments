#!/bin/bash
# lease_run.sh — Bounded m1-test-host /dev/accel/accel0 lease for ParakeetPerformance.
# Protocol: acquire /tmp/m1-gpu.lock inode 27 (flock, 1200s ceiling),
# run perf-battery.sh (warm + 10 measured), release lock. Output to
# /var/tmp/m1-test-host-ane-step2/fused-e2e/baseline-reconfirm-TS/.
#
# Identity pinned at run start; matches perf-battery-receipt.json (2026-09-20).
set -uo pipefail

LOCK=/tmp/m1-gpu.lock
LOCK_TIMEOUT_S=1200
TS=$(date +%Y%m%dT%H%M%S)
BASE=/var/tmp/m1-test-host-ane-step2/fused-e2e/baseline-reconfirm-$TS
LOG=$BASE/run.log
mkdir -p "$BASE"
chmod 755 "$BASE"

# Critical: the entire body runs under flock; exit (any signal) releases it.
exec 9>"$LOCK"
echo "ACQUIRE_LOCK_ATTEMPT $(date -u -Ins) host=$(hostname) inode=$(stat -c %i $LOCK)" >> "$LOG"
if ! flock -w $LOCK_TIMEOUT_S 9; then
  echo "FAILED_TO_ACQUIRE_LOCK $(date -u -Ins) timeout=${LOCK_TIMEOUT_S}s" >> "$LOG"
  cat "$LOG"
  exit 2
fi
echo "LOCK_HELD $(date -u -Ins) pid=$$ ppid=$PPID" >> "$LOG"

# Identity pin before any work — verifies the binary state at run time.
{
  echo "=== IDENTITY ==="
  date -u -Ins
  hostname
  uname -r
  echo "VK_DRIVER_FILES=/tmp/mesa-sin-ftz-m1-test-host/m1-test-host-e167-icd.json"
  echo "MLX_OMARCHY_PLACED=AC"
  echo "ANE_ISLAND_MODE=\${ANE_ISLAND_MODE-<unset: code default resident-batch>}"
  sha256sum \
    /var/tmp/m1-test-host-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker \
    /var/tmp/m1-test-host-ane-step2/libane.so \
    /tmp/mesa-sin-ftz-m1-test-host/drivers/libvulkan_asahi-e167.so \
    /var/tmp/encwall-v071/base/vulkan_encoder.py \
    /var/tmp/m1-test-host-ane-step2/fused-e2e/fused_e2e.py \
    /var/tmp/m1-test-host-v072rc1/venv/bin/python3
  echo "driver-buildid: $(readelf -n /tmp/mesa-sin-ftz-m1-test-host/drivers/libvulkan_asahi-e167.so | sed -n 's/.*Build ID: //p')"
} > "$BASE/identity.txt" 2>&1

# Run perf-battery.sh; tee the inner run to BASE/run.log
echo "=== PERF_BATTERY_START $(date -u -Ins) ===" >> "$LOG"
bash /tmp/parakeet-perf-resident/perf-battery.sh 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
echo "=== PERF_BATTERY_END $(date -u -Ins) rc=$RC ===" >> "$LOG"

echo "LOCK_RELEASE $(date -u -Ins)" >> "$LOG"
# flock auto-releases on exec/file-descriptor close; explicit for clarity.
flock -u 9

echo "=== SUMMARY ==="
echo "BASE=$BASE"
echo "RC=$RC"
exit $RC
