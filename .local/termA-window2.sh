#!/usr/bin/env bash
# TermA attribution window 2 (2026-09-16): fixed prompt texts + long decode
# legs so perf samples land on the decode phase. One lock hold.
#   leg1  perf ctx1053, --tokens 224  (decode dominates the process)
#   leg2  perf short,    --tokens 224
#   leg3  control 32-token runs on both prompts, digests printed (no perf)
# Reports: top symbols overall + dso-filtered (libmlx.so, libvulkan*, gallium).
set -euo pipefail
W=/var/tmp/TermASplit
PY=/var/tmp/V060PIN-venv2/bin/python
BENCH=/var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py
MODEL=/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx
WHEEL=/var/tmp/V060-rel/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
mkdir -p $W
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/TermASplit/spirv

say() { echo "[termA] $*"; }
P_CTX=$(cat $W/prompt-ctx1024.txt)
P_SHORT=$(cat $W/prompt-short.txt)

run_leg() { # $1 name $2 prompt-text $3 tokens
  "$PY" "$BENCH" --model "$MODEL" --prompt "$2" --tokens "$3" --temp 0.0 \
    --seed 0 --warmup-tokens 4 --wheel "$WHEEL" \
    > "$W/$1.json" 2> "$W/$1.err"
  tail -1 "$W/$1.json"
}

case "${1:-all}" in
perf|all)
  say "leg3 controls (32 tokens, no sampler)"
  run_leg ctrl-short "$P_SHORT" 32
  run_leg ctrl-ctx1024 "$P_CTX" 32

  say "leg1 perf ctx1053 x224"
  perf record -F 1499 -o "$W/perf-ctx1024.data" \
    -- "$PY" "$BENCH" --model "$MODEL" --prompt "$P_CTX" --tokens 224 \
    --temp 0.0 --seed 0 --warmup-tokens 4 --wheel "$WHEEL" \
    > "$W/perf-ctx1024.json" 2> "$W/perf-ctx1024.err"

  say "leg2 perf short x224"
  perf record -F 1499 -o "$W/perf-short.data" \
    -- "$PY" "$BENCH" --model "$MODEL" --prompt "$P_SHORT" --tokens 224 \
    --temp 0.0 --seed 0 --warmup-tokens 4 --wheel "$WHEEL" \
    > "$W/perf-short.json" 2> "$W/perf-short.err"

  for d in perf-ctx1024 perf-short; do
    say "report $d (all dso)"
    perf report --stdio --no-children --percent-limit 0.4 \
      -i "$W/$d.data" > "$W/$d.report.txt" 2>/dev/null || true
    say "report $d (driver + mlx dso only)"
    perf report --stdio --no-children --percent-limit 0.02 \
      -i "$W/$d.data" -c python 2>/dev/null \
      | awk '/libvulkan|vulkan_asahi|libgallium|libmlx|libagx|vertex|asahi/ {show=1} show' \
      > "$W/$d.drv.txt" || true
    grep -E "^(#[0-9]|.*%[[:space:]]+python.*(libvulkan|asahi|gallium|libmlx|libagx))" "$W/$d.drv.txt" | head -30 || true
    tail -1 "$W/$d.json"
  done
  ;;
*) echo "usage: $0 [perf|all]"; exit 2;;
esac
say "done"
