#!/bin/bash
# Whole-encoder ANE E2E: fused_e2e with the single-submit whole-encoder
# runner (Apple hwx, 13701 TDs, one ANE submit) behind the encoder call.
# Lock: flock -w 900 /tmp/m1-gpu.lock, never steal, never unlink.
set -e
PREFIX=/var/tmp/ane-whole-e2e
PY=/var/tmp/v072-venv-fused/bin/python3
export ANE_WHOLE_ENCODER_ANEC=/var/tmp/encoder-fp16-v3.anec
OUT=$PREFIX/out-$1
SCR=$PREFIX/scratch-$1
mkdir -p "$OUT" "$SCR"
flock -w 900 /tmp/m1-gpu.lock \
  $PY /var/tmp/m1-host-ane-step2/fused-e2e/fused_e2e.py \
  --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
  --golden /var/tmp/EncoderParityAne/capture \
  --model ~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018 \
  --pkg /var/tmp/TdtLoopDefault/pkg \
  --encoder-runner /var/tmp/m1-host-ane-step2/fused-e2e/ane_whole_encoder.py \
  --source /var/tmp/IslandsExecM1-host/encoder-source \
  --bundles /var/tmp/island-reexport/bundles \
  --worker /var/tmp/encwall-decomp/libane_tile512.so \
  --libane /var/tmp/encwall-decomp/libane_tile512.so \
  --scratch "$SCR" \
  --ane-reference /var/tmp/EncoderParityAne/out-ane/encoder_hidden.npy \
  --out "$OUT" \
  --deadline-ms 20000
