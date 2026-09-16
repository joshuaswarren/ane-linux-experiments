#!/usr/bin/env bash
# TermA leg P2: long decode under perf for decode-phase statistical power.
# 2048 decode tokens at ~103 tok/s ≈ 20 s of decode; -F 4000 dwarf.
set -euo pipefail
W=/var/tmp/TermASplit
PY=/var/tmp/V060PIN-venv2/bin/python
BENCH=/var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py
MODEL=/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx
WHEEL=/var/tmp/V060-rel/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/TermASplit/spirv
P_CTX=$(cat $W/prompt-ctx1024.txt)
perf record -F 4000 --call-graph dwarf,16384 -o "$W/perf-long.data" \
  -- "$PY" "$BENCH" --model "$MODEL" --prompt "$P_CTX" --tokens 2048 \
  --temp 0.0 --seed 0 --warmup-tokens 4 --wheel "$WHEEL" \
  > "$W/perf-long.json" 2> "$W/perf-long.err"
tail -1 "$W/perf-long.json"
perf report --stdio --no-children --percent-limit 0.15 -i "$W/perf-long.data" \
  > "$W/perf-long.report.txt" 2>/dev/null
perf report --stdio --no-children --percent-limit 0.05 --dsos libvulkan_asahi.so -i "$W/perf-long.data" \
  > "$W/perf-long.drv.txt" 2>/dev/null || true
perf report --stdio --no-children --percent-limit 0.05 --dsos libmlx.so -i "$W/perf-long.data" \
  > "$W/perf-long.mlx.txt" 2>/dev/null || true
echo "== driver top =="
grep -E "^\s+[0-9]+\.[0-9]+%" "$W/perf-long.drv.txt" | head -15
echo "== mlx top =="
grep -E "^\s+[0-9]+\.[0-9]+%" "$W/perf-long.mlx.txt" | head -15
echo "== overall top 15 =="
grep -E "^\s+[0-9]+\.[0-9]+%" "$W/perf-long.report.txt" | head -15
