#!/bin/bash
# AneEncoderCoverage window (jw16): interleaved inventory battery on CURRENT main bytes.
# Runner: cand-run/vulkan_encoder.py (sha 789aaec3 = v0.7.1 bytes).
# Transport: relay-bypass candidate worker+client (44a99528/ad331981, current main default).
# Placement via MLX_OMARCHY_PLACED env (fused_e2e.py takes NO --islands flag).
# Rotation [AC, ABC, ACO, GPU] x6 interleaved = 24 runs; GPU arm is --no-ane control.
set -uo pipefail
W=/var/tmp/ane-cov
RUN=/var/tmp/ParakeetE2EJw16
PY=/var/tmp/V071REL-venv/bin/python
CRUN=/var/tmp/encwall-relay/cand-run/vulkan_encoder.py
CWORK=/var/tmp/encwall-relay/cand/bin/mlx-omarchy-ane-worker
LIBANE=/var/tmp/jw16-oproj-place/libane-strict-fill.so
BUNDLES=/var/tmp/jw16-conv-place/bundles-conv
JSONL=$W/rows.jsonl
mkdir -p $W
unset PYTHONPATH
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
export ANE_OP_WALL=1
export MLX_OMARCHY_ANE_RELAY_BYPASS=1
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
: > $JSONL
run_arm () {
  local name=$1 islands=$2 mode=$3 rep=$4
  local outdir=$W/out-$name scratch=$W/scratch-$name
  echo "--- arm $name PLACED=$islands MODE=$mode rep=$rep worker=$(sha256sum $CWORK | cut -c1-8) $(date -Iseconds) ---"
  python3 -c "import shutil; shutil.rmtree('$outdir', ignore_errors=True); shutil.rmtree('$scratch', ignore_errors=True)"
  mkdir -p "$outdir" "$scratch"
  local extr="" ctl=""
  if [ "$islands" = "GPU" ]; then extr="--no-ane"; ctl="--control"; fi
  # shellcheck disable=SC2086
  MLX_OMARCHY_PLACED="$islands" ANE_ISLAND_MODE=$mode \
  flock -w 900 /tmp/m1-gpu.lock \
  $PY $RUN/fused_e2e.py \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model ~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018 \
    --pkg /var/tmp/TdtLoopDefault/pkg \
    --encoder-runner $CRUN \
    --source /var/tmp/EncoderParityAne/encoder-source \
    --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
    --bundles $BUNDLES \
    --worker $CWORK \
    --libane $LIBANE \
    --scratch $scratch --out $outdir \
    $extr --deadline-ms 20000 > $W/arm-$name.log 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then echo "ARM $name RUN-FAILED rc=$rc"; tail -5 $W/arm-$name.log; exit 3; fi
  python3 /var/tmp/encwall-v071/attr_row.py "$outdir" "$name" "$islands" "$mode" "$rep" --jsonl $JSONL $ctl || exit 2
}
$PY /var/tmp/v063-jw16/scripts/venv-identity-guard.py --expect df3d4e74c597956c /var/tmp/V071REL-venv || exit 4
echo "staged runner $(sha256sum $CRUN | cut -c1-16) worker $(sha256sum $CWORK | cut -c1-16)"
run_arm warm-ac AC resident-batch 0
for rep in 1 2 3 4 5 6; do
  run_arm ac-serve$rep   AC  resident-batch $rep || exit $?
  run_arm abc-serve$rep  ABC resident-batch $rep || exit $?
  run_arm aco-serve$rep  ACO resident-batch $rep || exit $?
  run_arm gpu-serve$rep  GPU resident-batch $rep || exit $?
done
echo "ENCOV DONE $(date -Iseconds)"
