#!/usr/bin/env bash
# Run one BO_INIT bisect stage and report whether the machine survived.
#
# Stages come from scripts/ane-driver-bostage.py:
#   1  lock only, no IOVA reservation   (pure CPU)
#   2  reserve IOVA, no iommu_map       (pure CPU)
#   3  map exactly one page, unwind     (first page-table write)
#   99 normal
#
# Logs to disk with fsync BEFORE the risky ioctl, because an SoC reset takes
# the netconsole tail with it.
#
#   usage: sudo bash ane-bo-bisect.sh <stage>
set -uo pipefail

stage="${1:?usage: ane-bo-bisect.sh <stage>}"
log=""$HOME"/ane-boot/bo-stage-${stage}.log"
ko="$HOME"/ane-boot/ane-instrumented.ko

exec > >(tee -a "$log") 2>&1
echo "=== BO stage $stage begin $(date -Is) ==="

bash "$HOME"/ane-boot/ane-fullchain-test.sh new 2>&1 | grep -E "CHAIN_ALL|TM_READ_OK"

rmmod ane 2>/dev/null || true
insmod "$ko" ane_skip_genpd=1 ane_skip_power=1 ane_np_map=1 \
    ane_bo_stop_stage="$stage" || { echo "insmod failed"; exit 1; }
printf on > /sys/bus/platform/devices/26bc04000.ane/power/control
echo "module loaded, stage=$stage"

test -c /dev/accel/accel0 || { echo "no accel node"; exit 1; }
sync

echo "--- issuing BO_INIT via example ---"
sync
cd "$HOME"/src/apple-ane
timeout 45 python3 "$HOME"/ane-boot/ane-ioctl-trace.py \
    examples/elementwise.py add 2>&1 | grep -E "BO_INIT|FAILED|output" | head -4
rc=$?

sync
echo "=== SURVIVED stage $stage (python rc=$rc) ==="
dmesg | grep -oE "bo: (stop stage|mapping).*" | tail -3
sync
