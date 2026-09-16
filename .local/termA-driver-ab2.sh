#!/usr/bin/env bash
# TermA driver-mask refinement: default vs 1F0 vs 150 vs 140, 6 rounds.
set -euo pipefail
W=/var/tmp/TermASplit
export VK_DRIVER_FILES=/home/joshuawarren/src/mesa-wt-dispatchfloor/dispatchfloor-icd.json
MODEL=/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx
WHEEL=/var/tmp/V060-rel/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=$W/spirv
/var/tmp/V060PIN-venv2/bin/python /var/tmp/termA-driver-ab.py \
  --bench /var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py \
  --model "$MODEL" \
  --short-text "$(cat $W/prompt-short.txt)" \
  --ctx-text "$(cat $W/prompt-ctx1024.txt)" \
  --wheel "$WHEEL" \
  --arm default=DEFAULT --arm k1f0=1F0 --arm m150=150 --arm m140=140 \
  --rounds 6 --out $W/driver-ab2.json
