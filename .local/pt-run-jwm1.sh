#!/bin/bash
# ParakeetTransport jwm1 arm: resident-batch ABC on the pt instrument stack.
# Runner: certified ed8c7758 bytes + 7 additive transport-instrumentation
# hunks -> 6fb0e5fc. Client: overlay ane_resident.py (f7d5bd10) — superset of
# the deployed 1972bc80 (adds write/read_ns + phase parsing), same interface.
# Worker+libmlx: pt wheel (mlx-omarchy pt.<commit>), PYTHONPATH puts the pt
# wheel FIRST so bindings and libmlx are the same build; the identity guard
# hard-fails on mismatch. Bundles/libane/gate: the certified jwm1 set.
set -euo pipefail
B=/var/tmp/jwm1-pt
RUN=/var/tmp/ParakeetE2E
CACHE=/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
export PYTHONPATH=/var/tmp/pt-wheelx:$CACHE
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
WORKER=/var/tmp/pt-wheelx/mlx/bin/mlx-omarchy-ane-worker
LIBANE=/var/tmp/jwm1-oproj-place/libane-strict-fill.so
RUNNER=$B/vulkan_encoder_pt.py
ABC_HID=38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7
WANT_LIBMLX=$(cat $B/expected-libmlx.sha256)

run_pass () { # name tag
  local name=$1 tag=$2
  echo "--- pt $name $tag $(date -Iseconds) ---"
  rm -rf $B/out-$name $B/scratch-$name
  mkdir -p $B/out-$name $B/scratch-$name
  ANE_ISLAND_MODE=resident-batch MLX_OMARCHY_PLACED=ABC \
  MLX_OMARCHY_EXPECTED_LIBMLX_SHA256=$WANT_LIBMLX \
  flock -w 900 /tmp/m1-gpu.lock \
  /home/joshuawarren/venv-agxgen/bin/python /var/tmp/ParakeetE2E/parakeet_e2e.py \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model ~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018 \
    --pkg /var/tmp/ParakeetE2EAneBnns/pkg \
    --encoder-runner $RUNNER \
    --source /var/tmp/EncoderParityAne/encoder-source \
    --bundles /var/tmp/jwm1-ep-bisect/bundles-sf \
    --worker $WORKER \
    --libane $LIBANE \
    --scratch $B/scratch-$name \
    --ane-reference /var/tmp/EncoderParityAne/out-ane/encoder_hidden.npy \
    --out $B/out-$name \
    --deadline-ms 20000 > $B/$name.log 2>&1
  python3 /var/tmp/jwm1-ep-bisect/gate.py $B/out-$name "$ABC_HID"
  grep -E "libmlx identity|ane attribution|ane_exec|ane mode=" $B/$name.log | tail -4 || true
}
echo "=== pt jwm1 start $(date -Iseconds) ==="
run_pass "$1" "$1"
echo "=== pt jwm1 done $(date -Iseconds) ==="
