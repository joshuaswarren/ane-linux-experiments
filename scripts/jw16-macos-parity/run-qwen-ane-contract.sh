#!/bin/bash
# Contract protocol for the Linux ANE Qwen reference: 3 warmup corpus passes then 10 measured passes over the first
# 10 corpus prompts (32 greedy tokens each). One process per PASS: the model/ANE session is loaded once and the
# 10 prompts loop in-process, with per-prompt result/logits files identical in format to the per-prompt-process
# runner. Resumable (also across reboots, via the qwen-contract systemd unit): a prompt counts as done only when its
# <id>.json exists (written last, atomically), so a prompt killed mid-run is rerun in full. Honors
# /var/tmp/qwen-contract.PAUSE between prompts (in-process) and between passes (here).
# Each attempt appends "##### attempt <pass> <n> <UTC>" to <pass>.log so the analysis can tell process starts apart.
# usage: run-qwen-ane-contract.sh OUTBASE   (ane-qwen-model.py and tools/ live under /var/tmp/qwen-ane-run)
set -u
OUTBASE="${1:?outbase}"
RUN=/var/tmp/qwen-ane-run
VENV=/var/tmp/qwen-ane-venv
PAUSE=/var/tmp/qwen-contract.PAUSE
cd "$RUN" || exit 1
mkdir -p "$OUTBASE"
done_in() { ls "$OUTBASE/$1"/p*.json 2>/dev/null | wc -l; }
for pass in w1 w2 w3 r01 r02 r03 r04 r05 r06 r07 r08 r09 r10; do
  [ "$(done_in "$pass")" -ge 10 ] && continue
  echo "##### pass $pass $(date -u +%FT%TZ)"
  for attempt in 1 2 3; do
    while [ -e "$PAUSE" ]; do sleep 60; done
    echo "##### attempt $pass $attempt $(date -u +%FT%TZ) boot $(cat /proc/sys/kernel/random/boot_id)" >> "$OUTBASE/$pass.log"
    LLAMA_TOKENIZE="$RUN/llama-tokenize" timeout 28800 "$VENV/bin/python3" "$RUN/ane-qwen-model.py" \
      --backend ane -m /var/tmp/qwen-gguf/Qwen3.8-2B-Q4_K_M.gguf \
      --gguf-py "$VENV/lib/python3.14/site-packages" \
      --recurrent-anec fixtures/qwen854/qwen-recurrent-native.anec --generate 32 --limit 10 \
      --prompts-file "$HOME/bench-scripts/qwen38-2b-prompts.jsonl" --results-dir "$OUTBASE/$pass" \
      --pause-file "$PAUSE" >> "$OUTBASE/$pass.log" 2>&1
    rc=$?
    echo "##### pass $pass attempt $attempt rc=$rc done=$(done_in "$pass")/10 $(date -u +%FT%TZ)"
    [ "$(done_in "$pass")" -ge 10 ] && break
  done
  [ "$(done_in "$pass")" -ge 10 ] || { echo "QWEN-CONTRACT-FAILED pass $pass"; exit 1; }
done
echo QWEN-CONTRACT-DONE
