#!/usr/bin/env bash
# Bring the Apple Neural Engine up on the target machine and prove it computes.
#
# Requires the v5 device tree (engine window 0x26bc04000 size 0x24000), loaded
# by the persistent ANE boot entry, and a module built with the stage gates from
# scripts/ane-driver-bostage.py.
#
# WHY THE LADDER
#
# Going straight to a normal load plus one op on a fresh boot resets the SoC,
# reproducibly. Running the gated stages first - each loads the module, fails a
# BO_INIT early, and is then replaced - makes the very next normal load compute
# correctly, also reproducibly:
#
#   stage 1  take the iommu lock, reserve nothing        (pure CPU)
#   stage 2  reserve an IOVA, map nothing                (pure CPU)
#   stage 3  map exactly one page, then unwind           (first page-table write)
#   normal   full path, real op
#
# So some state established by a prior attach cycle is required before the
# first real mapping survives. That is a genuine bug in the out-of-tree KMD's
# attach path, not a property of the hardware, and it is recorded in
# docs/jw-m1.md as the next thing to fix. Until then this ladder is the
# reliable route, and it costs about fifteen seconds.
#
# Two further rules, both measured:
#   * Runtime PM must be pinned right after each insmod. Otherwise autosuspend
#     invalidates DART TLBs about a second later, including dart0 which
#     apple-dart owns, and resets the SoC.
#   * The shared DART irq is left ENABLED. Upstream's ane_disable_dart_irq=1
#     makes the first submission fatal here.
#
#   usage: sudo bash ane-bringup.sh [--quiet]
set -uo pipefail

ko="${ANE_KO:-"$HOME"/ane-boot/ane-instrumented.ko}"
dev=/sys/bus/platform/devices/26bc04000.ane
examples="$HOME"/src/apple-ane
quiet="${1:-}"

mark() {
    printf 'ANE_BRINGUP: %s\n' "$1" | tee -a /dev/kmsg >/dev/null 2>&1 || true
    [ "$quiet" = "--quiet" ] || printf '%s\n' "$1"
}

test -e /proc/device-tree/soc/ane@26a000000 || {
    echo "no ANE node: boot the ANE entry first" >&2; exit 1; }
test -f "$ko" || { echo "missing module $ko" >&2; exit 1; }
grep -q ane_bo_stop_stage <(modinfo "$ko" 2>/dev/null) || {
    echo "module lacks ane_bo_stop_stage; rebuild with ane-driver-bostage.py" >&2
    exit 1; }

power_chain() {
    local out
    out=$(bash "$HOME"/ane-boot/ane-fullchain-test.sh new 2>&1)
    case "$out" in
        *CHAIN_ALL_ACTIVE*) return 0 ;;
        *) mark "POWER_FAIL"; return 1 ;;
    esac
}

load() {  # load [extra module args]
    # Re-raise the power chain before every load. The working sequence did this
    # per stage, and the module's remove path is known to be broken (it leaks
    # IOVA mappings), so state after an rmmod cannot be assumed.
    power_chain || return 1
    rmmod ane 2>/dev/null || true
    insmod "$ko" ane_skip_genpd=1 ane_skip_power=1 ane_np_map=1 "$@" || return 1
    [ -e "$dev/power/control" ] && printf on | tee "$dev/power/control" >/dev/null
    return 0
}

for stage in 1 2 3; do
    mark "LADDER stage=$stage"
    load "ane_bo_stop_stage=$stage" || { mark "insmod failed at stage $stage"; exit 1; }
    # The gated BO_INIT is expected to fail; only its side effect matters.
    (cd "$examples" && timeout 30 python3 examples/elementwise.py add \
        >/dev/null 2>&1) || true
done

mark "LADDER complete, loading normally"
load || { mark "insmod failed"; exit 1; }
sync
test -c /dev/accel/accel0 || { mark "ANE_MISSING"; exit 1; }
mark "ANE_READY /dev/accel/accel0"

if (cd "$examples" && timeout 45 python3 examples/elementwise.py add 2>&1 |
        grep -q "^output"); then
    mark "ANE_VERIFIED elementwise add computed"
else
    mark "ANE_SELFTEST_FAILED"
    exit 1
fi
