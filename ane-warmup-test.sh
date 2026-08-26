#!/usr/bin/env bash
# Find the minimal warm-up that makes the first ANE op survive a fresh boot.
#
# Measured on the target machine: going straight to a normal module load plus one op on
# a fresh boot resets the SoC. Running the gated bisect stages 1, 2 and 3 first
# - each of which loads the module, fails a BO_INIT early, and unloads - makes
# the very next normal load compute correctly, repeatedly.
#
# So some state established by a prior load/attach cycle is required. This
# tests the two candidates:
#
#   reload  load, pin, unload, load, pin, op      (no BO_INIT during warm-up)
#   gated   load, pin, failing BO_INIT, unload, load, pin, op
#
# Markers go to /dev/kmsg because netconsole is the only channel that survives
# the reset here.
#
#   usage: sudo bash ane-warmup-test.sh <reload|gated|none>
set -uo pipefail

mode="${1:?usage: ane-warmup-test.sh <reload|gated|none>}"
ko="$HOME"/ane-boot/ane-instrumented.ko
dev=/sys/bus/platform/devices/26bc04000.ane
examples="$HOME"/src/apple-ane

mark() {
    printf 'ANE_WARMUP: %s\n' "$1" | tee -a /dev/kmsg >/dev/null 2>&1 || true
    printf '%s\n' "$1"
}

power_and_load() {
    # Capture first: piping into `grep -q` closes the pipe on first match, and
    # with pipefail that SIGPIPE looks like a power failure.
    local out
    out=$(bash "$HOME"/ane-boot/ane-fullchain-test.sh new 2>&1)
    case "$out" in
        *CHAIN_ALL_ACTIVE*) ;;
        *) mark "power failed"; exit 1 ;;
    esac
    rmmod ane 2>/dev/null || true
    insmod "$ko" ane_skip_genpd=1 ane_skip_power=1 ane_np_map=1 "$@" || {
        mark "insmod failed"; exit 1; }
    printf on | tee "$dev/power/control" >/dev/null
}

mark "BEGIN mode=$mode uptime=$(cut -d' ' -f1 /proc/uptime)"

case "$mode" in
  reload)
    mark "warmup: load+pin, no ioctl"
    power_and_load
    mark "warmup: unload"
    rmmod ane
    mark "warmup done"
    ;;
  gated)
    mark "warmup: load+pin with ane_bo_stop_stage=1"
    power_and_load ane_bo_stop_stage=1
    mark "warmup: issuing failing BO_INIT"
    (cd "$examples" && timeout 30 python3 examples/elementwise.py add \
        > /dev/null 2>&1) || true
    mark "warmup: unload"
    rmmod ane
    mark "warmup done"
    ;;
  none)
    mark "no warmup"
    ;;
  *)
    mark "unknown mode"; exit 1 ;;
esac

mark "STEP real_load"
power_and_load
mark "STEP first_op"
cd "$examples" || exit 1
if timeout 45 python3 examples/elementwise.py add 2>&1 | grep -q "^output"; then
    mark "RESULT op_computed mode=$mode"
else
    mark "RESULT op_failed mode=$mode"
fi
