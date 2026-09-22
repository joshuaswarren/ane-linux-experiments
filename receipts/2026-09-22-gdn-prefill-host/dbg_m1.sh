#!/usr/bin/env bash
set -u
exec 9>/tmp/m1-gpu.lock
flock -w 600 9 || { echo "lock timeout" >&2; exit 1; }
export GDN_FALLBACK_DEBUG=1 MLX_OMARCHY_TRACE_DISPATCH=1
/var/tmp/bf16-prefill-venv/bin/python /var/tmp/profile_prefill.py /var/tmp/prompt512.txt 2>&1 | grep -m6 "GDN-FALLBACK\|PREFILL\|gated_delta_fallback"
echo DBG-DONE
