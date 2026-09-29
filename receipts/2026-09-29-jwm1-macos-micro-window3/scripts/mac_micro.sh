#!/bin/bash
# Same-die macOS microbench leg. usage: mac_micro.sh <python> <model-dir> <prompts.jsonl> <outdir> <scripts-dir>
set -u
PY="$1"; M="$2"; P="$3"; O="$4"; S="$5"
mkdir -p "$O"
for s in mm_idle chain_costs host_bound; do
  "$PY" "$S/$s.py" > "$O/$s.out" 2> "$O/$s.err"
  echo "$s rc=$?"
done
for s in qmm_small_m qmm_large_m; do
  "$PY" "$S/$s.py" "$M" > "$O/$s.out" 2> "$O/$s.err"
  echo "$s rc=$?"
done
"$PY" "$S/ttft_curve.py" "$M" "$P" > "$O/ttft_curve.out" 2> "$O/ttft_curve.err"
echo "ttft_curve rc=$?"
echo MICRO-DONE
