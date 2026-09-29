#!/bin/bash
# H14: Parakeet product-path driver, installed venv (ctl, no soundfile) vs /var/tmp/jwm1-main-venv (cand, soundfile), interleaved blocks.
set -u
O=/var/tmp/h16pk; mkdir -p $O
for t in $(seq 1 60); do
  L=$(cut -d' ' -f1 /proc/loadavg)
  if awk -v l="$L" 'BEGIN{exit !(l<0.4)}'; then break; fi
  sleep 5
done
echo "loadwait done load=$(cut -d' ' -f1-3 /proc/loadavg)"
exec 9>/tmp/m1-gpu.lock
flock -w 300 9 || { echo LOCK-TIMEOUT; exit 3; }
for blk in 1 2; do
  for arm in ctl cand; do
    if [ "$arm" = cand ]; then V=/var/tmp/jwm1-main-venv; else V=$HOME/.local/share/mlx-omarchy/venv; fi
    echo "block $blk arm $arm venv $V load $(cut -d' ' -f1-3 /proc/loadavg) start $(date -u +%FT%TZ)"
    (cd /tmp/h1 && timeout 400 "$V/bin/python" /var/tmp/pk-sess-driver.py --venv "$V" --out-root "$O/$arm-$blk" --runs 6 --label "h16-$arm-$blk" > "$O/$arm-$blk.log" 2>&1)
    echo "rc=$?"
  done
done
flock -u 9
echo AB-DONE
