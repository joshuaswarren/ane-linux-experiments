#!/usr/bin/env bash
set -u
exec 9>/tmp/m1-gpu.lock
flock -w 900 9 || exit 1
export GDN_FALLBACK_DEBUG=1
export MLX_DISABLE_COMPILE=1
/var/tmp/decodecut-venv/bin/python /var/tmp/decodecut/spy_dtypes.py > /var/tmp/decodecut/spy2.out 2>&1
echo "fallback lines: $(grep -c GDN-FALLBACK /var/tmp/decodecut/spy2.out)"
grep GDN-FALLBACK /var/tmp/decodecut/spy2.out | head -3
grep -E "raw calls" /var/tmp/decodecut/spy2.out
