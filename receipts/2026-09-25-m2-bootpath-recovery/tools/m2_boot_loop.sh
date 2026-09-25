#!/bin/bash
# Arm on jwm1. Each time the M2's 43ec stage-1 proxy appears, clear any
# foreign ACM holder and run one unbroken proxy session that chainloads the
# M2's own Linux kernel (m2_linux_boot.py), bypassing the hanging U-Boot.
# panic=30 makes a panicking kernel reboot into the next catch. At most
# MAX_BOOTS chainloads per arming, so a boot loop stops by itself.
set -u
PX=$HOME/m2proxy
CACHE=$PX/m2boot
MAX_BOOTS=${MAX_BOOTS:-3}
OUT=$PX/hvlogs/bootloop-$(date -u +%Y%m%dT%H%M%S)
mkdir -p "$OUT"
LOG=$OUT/loop.log
say() { echo "$(date -u +%T) $*" | tee -a "$LOG"; }
say "armed: up to $MAX_BOOTS chainloads, cache $CACHE"
for n in $(seq 1 "$MAX_BOOTS"); do
    say "boot $n: waiting for /dev/ttyACM0 (up to 8 h)"
    for _ in $(seq 1 57600); do
        [ -e /dev/ttyACM0 ] && break
        sleep 0.5
    done
    [ -e /dev/ttyACM0 ] || { say "no ttyACM0"; exit 1; }
    say "ttyACM0 present: $(sudo -n dmesg | grep -E 'usb 1-1: Product' | tail -n 1)"
    for pid in $(sudo -n fuser /dev/ttyACM0 /dev/ttyACM1 2>/dev/null); do
        say "foreign holder $pid: $(ps -o cmd= -p "$pid")"
        sudo -n kill "$pid"
    done
    cd "$PX/hvproxy/proxyclient" || exit 1
    sudo -n env PYTHONPATH="$PX/pylib:.:$PX" M1N1DEVICE=/dev/ttyACM0 timeout 900 \
        python3 -u "$PX/m2_linux_boot.py" "$CACHE" panic=30 2>&1 | tee -a "$OUT/boot$n.log"
    say "boot $n session exit ${PIPESTATUS[0]}"
    sudo -n chown -R joshuawarren: "$CACHE" 2>/dev/null
    for _ in $(seq 1 120); do
        [ -e /dev/ttyACM0 ] || break
        sleep 0.5
    done
done
say "done after $MAX_BOOTS boots"
