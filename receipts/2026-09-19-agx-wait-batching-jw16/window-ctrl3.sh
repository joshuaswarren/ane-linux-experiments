#!/usr/bin/env bash
# Control 3: 5deac1c8068 rebuilt TODAY (pkg-s5de) — same 3 short runs.
# ~140 => toolchain drift; ~190 => source regression merged into trunk.
exec > /var/tmp/cb/window-ctrl3.log 2>&1
set -uo pipefail
L=/var/tmp/cb
cleanup() {
  sudo -n systemctl start llm-inference.service
  sleep 3
  echo "post: $(systemctl is-active llm-inference.service)"
}
trap cleanup EXIT
sudo -n systemctl stop llm-inference.service || exit 1
sleep 2
echo "pre: $(systemctl is-active llm-inference.service)"
exec 9>/tmp/m1-gpu.lock
flock -w 900 9 || { echo FLOCK-FAIL; exit 5; }
ls -i /tmp/m1-gpu.lock
date -u +%FT%TZ
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=$L/spirv
export MLX_OMARCHY_EXPECTED_LIBMLX_SHA256=df3d4e74c597956c
PY=/var/tmp/v071perf-venv/bin/python
B=$L/scripts/bench_decode.py
MODEL=/var/tmp/jw16gap-model
export VK_DRIVER_FILES=/var/tmp/MesaL2/pkg-s5de/icd.json
for i in 1 2 3; do
  $PY $B --model "$MODEL" --prompt "Hi" --tokens 32 \
    --temp 0.0 --seed 0 --warmup-tokens 4 2>&1 | grep -E "^decode|generated_ids"
done
unset VK_DRIVER_FILES
