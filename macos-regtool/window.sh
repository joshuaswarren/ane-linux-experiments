#!/bin/bash
# One macOS window: native ANE-start trace + working-state register dump.
# Run as root AFTER csrutil disable + Reduced Security (1TR visit done).
set -euo pipefail
OUT="${1:-$HOME/ane-mac-window-$(date +%Y%m%dT%H%M%S)}"
mkdir -p "$OUT"
echo "== log stream =="
log stream --style compact --predicate 'process == "kernel" AND (eventMessage CONTAINS "ANE" OR eventMessage CONTAINS "aned")' --info --debug > "$OUT/log-ane.log" 2>&1 &
LOGPID=$!
echo "== ioreg before =="
ioreg -l -w0 -r -n AppleH11ANEInterface > "$OUT/ioreg-before.txt" 2>&1 || true
ioreg -l -w0 -r -n AppleANELoadBalancer >> "$OUT/ioreg-before.txt" 2>&1 || true
echo "== powermetrics =="
timeout 30 powermetrics --samplers ane -i 1000 -n 25 > "$OUT/powermetrics-ane.txt" 2>&1 || true
echo "== dtrace (best effort; needs dev mode) =="
dtrace -n 'fbt::ANE_Init:entry { printf("ANE_Init pid=%d\n", pid); }' -o "$OUT/dtrace-aneinit.txt" 2>&1 || true &
DTPID=$!
echo "== register dump (firmware already started) =="
./ane_regdump -o "$OUT/regs" || echo "regdump rc=$? (see $OUT)"
kill $LOGPID $DTPID 2>/dev/null || true
echo "== ioreg after =="
ioreg -l -w0 -r -n AppleH11ANEInterface > "$OUT/ioreg-after.txt" 2>&1 || true
shasum -a 256 "$OUT"/* > "$OUT/SHA256SUMS" 2>/dev/null || true
echo "window done: $OUT"
