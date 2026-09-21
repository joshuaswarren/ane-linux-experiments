#!/bin/bash
# basheval_confirm_run.sh — Randomized counterbalanced confirmation trial
# for the batch-eval lever (Main-authorized 2026-09-21).
#
# Design: 6 passes (3 base, 3 lever), order pre-generated with documented
# seed (random.seed(20260921), shuffled ['base','lever']*3):
#   P1=lever P2=base P3=base P4=lever P5=base P6=lever
# Warm + 5 measured per pass; ALL 30 measured runs kept; 104 pins +
# three golden hashes bit-exact per run. Report RAW per-pass and pooled
# medians — no threshold verdict, effect + uncertainty only.
set -uo pipefail

LOCK=/tmp/m1-gpu.lock
LOCK_TIMEOUT_S=1800
TS=$(date +%Y%m%dT%H%M%S)
BASE=/var/tmp/jwm1-ane-step2/fused-e2e/confirm-$TS
LOG=$BASE/run.log
mkdir -p "$BASE"

exec 9>"$LOCK"
echo "CONFIRM_ACQUIRE $(date -u -Ins) inode=$(stat -c %i $LOCK)" >> "$LOG"
if ! flock -w $LOCK_TIMEOUT_S 9; then echo "LOCK_FAIL" >> "$LOG"; exit 2; fi
echo "CONFIRM_LOCK_HELD $(date -u -Ins)" >> "$LOG"

export VK_DRIVER_FILES=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json
export MLX_OMARCHY_PLACED=AC
unset PYTHONPATH LD_LIBRARY_PATH HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL MLX_OMARCHY_SPIRV_CACHE || true

PY=/var/tmp/jwm1-v072rc1/venv/bin/python3
MODEL=/home/joshuawarren/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
RUN=/var/tmp/jwm1-ane-step2/fused-e2e/fused_e2e.py
WORKER=/var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=/var/tmp/jwm1-ane-step2/libane.so
RUNNER_BASE=/var/tmp/encwall-v071/base/vulkan_encoder.py
RUNNER_LEVER=/tmp/parakeet-perf-resident/vulkan_encoder_basheval_wrapper.py

ORDER=(lever base base lever base lever)

run_pass () { # idx label runner
  local idx=$1 label=$2 runner=$3
  local pbase=$BASE/P${idx}-$label
  mkdir -p "$pbase"
  {
    echo "=== IDENTITY P${idx}-$label ==="; date -u -Ins; hostname
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
      --source /var/tmp/IslandsExecJwm1/encoder-source \
      --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
      --bundles /var/tmp/jwm1-ane-step2/bundles \
      --worker "$WORKER" \
      --libane "$LIBANE" \
      --scratch "$scratch" --out "$out" \
      --deadline-ms 20000 > "$pbase/log-$name.txt" 2>&1
    [ $? -ne 0 ] && { echo "RUN-FAILED P${idx}-$label/$name"; tail -4 "$pbase/log-$name.txt"; return 3; }
    return 0
  }
  run_one warm || return 3
  for i in 1 2 3 4 5; do run_one "meas-$i" || return 3; done
  echo "P${idx}-$label done $(date -u -Ins)" >> "$LOG"
  return 0
}

RC=0
for idx in 1 2 3 4 5 6; do
  arm=${ORDER[$((idx-1))]}
  if [ "$arm" = "base" ]; then runner=$RUNNER_BASE; else runner=$RUNNER_LEVER; fi
  run_pass "$idx" "$arm" "$runner"; RC=$((RC+$?))
done

"$PY" - "$BASE" <<'PYEOF'
import glob, hashlib, json, statistics, sys
base = sys.argv[1]
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
passes = {}
for pd_ in sorted(glob.glob(base+"/P*")):
    label = pd_.rsplit("/",1)[1]
    arm = "lever" if "lever" in label else "base"
    rows = []
    for d in sorted(glob.glob(pd_+"/out-meas-*")):
        r = json.load(open(d+"/e2e-report.json"))
        st = {s["stage"]: s.get("wall_ms") for s in r.get("stages", [])}
        gold = (sha(d+"/mel.npy")==MEL, sha(d+"/encoder_hidden.npy")==HID, sha(d+"/transcript.txt")==TRX)
        rows.append({"encoder_ane_ms": st.get("encoder_ane"), "goldens": all(gold), "status": r.get("status")})
    passes[label] = {"arm": arm, "rows": rows}
per_pass = {k: {"arm": v["arm"],
                "median_ms": statistics.median([r["encoder_ane_ms"] for r in v["rows"]]),
                "all_gates": all(r["goldens"] and r["status"]=="match" for r in v["rows"]),
                "n": len(v["rows"])}
            for k, v in sorted(passes.items())}
base_vals = [r["encoder_ane_ms"] for v in passes.values() if v["arm"]=="base" for r in v["rows"]]
lever_vals = [r["encoder_ane_ms"] for v in passes.values() if v["arm"]=="lever" for r in v["rows"]]
summary = {
  "schema": "jwm1-basheval-confirm/1",
  "seed": 20260921,
  "order": ["lever","base","base","lever","base","lever"],
  "all_runs_kept": True,
  "per_pass": per_pass,
  "pooled": {
    "base_n": len(base_vals), "lever_n": len(lever_vals),
    "base_median_ms": statistics.median(base_vals),
    "lever_median_ms": statistics.median(lever_vals),
    "delta_median_ms": statistics.median(lever_vals) - statistics.median(base_vals),
    "base_min_ms": min(base_vals), "base_max_ms": max(base_vals),
    "lever_min_ms": min(lever_vals), "lever_max_ms": max(lever_vals),
    "overlap": bool(max(lever_vals) > min(base_vals)),
  },
  "note": "RAW medians only - no threshold verdict. Effect + uncertainty reported; landing decision per Main on robustness.",
}
json.dump(summary, open(base+"/confirm-summary.json","w"), indent=1)
print(json.dumps(summary, indent=1))
PYEOF
RC=$((RC+$?))
echo "CONFIRM_RELEASE $(date -u -Ins) rc=$RC" >> "$LOG"
flock -u 9
echo "=== CONFIRM_DONE BASE=$BASE rc=$RC ==="
exit $RC
