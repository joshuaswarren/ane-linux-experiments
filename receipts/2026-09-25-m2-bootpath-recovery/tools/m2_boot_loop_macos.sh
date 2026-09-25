#!/bin/bash
# jwm1 macOS catcher. Each time the M2's 43ec stage-1 proxy appears as
# /dev/cu.usbmodem*, clear any foreign holder and run one unbroken proxy
# session (m2_linux_boot.py) that chainloads the M2's own Linux kernel,
# bypassing the hanging U-Boot. panic=30 makes a panicking kernel reboot
# into the next catch; at most MAX_BOOTS chainloads per arming.
# DRYRUN=1: check imports and device detection, then exit.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
CACHE=$HERE/m2boot
MAX_BOOTS=${MAX_BOOTS:-3}
OUT=$HERE/logs/bootloop-$(date -u +%Y%m%dT%H%M%S)
mkdir -p "$OUT"
LOG=$OUT/loop.log
say() { echo "$(date -u +%T) $*" | tee -a "$LOG"; }
proxy_dev() { ls /dev/cu.usbmodem* 2>/dev/null | sort | head -n 1; }
run() { perl -e 'alarm shift; exec @ARGV' "$@"; }
export PYTHONPATH="$HERE/pylib:$HERE/proxyclient:$HERE"
if [ "${DRYRUN:-0}" = 1 ]; then
    say "dry run: python $(python3 --version 2>&1)"
    python3 -c "import serial, construct, m1n1.proxy, m1n1.utils; print('imports ok')" 2>&1 \
        | tee -a "$LOG"
    say "proxy device now: '$(proxy_dev)'"
    exit 0
fi
say "armed: up to $MAX_BOOTS chainloads, cache $CACHE"
for n in $(seq 1 "$MAX_BOOTS"); do
    say "boot $n: waiting for /dev/cu.usbmodem* (up to 8 h)"
    DEV=""
    for _ in $(seq 1 57600); do
        DEV=$(proxy_dev)
        [ -n "$DEV" ] && break
        sleep 0.5
    done
    [ -n "$DEV" ] || { say "no proxy device"; exit 1; }
    say "proxy device $DEV: $(ls /dev/cu.usbmodem* | tr '\n' ' ')"
    for pid in $(lsof -t /dev/cu.usbmodem* 2>/dev/null); do
        say "foreign holder $pid: $(ps -o command= -p "$pid")"
        kill "$pid"
    done
    (cd "$HERE/proxyclient" && M1N1DEVICE="$DEV" run 900 python3 -u "$HERE/m2_linux_boot.py" \
        "$CACHE" panic=30) 2>&1 | tee -a "$OUT/boot$n.log"
    say "boot $n session exit ${PIPESTATUS[0]}"
    for _ in $(seq 1 120); do
        [ -z "$(proxy_dev)" ] && break
        sleep 0.5
    done
done
say "done after $MAX_BOOTS boots"
