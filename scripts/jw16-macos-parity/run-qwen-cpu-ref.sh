#!/bin/bash
# CPU fp32 reference (same script, --backend cpu) for the first N corpus prompts, 32 greedy tokens each.
# usage: run-qwen-cpu-ref.sh OUTDIR [N]
set -u
OUT="${1:?outdir}"; N="${2:-10}"
mkdir -p "$OUT"
cd /var/tmp/qwen-ane-run || exit 1
export LLAMA_TOKENIZE=/var/tmp/qwen-ane-run/llama-tokenize
i=0
while IFS= read -r line && [ "$i" -lt "$N" ]; do
  i=$((i + 1))
  id=$(printf '%s' "$line" | /var/tmp/qwen-ane-venv/bin/python3 -c "import json,sys; print(json.loads(sys.stdin.read())['id'])")
  text=$(printf '%s' "$line" | /var/tmp/qwen-ane-venv/bin/python3 -c "import json,sys; print(json.loads(sys.stdin.read())['text'])")
  echo "=== $id $(date -u +%FT%TZ)"
  timeout 1800 /var/tmp/qwen-ane-venv/bin/python3 ane-qwen-model.py --backend cpu -m /var/tmp/qwen-gguf/Qwen3.8-2B-Q4_K_M.gguf \
    -p "$text" --prompt-id "$id" --gguf-py /var/tmp/qwen-ane-venv/lib/python3.14/site-packages --generate 32 \
    --result-output "$OUT/$id.json" --logits-output "$OUT/$id-logits.npz" > "$OUT/$id.log" 2>&1
  echo "rc=$? $(grep timing_s "$OUT/$id.log" | tail -1)"
done < "$HOME/bench-scripts/qwen38-2b-prompts.jsonl"
echo QWEN-CPU-DONE
