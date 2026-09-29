#!/bin/bash
# usage: mac_run.sh <outdir>
set -u
O="$1"; mkdir -p "$O"
PY="$HOME/bench-qwen38-venv/bin/python"
M="$HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/0867d98bfb174b042d88461c0e7c97b86b34b381"
P="$HOME/mac-reference-bundle/qwen38-2b-prompts.jsonl"
S="$HOME/h1-micro"
{
  date -u +%FT%TZ
  sw_vers
  pmset -g therm
  uptime
  "$PY" --version
  "$PY" -m pip list 2>/dev/null | grep -i -E "^mlx|numpy"
  shasum -a 256 "$P" | cut -c1-16
} > "$O/identity.txt" 2>&1
for t in $(seq 1 40); do
  L=$(uptime | sed 's/.*load averages*: //' | cut -d' ' -f1 | tr -d ,)
  if awk -v l="$L" 'BEGIN{exit !(l<0.5)}'; then break; fi
  sleep 5
done
echo "load at start: $(uptime)" >> "$O/identity.txt"
caffeinate -dimsu bash "$S/mac_micro.sh" "$PY" "$M" "$P" "$O" "$S"
