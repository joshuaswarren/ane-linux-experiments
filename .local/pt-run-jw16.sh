#!/bin/bash
# ParakeetTransport jw16 arm: resident-batch ABC on the pt instrument stack.
# Same additive instrumentation as jwm1 (runner 6fb0e5fc, client f7d5bd10).
# Certified jw16 set: bundles-sf, fill libane, gate.py pins db501a8c/38c73261.
# jw16 discipline: llm-inference.service is stopped by whoever holds the
# lock; this script only flocks and never touches the service.
set -euo pipefail
B=/var/tmp/jw16-pt
RUN=/var/tmp/ParakeetE2EJw16
CACHE=/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
export PYTHONPATH=/var/tmp/pt-wheelx:$CACHE
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
WORKER=/var/tmp/pt-wheelx/mlx/bin/mlx-omarchy-ane-worker
LIBANE=/var/tmp/jw16-oproj-place/libane-strict-fill.so
RUNNER=$B/vulkan_encoder_pt.py
ABC_HID=38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7
WANT_LIBMLX=$(cat $B/expected-libmlx.sha256)

run_pass () { # name
  local name=$1
  echo "--- pt $name $(date -Iseconds) ---"
  rm -rf $B/out-$name $B/scratch-$name
  mkdir -p $B/out-$name $B/scratch-$name
  ANE_ISLAND_MODE=resident-batch MLX_OMARCHY_PLACED=ABC \
  MLX_OMARCHY_EXPECTED_LIBMLX_SHA256=$WANT_LIBMLX \
  flock -w 900 /tmp/m1-gpu.lock \
  /home/joshuawarren/venv-agxgen/bin/python $RUN/fused_e2e.py \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model ~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018 \
    --pkg /var/tmp/TdtLoopDefault/pkg \
    --encoder-runner $RUNNER \
    --source /var/tmp/EncoderParityAne/encoder-source \
    --bundles /var/tmp/jw16-ep-bisect/bundles-sf \
    --worker $WORKER \
    --libane $LIBANE \
    --scratch $B/scratch-$name \
    --out $B/out-$name \
    --deadline-ms 20000 > $B/$name.log 2>&1
  python3 /var/tmp/jw16-ep-bisect/gate.py $B/out-$name "$ABC_HID"
  grep -E "libmlx identity|ane attribution|ane mode=" $B/$name.log | tail -3 || true
}
echo "=== pt jw16 start $(date -Iseconds) ==="
run_pass "$1"
echo "=== pt jw16 done $(date -Iseconds) ==="
