#!/bin/bash
# prefill A/B across two venvs: ctl (installed) vs cand (main-wheel venv), interleaved per sample.
# usage: abpm.sh <outdir> <prefill_tokens> <pairs>
set -u
O=$1; PF=$2; N=$3; mkdir -p "$O"
B=$HOME/src/ane-linux-experiments/benchmarks
CTL=$HOME/.local/share/mlx-omarchy/venv/bin/python
CAND=/var/tmp/jwm1-main-venv/bin/python
M=$HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/0867d98bfb174b042d88461c0e7c97b86b34b381
cd "$B" || exit 2
exec 9>/tmp/m1-gpu.lock
flock -w 300 9 || { echo LOCK-TIMEOUT; exit 3; }
for i in $(seq 1 "$N"); do
  for arm in ctl cand; do
    if [ "$arm" = cand ]; then PY=$CAND; else PY=$CTL; fi
    echo "pair $i arm $arm load $(cut -d' ' -f1-3 /proc/loadavg) thermal $(cat /sys/class/thermal/thermal_zone0/temp) start $(date -u +%FT%TZ)"
    "$PY" qwen38-mlx-bench.py --model "$M" --prompts qwen38-2b-prompts.jsonl --limit 1 --new-tokens 1 \
      --prefill-tokens "$PF" --warmup 2 --passes 1 --label "h16-$arm-$i" --out "$O/$arm-$i.json" > "$O/$arm-$i.log" 2>&1
    echo "rc=$?"
  done
done
flock -u 9
echo AB-DONE
