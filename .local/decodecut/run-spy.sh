#!/usr/bin/env bash
set -u
exec 9>/tmp/m1-gpu.lock
flock -w 900 9 || exit 1
/var/tmp/decodecut-venv/bin/python /var/tmp/decodecut/spy_dtypes.py > /var/tmp/decodecut/spy.out 2>&1
grep -v rtmod /var/tmp/decodecut/spy.out | grep -E "raw call|q:|k:|v:|a:|b:|A_log|dt:|state:|mask|calls|exc"
