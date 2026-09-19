#!/usr/bin/env bash
# MesaRegressionBisect residual screen: same-session paired single-arm phases
# with driver swaps, 6 rounds each on short+ctx1024, 1deb70f1 wheel protocol
# (the vintage the 158.17-vs-179.70 numbers came from).
# Caller holds /tmp/m1-gpu.lock. Restores hk5deac1c-2 at the end.
set -uo pipefail
R=/var/tmp/SwigluRmsJw16
OUT=/var/tmp/MesaRegress20260919
MODEL=/home/joshuawarren/.cache/huggingface/hub/models--mlx-community--Qwen2.5-0.5B-Instruct-4bit/snapshots/a5339a4131f135d0fdc6a5c8b5bbed2753bbe0f3
BENCH=$R/rms/scripts/bench_decode.py
MANIFEST=$R/rms/scripts/bench_matrix.json
PY=$R/venv-base/bin/python
WHEEL=$(echo "$R"/dist-base/mlx_omarchy-0.32.2.dev202609152131+1deb70f1-*.whl)
PKGBUNDLE=/home/joshuawarren/src/mesa-pkg-jw16-resid-20260919/mesa-honeykrisp-omarchy-26.3.0.devel.hk092f35e-1-aarch64.pkg.tar.xz
PKGRESTO=/home/joshuawarren/src/mesa-pkg-jw16-simdmat-20260919/mesa-honeykrisp-omarchy-26.3.0.devel.hk3a37b4f-3-aarch64.pkg.tar.xz
PKGBASE=/var/tmp/TermAJW16/mesa-honeykrisp-omarchy-26.3.0.devel.hk5deac1c-2-aarch64.pkg.tar.xz

if flock -n /tmp/m1-gpu.lock -c true; then
  echo "ERROR: we do not hold the lock" >&2
  exit 2
fi

echo "== stop llm-inference (restart on exit) =="
sudo systemctl stop llm-inference.service
trap 'sudo systemctl start llm-inference.service' EXIT

provenance() {
  { pacman -Q mesa-honeykrisp-omarchy
    vulkaninfo --summary 2>/dev/null | grep -E "driverName|driverInfo" | head -2; } | tee "$OUT/prov-$1.txt"
}

run_phase() {
  "$PY" "$R"/ab_decode.py \
    --arm "$1=$PY=$WHEEL" \
    --model "$MODEL" --manifest "$MANIFEST" --bench "$BENCH" \
    --rounds 6 --out "$OUT/ab-resid-$1.json"
}

echo "== install resid-bundle =="
sudo pacman -U --noconfirm "$PKGBUNDLE" | tail -2
provenance resid-bundle
run_phase bundle

echo "== install resto (3a37b4f-3) same-session control =="
sudo pacman -U --noconfirm "$PKGRESTO" | tail -2
provenance resto
run_phase resto

echo "== restore installed hk5deac1c-2 =="
sudo pacman -U --noconfirm "$PKGBASE" | tail -2
provenance base-restore
date -u +"%Y-%m-%dT%H:%M:%SZ"
