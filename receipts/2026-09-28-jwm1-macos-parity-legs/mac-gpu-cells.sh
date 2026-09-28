#!/bin/bash
# jwm1 macOS GPU legs: mirrors the Linux cell protocol (qwen38-mlx-bench.py, temp 0 greedy,
# --warmup 2 --passes 1, n=5 per cell). usage: mac-gpu-cells.sh <bench-dir> <python> <model-dir> <outdir>
set -u
B="$1"; PY="$2"; M="$3"; O="$4"; mkdir -p "$O"; cd "$B" || exit 2
run() { # label limit newtok prefill
  "$PY" qwen38-mlx-bench.py --model "$M" --prompts qwen38-2b-prompts.jsonl --limit "$2" \
    --new-tokens "$3" --prefill-tokens "$4" --warmup 2 --passes 1 --label "$1" --out "$O/$1.json" > "$O/$1.log" 2>&1
  echo "$1 rc=$?"
}
for N in 512 1024 2048; do for i in 1 2 3 4 5; do run "mac-prefill$N-run$i" 1 1 $N; done; done
run mac-decode64 5 64 0
run mac-decode128 5 128 0
for i in 1 2 3 4 5; do run "mac-decode256-run$i" 1 256 0; done
echo CELLS-DONE
