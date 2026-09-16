#!/usr/bin/env bash
# Quick check: fixup worktree driver, ctx1053/32 x3, print tps + digest.
set -uo pipefail
export VK_DRIVER_FILES=/home/joshuawarren/src/mesa-wt-dispatchfloor/dispatchfloor-icd.json
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/TermASplit/spirv
PY=/var/tmp/V060PIN-venv2/bin/python
B=/var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py
M=/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx
WW=/var/tmp/V060-rel/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
P=$(cat /var/tmp/TermASplit/prompt-ctx1024.txt)
for i in 1 2 3; do
  $PY $B --model "$M" --prompt "$P" --tokens 32 --temp 0.0 --seed 0 \
    --warmup-tokens 4 --wheel "$WW" 2>/dev/null | tail -1 | \
    python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["decode_tps"], d["ids_sha256_16"])'
done
