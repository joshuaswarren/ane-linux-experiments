#!/bin/bash
# jw16 window-5 pre-flight (run on omp-studio-local before blessing macOS). Read-only checks.
# usage: bash window5-preflight.sh
set -u
J=ssh jw16mbp1-linux
FAIL=0
chk() { # $1 desc $2 want $3 got
  if [ "$2" = "$3" ]; then echo "OK   $1: $3"; else echo "FAIL $1: got '$3' want '$2'"; FAIL=1; fi
}
echo "== jw16 Linux pre-flight $(date -u +%FT%TZ)"
chk "llm-inference active" "active" "$($J 'systemctl is-active llm-inference')"
$J 'cat /proc/sys/kernel/random/boot_id; uname -r'
chk "gpuwin procs" "0" "$($J 'pgrep -fc "[g]pu[w]in.sh|[r]un-linux-cells" || true')"
echo "lock: $($J 'ls -la /tmp/m1-gpu.lock /tmp/gpuwin.mutex 2>&1; fuser /tmp/m1-gpu.lock 2>&1 || true')"
chk "ane module srcversion" "9109B200A150B27F484F718" "$($J 'cat /sys/module/ane/parameters/srcversion 2>/dev/null || modinfo -F srcversion ane 2>/dev/null')"
$J 'modinfo -F srcversion ane 2>/dev/null; sha256sum /boot/efi/m1n1/boot.bin; grub-install --version | head -1; df -h / | tail -1'
echo "stage pin:"
shasum -a 256 ~/stage/jw16-macos-w5/* 2>/dev/null
exit $FAIL
