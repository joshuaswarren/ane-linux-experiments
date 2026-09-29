#!/bin/bash
# H3 A/B: installed venv (ctl) vs patched venv copy (cand), interleaved, one lock hold.
# usage: ab2.sh <outdir> <newtokens> <prefill_tokens> <rounds>
set -u
O=$1; NT=$2; PF=$3; R=$4; mkdir -p "$O"
B=$HOME/src/ane-linux-experiments/benchmarks
CTL=$HOME/.local/share/mlx-omarchy/venv/bin/python
CAND=/var/tmp/jwm1-main-venv/bin/python
M=$HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/0867d98bfb174b042d88461c0e7c97b86b34b381
cd "$B" || exit 2
exec 9>/tmp/m1-gpu.lock
flock -w 180 9 || { echo LOCK-TIMEOUT; exit 3; }
for r in $(seq 1 "$R"); do
  for arm in ctl cand; do
    if [ "$arm" = cand ]; then PY=$CAND; else PY=$CTL; fi
    echo "round $r arm $arm py $PY load $(cut -d' ' -f1-3 /proc/loadavg) thermal $(cat /sys/class/thermal/thermal_zone0/temp) start $(date -u +%FT%TZ)"
    "$PY" qwen38-mlx-bench.py --model "$M" --prompts qwen38-2b-prompts.jsonl --limit 5 --new-tokens "$NT" \
      --prefill-tokens "$PF" --warmup 2 --passes 1 --label "h3-$arm-r$r" --out "$O/$arm-r$r.json" > "$O/$arm-r$r.log" 2>&1
    echo "rc=$?"
  done
done
flock -u 9
echo AB-DONE
