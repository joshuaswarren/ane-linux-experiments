#!/bin/bash
# H33: MLX_OMARCHY_GATED_BARRIERS digest gate on the live jwm1 venv. Arms interleaved per sample, one lock hold.
# arms: a=live default (both unset), b=GATED_BARRIERS=1, c=GATED_BARRIERS=1 + HK_SUBMIT_POLL_US=2000 (future main defaults)
# usage: gate3.sh <outdir> <newtokens> <prefill_tokens> <limit> <rounds>
set -u
O=$1; NT=$2; PF=$3; LIM=$4; R=$5; mkdir -p "$O"
B=$HOME/src/ane-linux-experiments/benchmarks
PY=$HOME/.local/share/mlx-omarchy/venv/bin/python
M=$(ls -d $HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*)
cd "$B" || exit 2
for t in $(seq 1 60); do
  L=$(cut -d' ' -f1 /proc/loadavg)
  if awk -v l="$L" 'BEGIN{exit !(l<0.4)}'; then break; fi
  sleep 5
done
exec 9>/tmp/m1-gpu.lock
flock -w 600 9 || { echo LOCK-TIMEOUT; exit 3; }
for r in $(seq 1 "$R"); do
  for arm in a b c; do
    unset MLX_OMARCHY_GATED_BARRIERS HK_SUBMIT_POLL_US
    case $arm in
      b) export MLX_OMARCHY_GATED_BARRIERS=1 ;;
      c) export MLX_OMARCHY_GATED_BARRIERS=1 HK_SUBMIT_POLL_US=2000 ;;
    esac
    echo "round $r arm $arm load $(cut -d' ' -f1-3 /proc/loadavg) $(date -u +%T)"
    "$PY" qwen38-mlx-bench.py --model "$M" --prompts qwen38-2b-prompts.jsonl --limit "$LIM" --new-tokens "$NT" \
      --prefill-tokens "$PF" --warmup 2 --passes 1 --label "h33-$arm-r$r" --out "$O/$arm-r$r.json" > "$O/$arm-r$r.log" 2>&1
    echo "rc=$?"
  done
done
flock -u 9
echo GATE-DONE
