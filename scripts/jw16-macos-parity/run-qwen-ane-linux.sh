#!/bin/bash
# Linux ANE-only Qwen3.8-2B: first N corpus prompts, 32 greedy tokens each, one rep (contract shape, reduced n).
# Per prompt result JSON + logits; ids compared to the macOS ANEForge record afterwards.
# usage: run-qwen-ane-linux.sh OUTDIR [N]   (run from /var/tmp/qwen-ane-run; ANE only, no GPU lock needed)
set -u
OUT="${1:?outdir}"; N="${2:-10}"
mkdir -p "$OUT"
cd /var/tmp/qwen-ane-run || exit 1
i=0
while IFS= read -r line && [ "$i" -lt "$N" ]; do
  i=$((i + 1))
  id=$(printf '%s' "$line" | /var/tmp/qwen-ane-venv/bin/python3 -c "import json,sys; print(json.loads(sys.stdin.read())['id'])")
  text=$(printf '%s' "$line" | /var/tmp/qwen-ane-venv/bin/python3 -c "import json,sys; print(json.loads(sys.stdin.read())['text'])")
  [ -n "${PROMPT_IDS:-}" ] && case " $PROMPT_IDS " in *" $id "*) ;; *) continue ;; esac
  [ -e "$OUT/$id.json" ] && { echo "skip $id (done)"; continue; }
  echo "=== $id $(date -u +%FT%TZ)"
  LLAMA_TOKENIZE=/var/tmp/qwen-ane-run/llama-tokenize timeout 3600 /var/tmp/qwen-ane-venv/bin/python3 ane-qwen-model.py \
    --backend ane -m /var/tmp/qwen-gguf/Qwen3.8-2B-Q4_K_M.gguf -p "$text" --prompt-id "$id" \
    --gguf-py /var/tmp/qwen-ane-venv/lib/python3.14/site-packages \
    --recurrent-anec fixtures/qwen854/qwen-recurrent-native.anec --generate 32 \
    --result-output "$OUT/$id.json" --logits-output "$OUT/$id-logits.npy" > "$OUT/$id.log" 2>&1
  echo "rc=$? $(grep -E 'timing_s' "$OUT/$id.log" | tail -1)"
done < "$HOME/bench-scripts/qwen38-2b-prompts.jsonl"
echo QWEN-ANE-LINUX-DONE
