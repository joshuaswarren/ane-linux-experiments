#!/usr/bin/env bash
# Pre-flight: verify jwm1 is safe to use before any GPU/ANE/Vulkan work.
# Run as the first command when the box is mine. CPU-only, read-only.
set -euo pipefail
echo "=== jwm1 GPU parity pre-flight ==="
echo "host: $(hostname)"
echo "uptime: $(uptime -p)"
echo "loadavg: $(cat /proc/loadavg)"
echo "date:   $(date -Is)"
echo
echo "--- M2 proxy hard rule ---"
echo "Reminder: coordinate with M2FwStart-2 BEFORE any jwm1 reboot/USB/ACM/hang action."
echo "Reminder: NO service to stop/start on jwm1 (no llm-inference.service unit exists)."
echo
echo "--- Vulkan ICD ---"
ls -la /usr/share/vulkan/icd.d/asahi_icd.json
sha256sum /usr/local/lib/libvulkan_asahi.so.7faf04c 2>/dev/null
echo
echo "--- GPU render node + lock ---"
ls -la /dev/dri/renderD128 /dev/accel/accel0 2>/dev/null
ls -la /tmp/m1-gpu.lock 2>&1 | head -1
fuser -v /dev/dri/renderD128 /dev/accel/accel0 2>&1 | head -10
echo
echo "--- ane.ko ---"
lsmod | grep -E "^ane\b" | head
echo
echo "--- mlx-omarchy installed ---"
for v in v072-venv-fused denom-b4757ac-venv; do
  L=/var/tmp/$v/lib/python3.14/site-packages/mlx/lib/libmlx.so
  [ -e "$L" ] && echo "$(sha256sum $L | cut -c1-16) $v libmlx.so"
done
/var/tmp/v072-venv-fused/bin/pip show mlx-omarchy 2>/dev/null | grep -E "^(Name|Version)" | head
echo
echo "--- model snapshot ---"
ls -d $HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/
echo
echo "--- worktrees ---"
cd ~/q38-build/mlx-omarchy && git worktree list | head -10
echo
cd /var/tmp/jwm1-gpu-parity-wt && git log --oneline -2
echo
echo "=== end pre-flight ==="
