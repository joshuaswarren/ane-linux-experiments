#!/bin/bash
# Contract protocol for the Linux ANE Qwen reference: 3 warmup corpus passes then 10 measured passes over the first
# 10 corpus prompts (32 greedy tokens each). One process per prompt (session opened per process). Resumable: a
# finished prompt json is skipped. usage: run-qwen-ane-contract.sh OUTBASE
set -u
OUTBASE="${1:?outbase}"
for pass in w1 w2 w3 r01 r02 r03 r04 r05 r06 r07 r08 r09 r10; do
  echo "##### pass $pass $(date -u +%FT%TZ)"
  bash /var/tmp/appbar/run-qwen-ane-linux.sh "$OUTBASE/$pass" 10 | grep -E "^===|^rc=|DONE"
done
echo QWEN-CONTRACT-DONE
