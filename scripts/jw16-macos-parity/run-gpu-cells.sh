#!/bin/bash
# jw16 (M1 Max) macOS GPU cells, paired with the 2026-09-28 Linux sweep:
#   decode 64/128/256/512 tok: --limit 1 --warmup 1 --passes 5 (one process each)
#   prefill 512/1024/2048 tok: 5 separate processes, --new-tokens 32 --passes 1
# Same bench script as jw16 Linux (max_tokens=new_tokens fix), same corpus/model pins.
# usage (on jw16 macOS): bash run-gpu-cells.sh OUTDIR   (dir holds bench + model-0867d98b + prompts)
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:?outdir}"; mkdir -p "$OUT"
MODEL="$HERE/model-0867d98b"
echo "9299a3b2fc136a4c0c355f9ad3e211be81823a5fb9eeadbc2e6608fb3e5718a0  $HERE/qwen38-2b-prompts.jsonl" | shasum -a 256 -c - || exit 1
echo "b0d5de688567bf4acd5e421027acd410dabcdc255a5bd46fdbf06c75dc2e6863  $MODEL/model.safetensors" | shasum -a 256 -c - || exit 1
grep -q 'max_tokens=a.new_tokens' "$HERE/qwen38-mlx-bench.py" || { echo "bench lacks max_tokens fix"; exit 1; }
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v $c >/dev/null && [ "$($c -c 'import sys;print(sys.version_info>=(3,10))')" = True ]; then PY=$c; break; fi
done
[ -n "$PY" ] || { echo "no python>=3.10"; exit 1; }
VENV="$HERE/venv-gpu"
[ -d "$VENV" ] || $PY -m venv "$VENV"
"$VENV/bin/pip" install -q "mlx==0.32.2" "mlx-lm==0.31.3" numpy 2>&1 | tail -2
"$VENV/bin/pip" list 2>/dev/null | grep -Ei '^(mlx|mlx-lm|numpy) ' | tee "$OUT/pip.txt"
{ date -u; sw_vers; sysctl -n machdep.cpu.brand_string hw.model kern.osversion kern.boottime; pmset -g batt; pmset -g; pmset -g therm; } > "$OUT/env.txt" 2>&1
sudo -n powermetrics --samplers thermal,gpu_power -i 5000 > "$OUT/powermetrics.txt" 2>&1 &
PM=$!
caffeinate -dimsu -w $$ &
B() { "$VENV/bin/python" "$HERE/qwen38-mlx-bench.py" --model "$MODEL" --prompts "$HERE/qwen38-2b-prompts.jsonl" --limit 1 "$@"; }
for N in 64 128 256 512; do
  echo "--- decode $N $(date -u +%FT%TZ)"; pmset -g therm | tail -3
  B --new-tokens $N --warmup 1 --passes 5 --prefill-tokens 512 --label macos-d$N-n5 --out "$OUT/qwen-gpu-d$N-n5.json" > "$OUT/d$N.log" 2>&1 || echo "d$N FAILED"
done
for P in 512 1024 2048; do
  for i in 1 2 3 4 5; do
    echo "--- prefill $P run $i $(date -u +%FT%TZ)"
    B --new-tokens 32 --warmup 1 --passes 1 --prefill-tokens $P --label macos-pf$P-$i --out "$OUT/qwen-gpu-pf$P-$i.json" > "$OUT/pf$P-$i.log" 2>&1 || echo "pf$P-$i FAILED"
  done
done
pmset -g therm >> "$OUT/env.txt"
sudo -n kill $PM 2>/dev/null
( cd "$OUT" && shasum -a 256 *.json *.log *.txt > SHA256SUMS )
echo GPU-CELLS-DONE
