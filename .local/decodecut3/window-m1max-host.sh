#!/usr/bin/env bash
# Raw-gates arm (6056969a-lineage + rope-pair bf16) A/B window, m1max-host.
# Baseline for this host: dc7ca4a0 — run window with tag=baseline-dc7ca4a0
# BEFORE switching venv wheels; then rerun with the diag wheel installed.
set -u
TAG=${1:?tag}
OUT=/var/tmp/decodecut
PY=/var/tmp/decodecut-venv/bin/python
WT=/var/tmp/integ-wt
MODEL=$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)
BENCH=$WT/qwen38-mlx-bench.py
PROMPTS=$WT/qwen38-2b-prompts.jsonl
STAMP=$(date +%H%M%S)

echo "== kernel: $(uname -r) =="
echo "== stopping resident llama-server (if any) =="
pkill -TERM -f "llama-server" || true
sleep 3
exec 9>/tmp/m1-gpu.lock
flock -w 1800 9 || { echo "lock timeout" >&2; exit 1; }
echo "== lock held $TAG $STAMP =="
export MLX_DISABLE_COMPILE=1

if [[ "$TAG" != baseline* ]]; then
  echo "== fallback spy =="
  export GDN_FALLBACK_DEBUG=1
  "$PY" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" --limit 2 \
    --warmup 0 --passes 1 --prefill-tokens 512 \
    --label "spy-$TAG-$STAMP" --out "$OUT/spy-$TAG.json" > "$OUT/spy-$TAG.log" 2>&1
  echo "GDN fallback lines: $(grep -c GDN-FALLBACK "$OUT/spy-$TAG.log" || true)"
  unset GDN_FALLBACK_DEBUG

  echo "== logits gate vs logits-integ-m1max-host.json =="
  "$PY" /tmp/q38c/logits.py "$MODEL" "$OUT/logits-$TAG.json" "$TAG" > "$OUT/logits-$TAG.log" 2>&1
  "$PY" /tmp/q38c/compare_logits.py "$OUT/logits-$TAG.json" /tmp/q38c/logits-integ-m1max-host.json 2>&1 | tail -5
  "$PY" /tmp/q38c/gate_class.py "$OUT/logits-$TAG.json" 2>/dev/null || true
fi

echo "== A/B bench =="
"$PY" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" --limit 10 \
  --warmup 1 --passes 1 --prefill-tokens 512 \
  --label "$TAG-$STAMP" \
  --out "$OUT/cadence-$TAG.json" > "$OUT/cadence-$TAG.log" 2>&1 \
  || echo "CADENCE BENCH FAILED" >&2
"$PY" - <<EOF
import json
d = json.load(open("$OUT/cadence-$TAG.json"))
print("decode median tok/s:", d["decode_tok_rate"]["median"], "ttft:", d["ttft_tok_rate"]["median"])
EOF

echo "== dispatch profile =="
export MLX_OMARCHY_TRACE_DISPATCH=1
export MLX_OMARCHY_GPU_PROFILE=$OUT/prof-$TAG.jsonl
export MLX_OMARCHY_GPU_PROFILE_LABEL=$TAG
"$PY" $WT/scripts/profile_generate.py --model "$MODEL" \
  --prompt "France France France France France France France France France France France France France France France France" \
  --max-tokens 32 --temp 0 --seed 0 --markers "$OUT/markers-$TAG.jsonl" \
  > "$OUT/gen-$TAG.log" 2>&1
unset MLX_OMARCHY_TRACE_DISPATCH MLX_OMARCHY_GPU_PROFILE MLX_OMARCHY_GPU_PROFILE_LABEL
"$PY" $WT/scripts/profile_analyze.py "$OUT/prof-$TAG.jsonl" \
  --markers "$OUT/markers-$TAG.jsonl" \
  --compute-h $WT/overlay/mlx/backend/omarchy/compute.h \
  > "$OUT/analyze-$TAG.txt" 2>&1 || echo "ANALYZE FAILED" >&2
grep -E "decode: dispatches" "$OUT/analyze-$TAG.txt" || true
grep -iE "gated|rope" "$OUT/analyze-$TAG.txt" | head -8 || true
echo "== done $TAG $(date +%H%M%S) =="
