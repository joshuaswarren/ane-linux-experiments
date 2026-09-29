#!/bin/bash
# Per-layer checkpoint capture for one corpus prompt: ANE arm then CPU fp32 reference arm (same script).
# usage: run-qwen-ckpt.sh PROMPT_ID OUTDIR GENERATE
set -u
ID="${1:?prompt id}"; OUT="${2:?outdir}"; GEN="${3:-6}"
mkdir -p "$OUT"
cd /var/tmp/qwen-ane-run || exit 1
TEXT=$(grep "\"id\": \"$ID\"" "$HOME/bench-scripts/qwen38-2b-prompts.jsonl" | /var/tmp/qwen-ane-venv/bin/python3 -c "import json,sys; print(json.loads(sys.stdin.read())['text'])")
echo "prompt: $TEXT"
export LLAMA_TOKENIZE=/var/tmp/qwen-ane-run/llama-tokenize
GG=/var/tmp/qwen-ane-venv/lib/python3.14/site-packages
M=/var/tmp/qwen-gguf/Qwen3.8-2B-Q4_K_M.gguf
echo "=== ANE arm $(date -u +%FT%TZ)"
timeout 3000 /var/tmp/qwen-ane-venv/bin/python3 ane-qwen-model.py --backend ane -m "$M" -p "$TEXT" --gguf-py "$GG" \
  --recurrent-anec fixtures/qwen854/qwen-recurrent-native.anec --generate "$GEN" \
  --result-output "$OUT/ane.json" --logits-output "$OUT/ane-logits.npz" --checkpoints-output "$OUT/ane-ckpt.npz" > "$OUT/ane.log" 2>&1
echo "rc=$? $(grep timing_s "$OUT/ane.log" | tail -1)"
echo "=== CPU arm $(date -u +%FT%TZ)"
timeout 12000 /var/tmp/qwen-ane-venv/bin/python3 ane-qwen-model.py --backend cpu -m "$M" -p "$TEXT" --gguf-py "$GG" --generate "$GEN" \
  --result-output "$OUT/cpu.json" --logits-output "$OUT/cpu-logits.npz" --checkpoints-output "$OUT/cpu-ckpt.npz" > "$OUT/cpu.log" 2>&1
echo "rc=$? $(grep timing_s "$OUT/cpu.log" | tail -1)"
echo QWEN-CKPT-DONE
