#!/usr/bin/env bash
# TermA attribution window (2026-09-16): where does the ~10 us/dispatch
# decode cost live, instrumented. Three legs, one lock hold.
#   leg1: perf CPU profile, ctx1024/32 decode, release v0.6.0 wheel
#         (201 dispatches/token) -> names host functions inside the
#         submit path if the host is the pacer.
#   leg2: perf CPU profile, short 30/32 leg -> same attribution with
#         term B (KV stream) priced out.
#   leg3: no-sampling control run of both legs (perf off) for the wall
#         the samples are normalized against + digest pins.
# Everything under ONE flock hold on /tmp/m1-gpu.lock; never unlinked.
set -euo pipefail
W=/var/tmp/TermASplit
PY=/var/tmp/V060PIN-venv2/bin/python
BENCH=/var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py
MODEL=/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx
WHEEL=/var/tmp/V060-rel/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
mkdir -p $W
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/TermASplit/spirv

run_leg() { # $1 name  $2 prompt
  echo "== leg $1 =="
  "$PY" "$BENCH" --model "$MODEL" --prompt "$2" --tokens 32 --temp 0.0 \
    --seed 0 --warmup-tokens 4 --wheel "$WHEEL" \
    > "$W/$1.json" 2> "$W/$1.err"
  grep -E '"decode_tok_s"|"digest"|provenance' "$W/$1.json" | tail -3 || true
}

say() { echo "[termA] $*"; }
say "boot_id=$(cat /proc/sys/kernel/random/boot_id)"
say "wheel=$(basename "$WHEEL")"

case "${1:-all}" in
perf|all)
  say "leg3 control first (no sampler)"
  run_leg ctrl-ctx1024 ctx1024
  run_leg ctrl-short short

  say "leg1 perf ctx1024"
  perf record -F 1499 --call-graph dwarf,16384 -o "$W/perf-ctx1024.data" \
    -- "$PY" "$BENCH" --model "$MODEL" --prompt ctx1024 --tokens 32 \
    --temp 0.0 --seed 0 --warmup-tokens 4 --wheel "$WHEEL" \
    > "$W/perf-ctx1024.json" 2> "$W/perf-ctx1024.err"

  say "leg2 perf short"
  perf record -F 1499 --call-graph dwarf,16384 -o "$W/perf-short.data" \
    -- "$PY" "$BENCH" --model "$MODEL" --prompt short --tokens 32 \
    --temp 0.0 --seed 0 --warmup-tokens 4 --wheel "$WHEEL" \
    > "$W/perf-short.json" 2> "$W/perf-short.err"

  for d in perf-ctx1024 perf-short; do
    say "report $d"
    perf report --stdio --no-children -g none --percent-limit 0.3 \
      -i "$W/$d.data" > "$W/$d.report.txt" 2>/dev/null
    perf report --stdio --stdio-color never --percent-limit 0.3 \
      -i "$W/$d.data" -g fractal,5,caller > "$W/$d.callers.txt" 2>/dev/null || true
    awk '/^# Overlord|^# Overhead|^[[:space:]]*[0-9]+\.[0-9]+%/' "$W/$d.report.txt" | head -40
  done
  ;;
*) echo "usage: $0 [perf|all]"; exit 2;;
esac
say "done"
