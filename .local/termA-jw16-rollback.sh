#!/usr/bin/env bash
# jw16 rollback: restore the hk6f6afc8-1 sink package (pre-assignment state),
# verify, restart the service.
set -uo pipefail
W=/var/tmp/TermAJW16
echo "== pause llm-inference =="
sudo -n systemctl stop llm-inference.service || exit 1
sleep 2
echo "== reinstall hk6f6afc8-1 =="
sudo -n pacman -U --noconfirm $W/mesa-honeykrisp-omarchy-26.3.0.devel.hk6f6afc8-1-aarch64.pkg.tar.xz 2>&1 | tail -1
pacman -Q mesa-honeykrisp-omarchy
echo "== quick control: ctx1024 leg digest+rate =="
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
MODEL=$(ls -d /home/joshuawarren/.cache/huggingface/hub/models--mlx-community--Qwen2.5-0.5B-Instruct-4bit/snapshots/*/ | head -1)
WHEEL=/var/tmp/TermAJW16/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
flock -w 900 /tmp/m1-gpu.lock timeout 300 /var/tmp/TermAJW16/venv/bin/python /var/tmp/decode-trio/scripts/bench_decode.py \
  --model "$MODEL" --prompt "$(cat $W/prompt-ctx1024.txt)" --tokens 32 --temp 0.0 \
  --seed 0 --warmup-tokens 4 --wheel "$WHEEL" 2>/dev/null | tail -1
echo "== restart llm-inference =="
sudo -n systemctl start llm-inference.service
sleep 3
systemctl is-active llm-inference.service
