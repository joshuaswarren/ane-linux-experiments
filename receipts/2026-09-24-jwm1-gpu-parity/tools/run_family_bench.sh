#!/usr/bin/env bash
# Convenience wrapper to invoke /var/tmp/vprof/family_bench.py with a venv
# and a model path, writing the JSON to a known path.
set -euo pipefail
VENV="${1:?venv path}"
MODEL="${2:?model path}"
OUT="${3:?out json path}"
VENVPY="${VENV}/bin/python"
cd /var/tmp/vprof
"${VENVPY}" family_bench.py --model "${MODEL}" --out "${OUT}" --reps 30
echo "wrote ${OUT}"
