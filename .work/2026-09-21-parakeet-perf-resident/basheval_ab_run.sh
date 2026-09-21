#!/bin/bash
# basheval_ab_run.sh — Paired interleaved A/B for the batch-eval lever.
#   R1 = BASE (vulkan_encoder.py unmodified)
#   R2 = LEVER (vulkan_encoder_basheval_wrapper.py, single mx.eval per round)
#   R3 = LEVER
#   R4 = BASE
# Warm + 5 measured per pass, ALL runs kept, 104 pins + golden sha per run.
# Pre-registered decision rule: |lever_pooled - base_pooled| < 3.7% (~190ms)
# => NEUTRAL. Additionally compare marshal wall directly per pass.
set -uo pipefail

LOCK=/tmp/m1-gpu.lock
LOCK_TIMEOUT_S=1200
TS=$(date +%Y%m%dT%H%M%S)
BASE=/var/tmp/ane-runtime/fused-e2e/basheval-$TS
LOG=$BASE/run.log
mkdir -p "$BASE"

exec 9>"$LOCK"
echo "BASHEVAL_ACQUIRE $(date -u -Ins) inode=$(stat -c %i $LOCK)" >> "$LOG"
if ! flock -w $LOCK_TIMEOUT_S 9; then echo "LOCK_FAIL" >> "$LOG"; exit 2; fi
echo "BASHEVAL_LOCK_HELD $(date -u -Ins)" >> "$LOG"

export VK_DRIVER_FILES=/tmp/mesa-icd-overlay/m1-test-host-e167-icd.json
export MLX_OMARCHY_PLACED=AC
unset PYTHONPATH LD_LIBRARY_PATH HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL MLX_OMARCHY_SPIRV_CACHE || true

PY=/var/tmp/runtime-venv/venv/bin/python3
MODEL=<model-cache>/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
RUN=/var/tmp/ane-runtime/fused-e2e/fused_e2e.py
WORKER=/var/tmp/ane-runtime/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=/var/tmp/ane-runtime/libane.so
RUNNER_BASE=/var/tmp/encoder-overlay/base/vulkan_encoder.py
RUNNER_LEVER=/tmp/parakeet-perf-resident/vulkan_encoder_basheval_wrapper.py

run_pass () { # label runner
  local label=$1 runner=$2
  local pbase=$BASE/$label
  mkdir -p "$pbase"
  {
    echo "=== IDENTITY $label ==="; date -u -Ins; hostname
    echo "runner=$runner"; sha256sum "$runner" "$WORKER" "$LIBANE" | sed 's|/var/tmp/||;s|/tmp/parakeet-perf-resident/||'
  } > "$pbase/identity.txt"
  run_one () {
    local name=$1
    local out=$pbase/out-$name scratch=$pbase/scratch-$name
    rm -rf "$out" "$scratch"; mkdir -p "$out" "$scratch"
    "$PY" "$RUN" \
      --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
      --golden /var/tmp/EncoderParityAne/capture \
      --model "$MODEL" \
      --pkg /var/tmp/TdtLoopDefault/pkg \
      --encoder-runner "$runner" \
      --source /var/tmp/IslandsExecM1TestHost/encoder-source \
      --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
      --bundles /var/tmp/ane-runtime/bundles \
      --worker "$WORKER" \
      --libane "$LIBANE" \
      --scratch "$scratch" --out "$out" \
      --deadline-ms 20000 > "$pbase/log-$name.txt" 2>&1
    [ $? -ne 0 ] && { echo "RUN-FAILED $label/$name"; tail -4 "$pbase/log-$name.txt"; return 3; }
    return 0
  }
  run_one warm || return 3
  for i in 1 2 3 4 5; do run_one "meas-$i" || return 3; done
  echo "$label done $(date -u -Ins)" >> "$LOG"
  return 0
}

run_pass R1-base "$RUNNER_BASE";  RC=$?
run_pass R2-lever "$RUNNER_LEVER"; RC=$((RC+$?))
run_pass R3-lever "$RUNNER_LEVER"; RC=$((RC+$?))
run_pass R4-base  "$RUNNER_BASE";  RC=$((RC+$?))

"$PY" - "$BASE" <<'PYEOF'
import glob, hashlib, json, statistics, sys
base = sys.argv[1]
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
def collect(label):
    rows = []
    for d in sorted(glob.glob(f"{base}/{label}/out-meas-*")):
        r = json.load(open(d+"/e2e-report.json"))
        st = {s["stage"]: s.get("wall_ms") for s in r.get("stages", [])}
        gold = (sha(d+"/mel.npy")==MEL, sha(d+"/encoder_hidden.npy")==HID, sha(d+"/transcript.txt")==TRX)
        rows.append({"encoder_ane_ms": st.get("encoder_ane"), "total_ms": r.get("timing",{}).get("total_pipeline_ms"),
                     "goldens": all(gold), "status": r.get("status"),
                     "mel_frontend_ms": st.get("mel_frontend")})
    return rows
R1=collect("R1-base"); R2=collect("R2-lever"); R3=collect("R3-lever"); R4=collect("R4-base")
def med(rs): return statistics.median([r["encoder_ane_ms"] for r in rs])
base_pooled = statistics.median([r["encoder_ane_ms"] for r in R1+R4])
lever_pooled = statistics.median([r["encoder_ane_ms"] for r in R2+R3])
result = {
  "schema": "m1-test-host-basheval-ab/1",
  "order": "R1-base,R2-lever,R3-lever,R4-base (interleaved counterbalanced)",
  "all_runs_kept": True,
  "arms": {k: {"n": len(v), "encoder_ane_median_ms": med(v),
               "all_gates": all(r["goldens"] and r["status"]=="match" for r in v)}
           for k, v in [("R1_base",R1),("R2_lever",R2),("R3_lever",R3),("R4_base",R4)]},
  "paired": {
    "base_pooled_median_ms": base_pooled,
    "lever_pooled_median_ms": lever_pooled,
    "lever_delta_ms": lever_pooled - base_pooled,
    "R1_vs_R4_drift_ms": med(R4) - med(R1),
    "R2_vs_R3_drift_ms": med(R3) - med(R2),
  },
  "noise_band_ms": 190,
  "decision_rule": "|lever_delta| < 190 => NEUTRAL; lever_delta < -190 => real win; > +190 => regression",
}
json.dump(result, open(base+"/basheval-summary.json","w"), indent=1)
print(json.dumps({k: result[k] for k in ("arms","paired","noise_band_ms","decision_rule")}, indent=1))
PYEOF
RC=$((RC+$?))
echo "BASHEVAL_RELEASE $(date -u -Ins) rc=$RC" >> "$LOG"
flock -u 9
echo "=== BASHEVAL_DONE BASE=$BASE rc=$RC ==="
exit $RC
