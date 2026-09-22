#!/bin/sh
# omarchy-now — return the parked m2-host to Omarchy over the live m1n1 USB proxy.
# Stops the m1n1-proxy-watcher, verifies the return boot.bin, and chainloads it
# (loads the payload into the running m1n1 and jumps — no ESP write).
#
# Usage: omarchy-now.sh [--dry-run] [--image PATH]
#        omarchy-now.sh --chainload [--image PATH]
# Image resolution: --image PATH, else /var/tmp/m2proxy/boot.bin.pre-proxy,
# else the proxy host's own /boot/efi/m1n1/boot.bin (update-m1n1 concatenates
# m1n1 + u-boot-nodtb + all apple dtbs, so the same file boots m2-host's t6021;
# u-boot then loads grub from m2-host's ESP as normal).
#
# Sha policy: the canonical return image is sha 153170e0…ff5 (m2-host's live
# pre-proxy boot.bin, m1n1 1.6.1-1). The proxy host's ESP image hashes
# differently (41a39ac7…, its own update-m1n1 build — same m1n1 1.6.1-1,
# uboot-asahi 2026.07.asahi2-1; m2-host has no separate asahi-dtbs package,
# dtbs ship inside the m1n1/uboot builds on both). A mismatched sha is only
# accepted when the image was given explicitly via --image, so a silent
# fallback can never chainload an unverified file.
#
# Modes: default --dry-run (prints status, changes nothing).
#        --chainload: preconditions verified BEFORE the watcher is stopped,
#        so any refusal leaves the watcher running.
set -u
M2ROOT=${M2ROOT:-/var/tmp/m2proxy}
M2PY=${M2PY:-/var/tmp/m2proxy-venv/bin/python}
M1N1TREE=$M2ROOT/scripts/.work-m1n1-proxyclient
DEFAULT_IMG=$M2ROOT/boot.bin.pre-proxy
LOCAL_IMG=/boot/efi/m1n1/boot.bin
EXPECT_SHA=153170e065383767a47bc234e02344ecdc09d03f4003d92e6a2d6e464fad1ff5
WATCHER=m1n1-proxy-watcher.service
M2_VID=1209
M2_PID=316d

mode=--dry-run
IMG=""
while [ $# -gt 0 ]; do
    case $1 in
        --dry-run|--chainload) mode=$1 ;;
        --image) [ $# -ge 2 ] || { echo "--image needs a path" >&2; exit 64; }; IMG=$2; shift ;;
        *) echo "usage: omarchy-now.sh [--dry-run|--chainload] [--image PATH]" >&2; exit 64 ;;
    esac
    shift
done

explicit=0
if [ -n "$IMG" ]; then
    explicit=1
elif [ -f "$DEFAULT_IMG" ]; then
    IMG=$DEFAULT_IMG
elif [ -f "$LOCAL_IMG" ]; then
    IMG=$LOCAL_IMG
    echo "note: $DEFAULT_IMG absent — falling back to this host's $IMG (update-m1n1 build; boots m2-host's t6021)"
fi

rc=0
if [ -n "$IMG" ] && [ -f "$IMG" ]; then
    got=$(sha256sum "$IMG" | cut -d' ' -f1)
    if [ "$got" = "$EXPECT_SHA" ]; then
        echo "image: OK  $IMG ($got)"
    elif [ "$explicit" -eq 1 ]; then
        echo "image: SHA MISMATCH (explicit --image, allowed)  $IMG" >&2
        echo "       expected $EXPECT_SHA, got $got" >&2
        echo "       confirm package parity before trusting: pacman -Q m1n1 uboot-asahi on both hosts" >&2
    else
        echo "image: SHA MISMATCH (refused — re-try with --image $IMG to override)" >&2
        echo "       expected $EXPECT_SHA, got $got" >&2
        rc=1
    fi
else
    echo "image: MISSING  $DEFAULT_IMG (and no $LOCAL_IMG) — copy from m2-host:/var/tmp/m2proxy-staging/boot.bin.pre-proxy once Linux is restored" >&2
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
