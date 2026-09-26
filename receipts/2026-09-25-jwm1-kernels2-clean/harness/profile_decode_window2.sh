#!/usr/bin/env bash
# Decode + prefill per-dispatch profile window on the installed-contract shape.
# Uses a dedicated profiling venv; the gate venv stays release.
# Usage: profile_decode_window2.sh <tag> [limit] [passes]
set -uo pipefail
TAG=${1:?tag}
LIMIT=${2:-1}
PASSES=${3:-1}
OUT=/tmp/prof-windows
STAMP=$(date +%H%M%S)
mkdir -p "$OUT"
PY=/var/tmp/prof-venv2/bin/python
echo "== lock $TAG $STAMP =="
exec 9>/tmp/m1-gpu.lock
flock -w 1800 9 || { echo "lock timeout" >&2; exit 1; }
"$PY" -c "import importlib.metadata as m; print('prof wheel:', m.version('mlx-omarchy'))"
export MLX_DISABLE_COMPILE=1
export MLX_OMARCHY_GPU_PROFILE=$OUT/prof-$TAG.jsonl
export MLX_OMARCHY_GPU_PROFILE_LABEL=$TAG
M=$(ls -d ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/ | head -1)
B=~/src/ane-linux-experiments/benchmarks/qwen38-mlx-bench.py
P=~/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl
"$PY" "$B" --model "$M" --prompts "$P" \
  --limit "$LIMIT" --warmup 1 --passes "$PASSES" --new-tokens 32 --prefill-tokens 512 \
  --label prof-$TAG --out $OUT/contract-$TAG.json > $OUT/run-$TAG.log 2>&1
rc=$?
unset MLX_OMARCHY_GPU_PROFILE MLX_OMARCHY_GPU_PROFILE_LABEL
tail -2 $OUT/run-$TAG.log
python3 - "$OUT/contract-$TAG.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print("digest", d["ordered_records_sha256"][:16],
      "decode", d["decode_tok_rate"]["median"],
      "prefill512", d["pure_prefill"]["pure_prefill_tok_rate"])
PY
ls -la $OUT/prof-$TAG.jsonl
echo "WINDOW-DONE $TAG rc=$rc $STAMP"
