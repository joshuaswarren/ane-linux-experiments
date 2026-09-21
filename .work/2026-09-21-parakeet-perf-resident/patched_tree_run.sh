#!/bin/bash
# patched_tree_run.sh — Run the ACTUAL patched runner (isolated tree) for
# 104 pins + time, and verify stage boundaries vs base trial data
# (no moved work outside encoder wall).
set -uo pipefail

LOCK=/tmp/m1-gpu.lock
TS=$(date +%Y%m%dT%H%M%S)
BASE=/var/tmp/m1-test-host-ane-step2/fused-e2e/patchedtree-$TS
LOG=$BASE/run.log
mkdir -p "$BASE"

exec 9>"$LOCK"
if ! flock -w 900 9; then echo "LOCK_FAIL"; exit 2; fi
echo "PATCHED_LOCK_HELD $(date -u -Ins)" >> "$LOG"

export VK_DRIVER_FILES=/tmp/mesa-sin-ftz-m1-test-host/m1-test-host-e167-icd.json
export MLX_OMARCHY_PLACED=AC
unset PYTHONPATH LD_LIBRARY_PATH HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL MLX_OMARCHY_SPIRV_CACHE || true

PY=/var/tmp/m1-test-host-v072rc1/venv/bin/python3
MODEL=$HOME/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
RUN=/var/tmp/m1-test-host-ane-step2/fused-e2e/fused_e2e.py
WORKER=/var/tmp/m1-test-host-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=/var/tmp/m1-test-host-ane-step2/libane.so
RUNNER_PATCHED=/tmp/parakeet-perf-resident/vulkan_encoder_batcheval_runtime.py

run_one () {
  local name=$1
  local out=$BASE/out-$name scratch=$BASE/scratch-$name
  rm -rf "$out" "$scratch"; mkdir -p "$out" "$scratch"
  "$PY" "$RUN" \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model "$MODEL" \
    --pkg /var/tmp/TdtLoopDefault/pkg \
    --encoder-runner "$RUNNER_PATCHED" \
    --source /var/tmp/IslandsExecm1-test-host/encoder-source \
    --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
    --bundles /var/tmp/m1-test-host-ane-step2/bundles \
    --worker "$WORKER" \
    --libane "$LIBANE" \
    --scratch "$scratch" --out "$out" \
    --deadline-ms 20000 > "$BASE/log-$name.txt" 2>&1
  [ $? -ne 0 ] && { echo "RUN-FAILED $name"; tail -4 "$BASE/log-$name.txt"; return 3; }
  return 0
}

run_one warm || { flock -u 9; exit 3; }
for i in 1 2 3 4 5; do run_one "meas-$i" || { flock -u 9; exit 3; }; done

"$PY" - "$BASE" <<'PYEOF'
import glob, hashlib, json, statistics, sys
base = sys.argv[1]
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
rows = []
for d in sorted(glob.glob(base+"/out-meas-*")):
    r = json.load(open(d+"/e2e-report.json"))
    st = {s["stage"]: s.get("wall_ms") for s in r.get("stages", [])}
    gold = (sha(d+"/mel.npy")==MEL, sha(d+"/encoder_hidden.npy")==HID, sha(d+"/transcript.txt")==TRX)
    rows.append({"encoder_ane_ms": st.get("encoder_ane"), "mel_frontend_ms": st.get("mel_frontend"),
                 "decoder_ms": st.get("decoder_infer", st.get("decoder")),
                 "tdt_ms": st.get("tdt_decode"), "total_ms": r.get("timing",{}).get("total_pipeline_ms"),
                 "goldens": all(gold), "status": r.get("status")})
enc = [r["encoder_ane_ms"] for r in rows]
mel = [r["mel_frontend_ms"] for r in rows if r["mel_frontend_ms"]]
summary = {
  "schema": "patched-tree-run/1",
  "runner": "vulkan_encoder_batcheval_runtime.py sha c7ba295c2a002372f8d3ed5e5417f1c5b82cb02a60d550c15bc234cc87748364",
  "n": len(rows),
  "encoder_ane_median_ms": statistics.median(enc),
  "all_gates": all(r["goldens"] and r["status"]=="match" for r in rows),
  "boundary_check": {
    "mel_frontend_median_ms": statistics.median(mel) if mel else None,
    "note": "compare vs base-trial mel_frontend median (~237-260ms band from today's base runs); encoder-wall-only change must not shift non-encoder stages",
  },
  "runs": rows,
}
json.dump(summary, open(base+"/patchedtree-summary.json","w"), indent=1)
print(json.dumps(summary, indent=1))
PYEOF
RC=$?
echo "PATCHED_RELEASE $(date -u -Ins) rc=$RC" >> "$LOG"
flock -u 9
echo "=== PATCHED_DONE BASE=$BASE rc=$RC ==="
exit $RC
