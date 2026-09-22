#!/usr/bin/env bash
set -u
PY=/var/tmp/decodecut-venv/bin/python
exec 9>/tmp/m1-gpu.lock
flock -w 1500 9 || exit 1
echo "== lock held $(date +%H%M%S) =="
echo "== 1. in-model fallback check =="
export GDN_FALLBACK_DEBUG=1 MLX_DISABLE_COMPILE=1
"$PY" /var/tmp/decodecut/spy_dtypes.py > /var/tmp/decodecut/spy3.out 2>&1
echo "fallback lines: $(grep -c GDN-FALLBACK /var/tmp/decodecut/spy3.out)"
unset GDN_FALLBACK_DEBUG
echo "== 2. logits gate =="
MODEL=$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)
"$PY" /tmp/q38c/logits.py "$MODEL" /var/tmp/decodecut/logits-fix2.json rawfix2 > /var/tmp/decodecut/logits-fix2.log 2>&1
"$PY" /var/tmp/decodecut/compare_logits.py /var/tmp/decodecut/logits-fix2.json /tmp/q38c/logits-integ-m1-host.json 2>&1 | grep -v rtmod | head -5
"$PY" /var/tmp/decodecut/gate_class.py /var/tmp/decodecut/logits-fix2.json 2>/dev/null
echo "== 3. A/B window (bench+profile) =="
TAG=rawfix4
OUT=/var/tmp/decodecut
STAMP=$(date +%H%M%S)
BENCH=/tmp/q38c/qwen38-mlx-bench.py
PROMPTS=/tmp/q38c/qwen38-2b-prompts.jsonl
"$PY" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" --limit 10 \
  --warmup 1 --passes 1 --prefill-tokens 512 \
  --label "$TAG-$STAMP" \
  --out "$OUT/cadence-$TAG.json" > "$OUT/cadence-$TAG.log" 2>&1 \
  || echo "CADENCE BENCH FAILED"
"$PY" - <<'EOF'
import json
d=json.load(open("/var/tmp/decodecut/cadence-rawfix4.json"))
print("decode median tok/s:", d["decode_tok_rate"]["median"], "ttft:", d["ttft_tok_rate"]["median"])
EOF
export MLX_OMARCHY_TRACE_DISPATCH=1
export MLX_OMARCHY_GPU_PROFILE=$OUT/prof-$TAG.jsonl
export MLX_OMARCHY_GPU_PROFILE_LABEL=$TAG
"$PY" /var/tmp/integ-wt/scripts/profile_generate.py --model "$MODEL" \
  --prompt "France France France France France France France France France France France France France France France France" \
  --max-tokens 32 --temp 0 --seed 0 --markers "$OUT/markers-$TAG.jsonl" \
  > "$OUT/gen-$TAG.log" 2>&1
unset MLX_OMARCHY_TRACE_DISPATCH MLX_OMARCHY_GPU_PROFILE MLX_OMARCHY_GPU_PROFILE_LABEL
"$PY" /var/tmp/integ-wt/scripts/profile_analyze.py "$OUT/prof-$TAG.jsonl" \
  --markers "$OUT/markers-$TAG.jsonl" \
  --compute-h /var/tmp/integ-wt/overlay/mlx/backend/omarchy/compute.h \
  > "$OUT/analyze-$TAG.txt" 2>&1 || echo "ANALYZE FAILED"
grep -E "decode: dispatches" "$OUT/analyze-$TAG.txt"
grep -E "GatedDelta|gated" "$OUT/analyze-$TAG.txt" | head -4
echo "== done $(date +%H%M%S) =="
