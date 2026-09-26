#!/bin/bash
# run-profile.sh — one fused_e2e_trace run under /tmp/m1-gpu.lock with
# gpu_scheduler + dma_fence ftrace and PARAKEET_* stage markers, mono clock.
# Same env/args discipline as run-contract.sh; resident worker pre-warmed so
# the encoder stage window is clean; llm-inference stopped/restored + probe.
# The measured pipeline runs as root because trace_marker needs
# CAP_SYS_ADMIN; outputs are chowned back to joshuawarren.
set -uo pipefail
R=/var/tmp/parakeet-recover
PY=/var/tmp/v072-venv-fused/bin/python3
E2E=$R/fused_e2e_trace.py
RUNNER=$R/ane_whole_worker_resident.py
BUNDLES=$R/bundles
SRC=$R/encoder-source
REF=$R/ane-reference/encoder_hidden.npy
AUDIO=$R/audio/fixture.flac
GOLDEN=$R/capture
PKG=$R/pkg
MODEL=$HOME/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
W_ENC=/var/tmp/encoder-whole
WORKER=$W_ENC/build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=$W_ENC/libane-strict.so
[ -x "$WORKER" ] || WORKER=$R/fallback-worker/worker-binary
[ -e "$LIBANE" ] || LIBANE=$R/fallback-worker/libane-strict.so
SHIM=$R/libane_inproc.so
TS=$(date +%Y%m%dT%H%M%S)
BASE=$R/profile-$TS
mkdir -p "$BASE"
fail=0
for f in "$PY" "$E2E" "$RUNNER" "$PKG/coreml/parakeet_tdt.py" "$AUDIO" "$MODEL" \
         "$GOLDEN/encoder_hidden.npy" "$GOLDEN/mel.npy" "$GOLDEN/transcript.txt" "$WORKER" "$LIBANE" "$SHIM" "$REF"; do
  [ -e "$f" ] || { echo "MISSING $f"; fail=1; }
done
[ $fail -ne 0 ] && { echo PREFLIGHT-FAIL; exit 9; }
{ date -Ins; hostname; id -u; sha256sum "$PY" "$E2E" "$RUNNER" "$SHIM" "$WORKER" "$LIBANE" "$AUDIO"; } > "$BASE/identity.txt" 2>&1

restore_service () {
  echo "=== restore llm-inference $(date -Iseconds) ==="
  sudo systemctl start llm-inference.service
  local ok=""
  for i in $(seq 1 45); do
    if curl -sf -m 3 http://127.0.0.1:8002/health >/dev/null 2>&1; then ok=1; break; fi
    sleep 2
  done
  [ -n "$ok" ] && echo "health: 200" || { echo "health: FAILED"; return 1; }
  local key rc
  key=$(sudo cat /etc/llm-inference/api-key) || return 1
  rc=$(curl -sS -m 60 http://127.0.0.1:8002/v1/chat/completions \
    -H "Authorization: Bearer $key" -H 'Content-Type: application/json' \
    -d '{"model":"default","messages":[{"role":"user","content":"Say Pacific"}],"max_tokens":8}' \
    | "$PY" -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['finish_reason'])" 2>/dev/null)
  echo "completion probe finish: ${rc:-FAILED}"
}
trap 'restore_service; "$PY" "$RUNNER" --shutdown || true' EXIT

echo "=== stop llm-inference $(date -Iseconds) ==="
sudo systemctl stop llm-inference.service
sleep 2

# Pre-warm the resident daemon so the encoder stage window is pure submit.
"$PY" - <<'PYEOF' || exit 3
import sys
sys.path.insert(0, "/var/tmp/parakeet-recover")
import ane_whole_worker_resident as r
r.ensure_daemon("/var/tmp/encoder-whole/build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker",
                "/var/tmp/encoder-whole/libane-strict.so",
                "/var/tmp/encoder-whole/bundle", 20000)
print("daemon pid:", r.daemon_pid())
PYEOF

echo "prewarm done $(date -Iseconds)"
echo "=== ftrace on $(date -Iseconds) ==="
sudo -n sh -c '
set -e
T=/sys/kernel/tracing
echo 0 > $T/tracing_on
echo mono > $T/trace_clock
echo 16384 > $T/buffer_size_kb
echo 0 > $T/events/gpu_scheduler/enable
echo 0 > $T/events/dma_fence/enable
echo > $T/trace
echo 1 > $T/events/gpu_scheduler/enable
echo 1 > $T/events/dma_fence/enable
echo 1 > $T/tracing_on
'
echo "PROBE_MARK transport" | sudo -n tee /sys/kernel/tracing/trace_marker > /dev/null

flock -w 900 /tmp/m1-gpu.lock \
sudo -n env -u PYTHONPATH -u LD_LIBRARY_PATH -u MLX_OMARCHY_GATED_BARRIERS \
  -u MLX_OMARCHY_GPU_PROFILE -u ANE_OP_WALL -u MLX_OMARCHY_SPIRV_CACHE \
  HOME="$HOME" PARAKEET_TRACE_MARKER=/sys/kernel/tracing/trace_marker \
  MLX_OMARCHY_PLACED=AC ANE_ISLAND_MODE=inprocess ANE_INPROC_SHIM="$SHIM" \
  MLX_OMARCHY_FUSED_AB=0 MLX_OMARCHY_PIPE_OPS= MLX_OMARCHY_DEFER_COMMIT=1 \
  "$PY" "$E2E" \
  --audio "$AUDIO" --golden "$GOLDEN" --model "$MODEL" --pkg "$PKG" \
  --encoder-runner "$RUNNER" --source "$SRC" --ane-reference "$REF" \
  --bundles "$BUNDLES" --worker "$WORKER" --libane "$LIBANE" \
  --scratch "$BASE/scratch" --out "$BASE/out-trace" --deadline-ms 20000 --tdt-host \
  > "$BASE/log-trace.txt" 2>&1
rc=$?
sudo -n chown -R joshuawarren:joshuawarren "$BASE"

echo "=== ftrace off $(date -Iseconds) ==="
sudo -n sh -c '
set -e
T=/sys/kernel/tracing
echo 0 > $T/tracing_on
echo 0 > $T/events/gpu_scheduler/enable
echo 0 > $T/events/dma_fence/enable
cat $T/trace > '"$BASE"'/trace.txt
wc -l '"$BASE"'/trace.txt
'
sudo -n chown joshuawarren:joshuawarren "$BASE/trace.txt"
if [ $rc -ne 0 ]; then echo "RUN-FAILED rc=$rc"; tail -12 "$BASE/log-trace.txt"; exit 3; fi
echo "=== PROFILE DONE $BASE ==="
