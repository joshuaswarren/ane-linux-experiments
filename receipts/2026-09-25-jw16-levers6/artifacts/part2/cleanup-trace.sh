#!/bin/bash
# cleanup-trace.sh — reset ftrace state, kill stray relay, shut resident daemon.
set -u
sudo -n sh -c '
T=/sys/kernel/tracing
echo 0 > $T/tracing_on
echo 0 > $T/events/gpu_scheduler/enable
echo 0 > $T/events/dma_fence/enable
'
sudo -n kill "$(cat /tmp/part2-catpid 2>/dev/null)" 2>/dev/null || true
rm -f /tmp/part2-marks /tmp/part2-catpid
/var/tmp/v072-venv-fused/bin/python3 /var/tmp/parakeet-recover/ane_whole_worker_resident.py --shutdown || true
echo cleanup-done
