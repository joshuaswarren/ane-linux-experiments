#!/usr/bin/env bash
# m1-host decode-profile window. Holds ONE flock inode for all measurements.
set -euo pipefail
VP=/var/tmp/vprof
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)"
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
mkdir -p "$VP/out"
exec 9>/tmp/m1-gpu.lock
flock 9
echo "lock held $(date -Is)"
V="$VP/venv-diag2"

echo "== bandwidth roofline =="
"$V/bin/python" "$VP/bw_roofline.py" 2>&1 | tee "$VP/out/bw.txt"

echo "== decode profile (prompt 0) =="
MLX_DISABLE_COMPILE=1 MLX_OMARCHY_GPU_PROFILE="$VP/out/prof-p0.jsonl" \
  MLX_OMARCHY_GPU_PROFILE_LABEL=p0 \
  "$V/bin/python" "$VP/prof_decode.py" --model "$MODEL" --prompts "$PROMPTS" \
  --prompt-idx 0 --new-tokens 32 --markers "$VP/out/markers-p0.jsonl" \
  2>&1 | tee "$VP/out/prof-p0.txt"

echo "== decode profile (prompt 5, control) =="
MLX_DISABLE_COMPILE=1 MLX_OMARCHY_GPU_PROFILE="$VP/out/prof-p5.jsonl" \
  MLX_OMARCHY_GPU_PROFILE_LABEL=p5 \
  "$V/bin/python" "$VP/prof_decode.py" --model "$MODEL" --prompts "$PROMPTS" \
  --prompt-idx 5 --new-tokens 32 --markers "$VP/out/markers-p5.jsonl" \
  2>&1 | tee "$VP/out/prof-p5.txt"
echo "lock released $(date -Is)"
