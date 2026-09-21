#!/bin/bash
# repeat-capture2.sh — full-ASR repeat with FIXED during-run /proc/<pid>/maps capture.
# Mapper appends directly (no sort buffering, no kill race); bounded 120s self-termination.
set -uo pipefail

RUN=/var/tmp/jwm1-ane-step2/fused-e2e
PY=/var/tmp/jwm1-v072rc1/venv/bin/python3
RUNNER=/var/tmp/encwall-v071/base/vulkan_encoder.py
MODEL=/home/joshuawarren/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
WORKER=/var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=/var/tmp/jwm1-ane-step2/libane.so
LIBMLX=/var/tmp/jwm1-v072rc1/venv/lib/python3.14/site-packages/mlx/lib/libmlx.so
CORE=/var/tmp/jwm1-v072rc1/venv/lib/python3.14/site-packages/mlx/core.cpython-314-aarch64-linux-gnu.so
DRIVER=/tmp/mesa-sin-ftz-jwm1/drivers/libvulkan_asahi-e167.so
ICD=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json
TS=$(date +%Y%m%dT%H%M%S)
OUT=/var/tmp/jwm1-ane-step2/fused-e2e/out-asr-repeat-$TS
SCRATCH=$RUN/scratch-asr-repeat-$TS
mkdir -p "$OUT" "$SCRATCH"
ID=$OUT/identity
mkdir -p "$ID"

export VK_DRIVER_FILES=$ICD
export MLX_OMARCHY_PLACED=AC
unset PYTHONPATH LD_LIBRARY_PATH HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL MLX_OMARCHY_SPIRV_CACHE || true

# --- allowlisted env + argv capture ---
{
  echo "date: $(date -Ins)"
  echo "host: $(hostname) $(uname -r)"
  echo "VK_DRIVER_FILES=${VK_DRIVER_FILES-}"
  echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH-}"
  echo "PYTHONPATH=${PYTHONPATH-}"
  env | grep -E '^MLX_[A-Za-z0-9_]+=' | sort
  env | grep -E '^OMP_(NUM_THREADS|MAX_ACTIVE_LEVELS|PROC_BIND|SCHEDULE)=' | sort
} > "$ID/env-allowlist.txt"
{
  printf 'argv:'; printf ' %q' \
    "$PY" "$RUN/fused_e2e.py" \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model "$MODEL" \
    --pkg /var/tmp/TdtLoopDefault/pkg \
    --encoder-runner "$RUNNER" \
    --source /var/tmp/IslandsExecJwm1/encoder-source \
    --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
    --bundles /var/tmp/jwm1-ane-step2/bundles \
    --worker "$WORKER" \
    --libane "$LIBANE" \
    --scratch "$SCRATCH" --out "$OUT" \
    --deadline-ms 20000
  echo
} > "$ID/argv.txt"

# --- pre-run binary identity ---
{
  sha256sum "$WORKER" "$LIBANE" "$LIBMLX" "$CORE" "$DRIVER" "$RUNNER" "$RUN/fused_e2e.py" "$PY"
  echo "driver-buildid: $(readelf -n "$DRIVER" | sed -n 's/.*Build ID: //p')"
  echo "icd-points-to: $(sed -n 's/.*"library_path": "\(.*\)",/\1/p' "$ICD")"
} > "$ID/identity-pre.txt" 2>&1

# --- FIXED during-run maps capture: direct append, no sort, bounded ---
MAPFILE=$ID/mapped-during-run.txt
: > "$MAPFILE"
(
  end=$((SECONDS+120))
  while [ $SECONDS -lt $end ]; do
    for p in $(pgrep -f 'fused_e2e\.py'; pgrep -f 'ane-worker/mlx-omarchy-ane-worker'); do
      grep -hoE '/[^ ]*(libvulkan[^ ]*asahi[^ ]*|libmlx\.so|libane\.so)' "/proc/$p/maps" 2>/dev/null | \
        sed -u "s/^/pid=$p /" >> "$MAPFILE"
    done
    sleep 0.2
  done
) &
MAPPER=$!

# --- the run ---
$PY "$RUN/fused_e2e.py" \
  --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
  --golden /var/tmp/EncoderParityAne/capture \
  --model "$MODEL" \
  --pkg /var/tmp/TdtLoopDefault/pkg \
  --encoder-runner "$RUNNER" \
  --source /var/tmp/IslandsExecJwm1/encoder-source \
  --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
  --bundles /var/tmp/jwm1-ane-step2/bundles \
  --worker "$WORKER" \
  --libane "$LIBANE" \
  --scratch "$SCRATCH" --out "$OUT" \
  --deadline-ms 20000 > "$OUT/stdout.log" 2>&1
RC=$?

# wait for at least one full poll cycle past run end, then stop mapper by bounded design
sleep 1
kill -TERM "$MAPPER" 2>/dev/null
wait "$MAPPER" 2>/dev/null
sort -u "$MAPFILE" -o "$MAPFILE"

# --- post-run identity + verdict ---
{
  echo "rc: $RC"
  date -Ins
  sha256sum "$WORKER" "$LIBANE" "$LIBMLX" "$CORE" "$DRIVER" "$RUNNER" "$RUN/fused_e2e.py" "$PY"
  echo "driver-buildid: $(readelf -n "$DRIVER" | sed -n 's/.*Build ID: //p')"
} > "$ID/identity-post.txt" 2>&1

MEL=5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde
HID=38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7
TRX=db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790
{
  sha256sum "$OUT/mel.npy" "$OUT/encoder_hidden.npy" "$OUT/transcript.txt" "$OUT/token_ids.json" "$OUT/e2e-report.json" 2>&1
  echo "golden-mel-match:    $( [ "$(sha256sum "$OUT/mel.npy" | cut -d" " -f1)" = "$MEL" ] && echo YES || echo NO )"
  echo "golden-hidden-match: $( [ "$(sha256sum "$OUT/encoder_hidden.npy" | cut -d" " -f1)" = "$HID" ] && echo YES || echo NO )"
  echo "golden-transcript-match: $( [ "$(sha256sum "$OUT/transcript.txt" | cut -d" " -f1)" = "$TRX" ] && echo YES || echo NO )"
  "$PY" - "$OUT/e2e-report.json" <<'PYX'
import json,sys
r=json.load(open(sys.argv[1]))
ex=r["execution"]
for l in json.dumps(r).split(","):
    if "matching_prefix_length" in l or "_emissions" in l:
        print(l.strip()[:120])
print("status:", r["status"])
print("cpu_tensor_events:", ex.get("cpu_tensor_events"), "ane_submissions:", r["ane"].get("submissions"), "worker_starts:", r["ane"].get("worker_starts"), "timeouts:", r["ane"].get("timeouts"))
print("total_pipeline_ms:", r["timing"].get("total_pipeline_ms"))
PYX
} > "$ID/verdict.txt" 2>&1

echo "=== REPEAT2 DONE rc=$RC out=$OUT ==="
cat "$ID/verdict.txt"
echo "=== distinct mapped libraries (pid-tagged, deduped) ==="
sort -u "$MAPFILE" | head -40
echo "=== driver-in-runner proof ==="
grep -c "libvulkan_asahi-e167" "$MAPFILE"
