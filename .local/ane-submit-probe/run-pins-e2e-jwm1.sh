#!/bin/bash
# run-pins-e2e-jwm1.sh — one pin-gated e2e pass on the certified green config
# on jwm1 (T8103): same runner/bundles/worker/libane bytes as jw16's
# run-pins-e2e.sh (all sha-verified identical across hosts), harness
# fused_e2e.py 0e38e7b1 from /var/tmp/TdtLoopDefault. PLACED=ABC,
# resident-batch. Caller holds /tmp/m1-gpu.lock. Gates checked by
# /var/tmp/jwm1-ep-bisect/gate.py (transcript pin db501a8c hardcoded there).
set -uo pipefail
TAG=${1:?tag required}
RUN=/var/tmp/TdtLoopDefault
PY=/home/joshuawarren/venv-agxgen/bin/python
OUTDIR=/var/tmp/ane-submit-probe/pins-e2e/$TAG
mkdir -p "$OUTDIR"
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE
export PYTHONPATH=/var/tmp/E2EREV/site:/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
export ANE_ISLAND_MODE=resident-batch
export MLX_OMARCHY_PLACED=ABC

{
  echo "tag=$TAG date=$(date -Is)"
  echo "module: $(grep '^ane ' /proc/modules) version=$(cat /sys/module/ane/version 2>/dev/null)"
  echo "map_mode: $(cat /sys/module/ane/parameters/map_mode 2>/dev/null || echo 'n/a')"
  echo "runner: $(sha256sum /var/tmp/jwm1-r4/vulkan_encoder_r4.py)"
  echo "worker: $(sha256sum /var/tmp/r4-wheelx/mlx/bin/mlx-omarchy-ane-worker)"
  echo "libane: $(sha256sum /var/tmp/jwm1-oproj-place/libane-strict-fill.so)"
  echo "harness: $(sha256sum $RUN/fused_e2e.py)"
} > "$OUTDIR/identity.txt"

$PY $RUN/fused_e2e.py \
  --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
  --golden /var/tmp/EncoderParityAne/capture \
  --model /home/joshuawarren/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018 \
  --pkg /var/tmp/TdtLoopDefault/pkg \
  --encoder-runner /var/tmp/jwm1-r4/vulkan_encoder_r4.py \
  --source /var/tmp/EncoderParityAne/encoder-source \
  --bundles /var/tmp/jwm1-ep-bisect/bundles-sf \
  --worker /var/tmp/r4-wheelx/mlx/bin/mlx-omarchy-ane-worker \
  --libane /var/tmp/jwm1-oproj-place/libane-strict-fill.so \
  --scratch $OUTDIR/scratch \
  --out $OUTDIR \
  --deadline-ms 20000

python3 /var/tmp/jwm1-ep-bisect/gate.py "$OUTDIR" 38c73261 || echo "GATE FAILED for $TAG"
