#!/usr/bin/env bash
# TermA profiled decode run with the diagnostics wheel (GPU profiling in).
# One locked run: ctx1053/32 pinned protocol, profile to NDJSON.
set -euo pipefail
W=/var/tmp/TermASplit
PY=/var/tmp/termA-diag-venv/bin/python
BENCH=/var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py
MODEL=/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx
WHEEL=$(ls /var/tmp/termA-diag/dist/mlx_omarchy-*aarch64.whl | head -1)
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_GPU_PROFILE=/var/tmp/TermASplit/profile.jsonl
export MLX_OMARCHY_GPU_PROFILE_LABEL=termA-ctx1053
P_CTX=$(cat $W/prompt-ctx1024.txt)
"$PY" "$BENCH" --model "$MODEL" --prompt "$P_CTX" --tokens 32 --temp 0.0 \
  --seed 0 --warmup-tokens 4 --wheel "$WHEEL" \
  > "$W/prof.json" 2> "$W/prof.err"
tail -2 "$W/prof.json"
ls -la "$W/profile.jsonl"
