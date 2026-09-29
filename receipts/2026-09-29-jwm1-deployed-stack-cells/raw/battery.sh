#!/bin/bash
# H16 battery: installed venv (ctl) vs main-wheel venv (cand). Each phase waits for load(1m) < 0.4 first.
set -u
waitload() {
  for t in $(seq 1 90); do
    L=$(cut -d' ' -f1 /proc/loadavg)
    if awk -v l="$L" 'BEGIN{exit !(l<0.4)}'; then break; fi
    sleep 5
  done
  echo "phase $1 loadwait done load=$(cut -d' ' -f1-3 /proc/loadavg) $(date -u +%FT%TZ)"
}
waitload decode64;  bash /tmp/h1/ab2m.sh /var/tmp/h16-d64 64 0 3
waitload decode128; bash /tmp/h1/ab2m.sh /var/tmp/h16-d128 128 0 2
waitload prefill512;  bash /tmp/h1/abpm.sh /var/tmp/h16-pf512 512 15
waitload prefill1024; bash /tmp/h1/abpm.sh /var/tmp/h16-pf1024 1024 5
waitload prefill2048; bash /tmp/h1/abpm.sh /var/tmp/h16-pf2048 2048 5
waitload parakeet;    bash /tmp/h1/abpkm.sh
echo BATTERY-DONE
