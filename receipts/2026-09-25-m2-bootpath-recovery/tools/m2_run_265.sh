#!/bin/bash
# M2 Linux: one fw_start run of 265bb63 in the macOS power form
# (ane_sys_mpm off via fw_start_mpm_off=1, VENC rails left off).
# A userspace-petted hardware watchdog covers the run: a kernel hang stops
# the petting and resets the box into the jwm1 catcher. A clean run
# disarms it with the magic close.
# Usage: sudo ./m2_run_265.sh [extra module params...]
set -euo pipefail
cd /var/tmp/ane-psform
OUT=/var/tmp/ane-psform/run-$(date +%H%M%S)
mkdir -p "$OUT"
say() { echo "$(date +%T) $*" | tee -a "$OUT/run.log"; }

say "kernel $(uname -r), boot $(uptime -s)"
if lsmod | grep -qE "^ane_t6021|^ane_ascdbg"; then
    say "an ANE module is already loaded; this run needs a fresh boot"
    exit 1
fi
sha256sum ane_t6021_rtclient.ko | tee -a "$OUT/run.log"

WDT=/dev/watchdog0
[ -e "$WDT" ] || WDT=/dev/watchdog
wdctl "$WDT" 2>&1 | tee -a "$OUT/run.log" || true
wdctl -s 60 "$WDT" >/dev/null 2>&1 || true
exec 3>"$WDT"
( while :; do printf . >&3 || exit; sleep 5; done ) &
PET=$!
say "watchdog armed on $WDT, petter $PET"

PARAMS="fw_load=1 fw_alias_reserved=1 fw_start=1 fw_start_mpm_off=1 fw_start_venc_gates=0 patch_timer_freq=0x016e3600 $*"
echo "RUN-265 $(date +%T) $PARAMS" > /dev/kmsg
say "insmod $PARAMS"
set +e
insmod ane_t6021_rtclient.ko $PARAMS
RC=$?
set -e
say "insmod rc=$RC"
sleep 30
dmesg | awk '/RUN-265/{f=1} f' > "$OUT/dmesg.txt"
grep -E "PS-FORM|BOOT-PHASE|VENC|timer-freq|SCRATCH7|READY|HELLO|EPMAP|rtkit|HELD|fw_start|STAMP|FW-TT|CPU_STATUS|ane_cpu" \
    "$OUT/dmesg.txt" | tee -a "$OUT/run.log" | tail -n 40

kill "$PET"
printf V >&3
exec 3>&-
say "watchdog disarmed (magic close); OUT=$OUT"
