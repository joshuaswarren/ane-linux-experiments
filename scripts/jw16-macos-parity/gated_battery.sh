#!/bin/bash
# Interleaved control/candidate battery of the full contract (10 prompts, warmup 3, 10 passes, greedy, 32 tokens,
# prefill 512). Each run in its own gpuwin window. usage: gated_battery.sh PAIRS [CAND_ENV]
set -u
PAIRS="${1:?pairs}"; CAND="${2:-MLX_OMARCHY_GATED_BARRIERS=1}"
PY=/var/tmp/v072-venv-fused/bin/python3
MODEL=$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/0867d98bfb174b042d88461c0e*)
OUT=/var/tmp/jw16-parity/gated-battery; mkdir -p "$OUT"
one () { # arm env
  local arm="$1" env="$2" i="$3"
  bash /var/tmp/appbar/gpuwin.sh "env $env $PY $HOME/bench-scripts/qwen38-mlx-bench.py --model $MODEL/ --prompts $HOME/bench-scripts/qwen38-2b-prompts.jsonl --limit 10 --new-tokens 32 --warmup 3 --passes 10 --prefill-tokens 512 --label gb-$arm-$i --out $OUT/gb-$arm-$i.json" > "$OUT/gb-$arm-$i.log" 2>&1
  $PY -c "
import json;d=json.load(open('$OUT/gb-$arm-$i.json'));print('$arm',$i,d['decode_tok_rate']['median'],d['ordered_records_sha256'][:12])" 2>&1 | grep -v rtmod
  grep RESTORE "$OUT/gb-$arm-$i.log" | tail -1
}
for i in $(seq 1 "$PAIRS"); do
  if [ $((i % 2)) -eq 1 ]; then one ctl "X=1" "$i"; one cand "$CAND" "$i"; else one cand "$CAND" "$i"; one ctl "X=1" "$i"; fi
done
