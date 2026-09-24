#!/bin/bash
# combined-parakeet.sh <t6001-host|t8103-host>
#
# One combined Parakeet pipeline on the recovered levers:
#   whole-encoder ANE (868fa7f1e, bundle 13c74423, one submit)
#   + host-TDT control loop      (MLX_OMARCHY_TDT_HOST=1  -> control "host")
#   + defer-commit submit batching (MLX_OMARCHY_DEFER_COMMIT=1, eval.cpp 8bba36b21)
#   + decoder/joint + detok       (fused_e2e stages, unchanged)
#
# Source branch: mlx-omarchy agent/combined-parakeet @ 8bba36b21.
# Runs 3 gated reps under /tmp/m1-gpu.lock; never steals or unlinks the lock.
# Neutral host tags: t6001-host (alias m1max-host), t8103-host (alias m1-host).
set -uo pipefail
TAG="${1:?usage: combined-parakeet.sh <t6001-host|t8103-host>}"

case "$TAG" in
  t6001-host)
    W=/var/tmp/encoder-whole
    E2E=${COMBINED_E2E:-/var/tmp/ParakeetE2EJw16/fused_e2e.py}
    SRC=${COMBINED_SRC:-/var/tmp/EncoderParityAne/encoder-source}
    BUNDLES=/var/tmp/island-reexport/bundles
    REF=/var/tmp/EncoderParityAne/out-ane/encoder_hidden.npy
    PY=${COMBINED_PY:-/var/tmp/combined-venv/bin/python3}
    SITE=/var/tmp/E2EREV/site:/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
    ;;
  t8103-host)
    W=/var/tmp/encoder-whole-m1-host
    E2E=${COMBINED_E2E:-/var/tmp/m1-host-ane-step2/fused-e2e/fused_e2e.py}
    SRC=${COMBINED_SRC:-/var/tmp/IslandsExecM1Host/encoder-source}
    BUNDLES=/var/tmp/m1-host-ane-step2/bundles
    REF=""
    PY=${COMBINED_PY:-/var/tmp/combined-venv/bin/python3}
    SITE=/var/tmp/E2EREV/site
    ;;
  *) echo "unknown host tag '$TAG'" >&2; exit 64 ;;
esac

RUNNER=$W/mlx/tools/coreml/vulkan_encoder.py
WORKER=$W/build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=$W/libane-strict.so
PKG=${COMBINED_PKG:-/var/tmp/TdtLoopDefault/pkg}
AUDIO=/var/tmp/ParakeetE2E/audio/fixture.flac
GOLDEN=/var/tmp/EncoderParityAne/capture
MODEL=$HOME/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
BUNDLE=$W/bundle
P=$W/combined-$(date +%Y%m%dT%H%M%S)
mkdir -p "$P"; fail=0

# ---- preflight ---------------------------------------------------------
echo "=== preflight $(date -Iseconds) ==="
for f in "$PY" "$E2E" "$RUNNER" "$WORKER" "$LIBANE" "$PKG/coreml/parakeet_tdt.py" \
         "$AUDIO" "$MODEL" "$GOLDEN/encoder_hidden.npy" "$BUNDLE/program-0.anec" "$SRC/model.mil"; do
  [ -e "$f" ] || { echo "MISSING $f"; fail=1; }
done
[ $fail -ne 0 ] && { echo PREFLIGHT-FAIL; exit 9; }
{ date -Ins; hostname; sha256sum "$BUNDLE/program-0.anec" "$LIBANE" "$WORKER" "$E2E" "$RUNNER"; } | tee "$P/identity.txt"

# wheel must carry the defer-commit lineage (built at 8bba36b21 stamps +8bba36b2;
# the original T6001-host defer wheel stamps +925cfa6)
WHEEL_OK=$("$PY" -m pip show mlx-omarchy 2>/dev/null | sed -n 's/^Version: //p')
case "$WHEEL_OK" in
  *8bba36b2*|*925cfa6*) echo "wheel: $WHEEL_OK (defer-commit lineage)" ;;
  *) if [ "${COMBINED_WHEEL_ALLOW:-0}" = 1 ]; then
       echo "WARNING: wheel '$WHEEL_OK' not recognized as defer-commit lineage (allowed by COMBINED_WHEEL_ALLOW)"
     else
       echo "FAIL: mlx-omarchy wheel '$WHEEL_OK' lacks defer-commit lineage stamp (8bba36b2|925cfa6)."
       echo "Build: git -C ~/src/mlx-omarchy worktree add /var/tmp/combined-src agent/combined-parakeet"
       echo "       bash /var/tmp/combined-src/scripts/build-wheel.sh && python3 -m venv /var/tmp/combined-venv"
       echo "       /var/tmp/combined-venv/bin/pip install /var/tmp/combined-src/dist/*.whl numpy soundfile"
       exit 9
     fi ;;
esac

grep -q "MLX_OMARCHY_TDT_HOST" "$PKG/coreml/parakeet_tdt.py" \
  || { echo "FAIL: pkg $PKG has no TDT_HOST knob (needs the 992feea98-era coreml tools)"; exit 9; }

# ---- env: the combined configuration ------------------------------------
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
export MLX_OMARCHY_WHOLE_ENCODER_BUNDLE=$BUNDLE
export ANE_ISLAND_MODE=resident-batch
export MLX_OMARCHY_TDT_HOST=1        # host control loop -> report control "host"
export MLX_OMARCHY_DEFER_COMMIT=1    # keep one command buffer across TDT-step graph evals
export MLX_OMARCHY_SPIRV_CACHE=$P/spirv   # lane-local; rep 1 pays the one-time compile
[ -d "$SITE" ] && export PYTHONPATH="$SITE${PYTHONPATH:+:$PYTHONPATH}"

# ---- E2E x3 -------------------------------------------------------------
echo "=== combined E2E x3 $(date -Iseconds) ==="
for r in 1 2 3; do
  echo "--- rep $r $(date -Iseconds) ---"
  rm -rf "$P/out-$r" "$P/scratch-$r"; mkdir -p "$P/out-$r" "$P/scratch-$r"
  REFARGS=(); [ -n "$REF" ] && REFARGS=(--ane-reference "$REF")
  T0=$(date +%s.%N)
  flock -w 1200 /tmp/m1-gpu.lock \
    "$PY" "$E2E" \
      --audio "$AUDIO" --golden "$GOLDEN" --model "$MODEL" --pkg "$PKG" \
      --encoder-runner "$RUNNER" --source "$SRC" --bundles "$BUNDLES" \
      --worker "$WORKER" --libane "$LIBANE" \
      "${REFARGS[@]}" \
      --scratch "$P/scratch-$r" --out "$P/out-$r" \
      --deadline-ms 20000 > "$P/e2e-r$r.log" 2>&1
  rc=$?; T1=$(date +%s.%N)
  echo "rep$r rc=$rc wall_ms=$(echo "($T1-$T0)*1000" | bc)"
  [ $rc -ne 0 ] && fail=1 && tail -20 "$P/e2e-r$r.log"
done

# ---- identity + summary -------------------------------------------------
echo "=== identity $(date -Iseconds) ==="
sha256sum "$P"/out-*/encoder_hidden.npy "$P"/out-1/transcript.txt 2>/dev/null
"$PY" - "$P" <<'EOF'
import glob, hashlib, json, sys
base = sys.argv[1]
TRX = "db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
for d in sorted(glob.glob(base + "/out-*/e2e-report.json")):
    r = json.load(open(d))
    stages = {s["stage"]: s.get("wall_ms") for s in r.get("stages", [])}
    trx = hashlib.sha256(open(d.rsplit("/", 1)[0] + "/transcript.txt", "rb").read()).hexdigest()
    print(json.dumps({
        "rep": d.split("/out-")[1].split("/")[0],
        "status": r.get("status"),
        "control": r.get("execution", {}).get("control"),
        "ane_exec_ms": r.get("ane", {}).get("exec_ms"),
        "submissions": r.get("ane", {}).get("submissions"),
        "cpu_tensor_events": r.get("execution", {}).get("cpu_tensor_events"),
        "prefix": r.get("matching_prefix_length"),
        "emissions": r.get("actual_emissions"),
        "transcript_match": r.get("layers", {}).get("layer_7_end_to_end_text", {}).get("transcript_match"),
        "transcript_sha_ok": trx == TRX,
        "stages_ms": {k: stages.get(k) for k in
                      ("audio_load", "mel_frontend", "encoder_ane", "decoder_load", "tdt_decode", "detokenize")},
        "total_pipeline_ms": r.get("timing", {}).get("total_pipeline_ms"),
    }, sort_keys=True))
EOF
echo "FAIL=$fail exit_marker $(date -Iseconds) out=$P"
exit $fail
