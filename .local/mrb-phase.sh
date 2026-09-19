#!/usr/bin/env bash
# MesaRegressionBisect phase runner: interleaved A/B of the two wheel vintages
# under ONE flock hold. Phase a = stray mlx-serve resident (09-19 conditions);
# phase b = stray killed (09-17 conditions). Caller holds /tmp/m1-gpu.lock.
set -euo pipefail
R=/var/tmp/SwigluRmsJw16
OUT=/var/tmp/MesaRegress20260919
MODEL=/home/joshuawarren/.cache/huggingface/hub/models--mlx-community--Qwen2.5-0.5B-Instruct-4bit/snapshots/a5339a4131f135d0fdc6a5c8b5bbed2753bbe0f3
BENCH=$R/rms/scripts/bench_decode.py
MANIFEST=$R/rms/scripts/bench_matrix.json
PYB=$R/venv-base/bin/python
WB=$(echo "$R"/dist-base/mlx_omarchy-0.32.2.dev202609152131+1deb70f1-*.whl)
PYV=/var/tmp/jw16-v061-parity/v061-venv/bin/python
WV=$(echo /var/tmp/v061-release/mlx_omarchy-0.32.2.dev202609170611+b8e5300-cp314-*.whl)
PH=$1
if flock -n /tmp/m1-gpu.lock -c true; then
  echo "ERROR: nested flock -n succeeded; we do not hold the lock" >&2
  exit 2
fi
echo "== phase $PH $(date -Iseconds) =="
"$PYB" "$R"/ab_decode.py \
  --arm "base=$PYB=$WB" \
  --arm "v061=$PYV=$WV" \
  --model "$MODEL" --manifest "$MANIFEST" --bench "$BENCH" \
  --rounds 6 --out "$OUT/ab-phase-$PH.json"
