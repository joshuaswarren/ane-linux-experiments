#!/bin/sh
# omarchy-now — return the parked m2-host to Omarchy over the live m1n1 USB proxy.
# Stops the m1n1-proxy-watcher, verifies the pre-proxy boot.bin by sha, and
# chainloads it (loads the payload into the running m1n1 and jumps — no ESP write).
# Usage: omarchy-now.sh [--dry-run]        (default: dry-run)
#        omarchy-now.sh --chainload        (real: stops watcher, chainloads)
set -u
M2ROOT=${M2ROOT:-/var/tmp/m2proxy}
M2PY=${M2PY:-/var/tmp/m2proxy-venv/bin/python}
M1N1TREE=$M2ROOT/scripts/.work-m1n1-proxyclient
IMG=$M2ROOT/boot.bin.pre-proxy
EXPECT_SHA=153170e065383767a47bc234e02344ecdc09d03f4003d92e6a2d6e464fad1ff5
WATCHER=m1n1-proxy-watcher.service
M2_VID=1209
M2_PID=316d

mode=${1:---dry-run}
case $mode in --dry-run|--chainload) ;; *) echo "usage: omarchy-now.sh [--dry-run|--chainload]" >&2; exit 64;; esac

rc=0
if [ -f "$IMG" ]; then
    if echo "$EXPECT_SHA  $IMG" | sha256sum -c - >/dev/null 2>&1; then
        echo "image: OK  $IMG ($EXPECT_SHA)"
    else
        echo "image: SHA MISMATCH  $IMG (expected $EXPECT_SHA, got $(sha256sum "$IMG" | cut -d' ' -f1))" >&2
        rc=1
    fi
else
    echo "image: MISSING  $IMG (copy from m2-host:/var/tmp/m2proxy-staging/boot.bin.pre-proxy once Linux is restored)" >&2
    rc=2
fi

dev=""
for d in /dev/ttyACM* /dev/ttyUSB*; do
    [ -e "$d" ] || continue
    sysdev=$(udevadm info -q path "$d" 2>/dev/null) || continue
    [ -n "$sysdev" ] || continue
    vid=$(cat "/sys${sysdev}/../idVendor" 2>/dev/null || cat "/sys${sysdev}/../../idVendor" 2>/dev/null)
    pid=$(cat "/sys${sysdev}/../idProduct" 2>/dev/null || cat "/sys${sysdev}/../../idProduct" 2>/dev/null)
    if [ "$vid" = "$M2_VID" ] && [ "$pid" = "$M2_PID" ]; then
        dev=$d
        break
    fi
done
if [ -n "$dev" ]; then
    echo "device: $dev (m1n1 USB proxy present)"
else
    echo "device: none (no m1n1 USB gadget 1209:316d on this host)" >&2
    [ "$rc" -eq 0 ] && rc=3
fi

if [ "$mode" = "--dry-run" ]; then
    echo "dry-run: would do -- systemctl stop $WATCHER; M1N1DEVICE=$dev $M2PY $M1N1TREE/tools/chainload.py $IMG"
    exit $rc
fi

[ "$rc" -eq 0 ] || exit $rc

echo "stopping $WATCHER"
systemctl stop "$WATCHER"
cd "$M1N1TREE" || exit 1
echo "chainloading $IMG via $dev ..."
M1N1DEVICE=$dev "$M2PY" tools/chainload.py "$IMG"
echo "chainload issued — m2-host should now boot Omarchy from its own ESP"
