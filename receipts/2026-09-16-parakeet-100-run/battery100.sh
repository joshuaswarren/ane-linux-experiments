#!/bin/bash
# Parakeet E2E 100-run warm stability battery (criterion 14, gate 10) on the
# v0.5.1 release wheel site /var/tmp/V051E2E/site. Derived from the proven
# /var/tmp/V051E2E/battery.sh (3/3, pins db501a8c/38c73261); changes are only:
# loop 1..100, per-run gate check (STOP on divergence, no blind retry), RSS
# sampling on r1/r50/r100, spirv cache pre-seeded from the proven 3-run
# battery so all 100 runs are warm. Runtime contract: ONE fresh process per
# run (what fused_e2e.py + every prior battery does; the ANE island worker is
# spawned per run, 1 worker start per run), shared SPIR-V cache, same boot.
# Lock /tmp/m1-gpu.lock: flock -w 900, never steal, never unlink.
set -euo pipefail
P=/var/tmp/V051E2E-battery100
PY=/home/joshuawarren/venv-agxgen/bin/python
export PYTHONPATH=/var/tmp/V051E2E/site:/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
export MLX_OMARCHY_SPIRV_CACHE=$P/spirv
export ANE_ISLAND_MODE=resident-batch
E2E=/var/tmp/ParakeetE2EBaseline7d82/fused_e2e.py
RUNNER=/var/tmp/E2EREV/overlay/tools/coreml/vulkan_encoder.py
E2EARGS=(--audio /var/tmp/ParakeetE2E/audio/fixture.flac
  --golden /var/tmp/EncoderParityAne/capture
  --model ~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
  --pkg /var/tmp/TdtLoopDefault/pkg
  --encoder-runner $RUNNER
  --source /var/tmp/EncoderParityAne/encoder-source
  --bundles /var/tmp/island-reexport/bundles
  --worker /var/tmp/mlx-main-strict/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
  --libane /var/tmp/island-reexport/libane-strict.so
  --ane-reference /var/tmp/EncoderParityAne/out-ane/encoder_hidden.npy
  --deadline-ms 20000)
mkdir -p $P
[ -d $P/spirv ] || cp -a /var/tmp/V051E2E-battery/spirv $P/spirv
echo "battery-start $(date -Iseconds) uptime_s=$(cut -d' ' -f1 /proc/uptime)"
stat -c "lock inode=%i held $(date -Iseconds)" /tmp/m1-gpu.lock
for r in $(seq 1 100); do
  echo "--- E2E r$r $(date -Iseconds) ---"
  rm -rf $P/out-$r $P/scratch-$r
  mkdir -p $P/out-$r $P/scratch-$r
  t0=$(date +%s.%N)
  case $r in
    1|50|100)
      : > $P/rss-$r.csv
      flock -w 900 /tmp/m1-gpu.lock \
        $PY $E2E "${E2EARGS[@]}" --scratch $P/scratch-$r --out $P/out-$r &
      epid=$!
      while kill -0 $epid 2>/dev/null; do
        prss=$(awk '/VmRSS/{print $2}' /proc/$epid/status 2>/dev/null || echo 0)
        kids=$(pgrep -P $epid 2>/dev/null | paste -sd, -)
        krss=0
        [ -n "$kids" ] && krss=$(ps -o rss= -p "$kids" 2>/dev/null | awk '{t+=$1} END{print t+0}')
        echo "$(date +%s.%N),$prss,$(( ${prss:-0} + krss ))" >> $P/rss-$r.csv
        sleep 0.25
      done
      wait $epid
      ;;
    *)
      flock -w 900 /tmp/m1-gpu.lock \
        $PY $E2E "${E2EARGS[@]}" --scratch $P/scratch-$r --out $P/out-$r
      ;;
  esac
  t1=$(date +%s.%N)
  echo "r$r wall=$(awk -v a=$t1 -v b=$t0 'BEGIN{printf "%.2f", a-b}')s"
  python3 $P/check_run.py $r $P/out-$r >> $P/per-run.jsonl \
    || { echo "DIVERGENCE at r$r — battery STOPPED, out-$r + scratch-$r preserved, no retry"; exit 42; }
done
stat -c "lock inode=%i freed $(date -Iseconds)" /tmp/m1-gpu.lock
flock -n /tmp/m1-gpu.lock true && echo "LOCK-FREE-OK"
echo "battery-end $(date -Iseconds) uptime_s=$(cut -d' ' -f1 /proc/uptime)"
echo '--- identity ---'
sha256sum $P/out-1/transcript.txt $P/out-100/transcript.txt
