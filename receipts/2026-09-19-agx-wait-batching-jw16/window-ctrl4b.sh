#!/usr/bin/env bash
# Control 4 (queued variant): flock FIRST, then gate the service. Safe to
# launch while another holder is inside the window.
# base arm (d8d4e1c500 rebuilt) WITH AGX_SIMDMAT=1.
# ~191 => regression is the f4859fb6991 opt-in flip; ~141 => hypothesis dead.
exec > /var/tmp/cb/window-ctrl4.log 2>&1
set -uo pipefail
L=/var/tmp/cb
exec 9>/tmp/m1-gpu.lock
flock -w 1800 9 || { echo FLOCK-FAIL; exit 5; }
cleanup() {
  sudo -n systemctl start llm-inference.service
  sleep 3
  echo "post: $(systemctl is-active llm-inference.service)"
}
trap cleanup EXIT
echo "== lock acquired $(date -u +%FT%TZ), inode: $(ls -i /tmp/m1-gpu.lock) =="
sudo -n systemctl stop llm-inference.service || exit 1
sleep 2
echo "pre: $(systemctl is-active llm-inference.service)"
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=$L/spirv
export MLX_OMARCHY_EXPECTED_LIBMLX_SHA256=df3d4e74c597956c
PY=/var/tmp/v071perf-venv/bin/python
B=$L/scripts/bench_decode.py
MODEL=/var/tmp/jw16gap-model
export VK_DRIVER_FILES=/var/tmp/MesaL2/pkg-base/icd.json
export AGX_SIMDMAT=1
for i in 1 2 3; do
  $PY $B --model "$MODEL" --prompt "Hi" --tokens 32 \
    --temp 0.0 --seed 0 --warmup-tokens 4 2>&1 | grep -E "^decode|generated_ids"
done
unset VK_DRIVER_FILES AGX_SIMDMAT
