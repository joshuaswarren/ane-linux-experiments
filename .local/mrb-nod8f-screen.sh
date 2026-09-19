#!/usr/bin/env bash
# MesaRegressionBisect nod8f screen: single arm, 6 rounds, wheel 1deb70f1
# protocol. Caller (launcher) holds /tmp/m1-gpu.lock and manages llm-inference.
set -uo pipefail
R=/var/tmp/SwigluRmsJw16
OUT=/var/tmp/MesaRegress20260919
MODEL=/home/joshuawarren/.cache/huggingface/hub/models--mlx-community--Qwen2.5-0.5B-Instruct-4bit/snapshots/a5339a4131f135d0fdc6a5c8b5bbed2753bbe0f3
BENCH=$R/rms/scripts/bench_decode.py
MANIFEST=$R/rms/scripts/bench_matrix.json
PY=$R/venv-base/bin/python
WHEEL=$(echo "$R"/dist-base/mlx_omarchy-0.32.2.dev202609152131+1deb70f1-*.whl)
PKGNOD8F=/home/joshuawarren/src/mesa-pkg-jw16-nod8f-20260919/mesa-honeykrisp-omarchy-26.3.0.devel.hkd447b64-1-aarch64.pkg.tar.xz
PKGBASE=/var/tmp/TermAJW16/mesa-honeykrisp-omarchy-26.3.0.devel.hk5deac1c-2-aarch64.pkg.tar.xz

if flock -n /tmp/m1-gpu.lock -c true; then
  echo "ERROR: we do not hold the lock" >&2
  exit 2
fi
echo "== install nod8f (hkd447b64-1) =="
sudo pacman -U --noconfirm "$PKGNOD8F" | tail -1
{ pacman -Q mesa-honeykrisp-omarchy; } | tee "$OUT/prov-nod8f.txt"
"$PY" "$R"/ab_decode.py \
  --arm "nod8f=$PY=$WHEEL" \
  --model "$MODEL" --manifest "$MANIFEST" --bench "$BENCH" \
  --rounds 6 --out "$OUT/ab-nod8f.json"
echo "== restore installed hk5deac1c-2 =="
sudo pacman -U --noconfirm "$PKGBASE" | tail -1
pacman -Q mesa-honeykrisp-omarchy | tee "$OUT/prov-nod8f-restore.txt"
date -u +"%Y-%m-%dT%H:%M:%SZ"
