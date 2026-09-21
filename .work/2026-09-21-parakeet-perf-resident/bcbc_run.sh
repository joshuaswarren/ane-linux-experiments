#!/bin/bash
# bcbc_run.sh — Interleaved B/C/C/B replication on m1-test-host.
#
# Per Main directive: ONE short interleaved run, order B -> C -> C -> B
# (counterbalanced), warm + 5 measured each, ALL runs kept (no runs2-5
# cherry-pick), ANE_RESIDENT_PROFILE=1 for per-segment stdout cost.
#
# Decision rule (pre-registered): compare PAIRED matched medians
# B1 vs B2 and C1 vs C2, and the interleaved C-vs-B median across all
# 20 measured runs. If |delta| < noise band (3.7% of stage => ~190 ms),
# label NEUTRAL and keep the bench receipt only.
set -uo pipefail

LOCK=/tmp/m1-gpu.lock
LOCK_TIMEOUT_S=1200
TS=$(date +%Y%m%dT%H%M%S)
BASE=/var/tmp/ane-runtime/fused-e2e/bcbc-$TS
LOG=$BASE/run.log
mkdir -p "$BASE"

exec 9>"$LOCK"
echo "BCBC_ACQUIRE $(date -u -Ins) inode=$(stat -c %i $LOCK)" >> "$LOG"
if ! flock -w $LOCK_TIMEOUT_S 9; then
  echo "BCBC_LOCK_FAIL" >> "$LOG"; exit 2
fi
echo "BCBC_LOCK_HELD $(date -u -Ins)" >> "$LOG"

export VK_DRIVER_FILES=/tmp/mesa-icd-overlay/m1-test-host-e167-icd.json
export MLX_OMARCHY_PLACED=AC
export ANE_RESIDENT_PROFILE=1
unset PYTHONPATH LD_LIBRARY_PATH HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL MLX_OMARCHY_SPIRV_CACHE || true

PY=/var/tmp/runtime-venv/venv/bin/python3
MODEL=<model-cache>/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
RUN=/var/tmp/ane-runtime/fused-e2e/fused_e2e.py
LIBANE=/var/tmp/ane-runtime/libane.so
RUNNER=/var/tmp/encoder-overlay/base/vulkan_encoder.py

# Worker wrappers (LD_LIBRARY_PATH isolated to the worker process)
mkdir -p /tmp/parakeet-perf-resident/wrapped
cat > /tmp/parakeet-perf-resident/wrapped/worker-tools <<'EOF'
#!/bin/bash
export LD_LIBRARY_PATH=/tmp/parakeet-perf-resident/build-lever
exec /tmp/parakeet-perf-resident/mlx-omarchy-ane-worker-tools "$@"
EOF
cat > /tmp/parakeet-perf-resident/wrapped/worker-lever <<'EOF'
#!/bin/bash
export LD_LIBRARY_PATH=/tmp/parakeet-perf-resident/build-lever
exec /tmp/parakeet-perf-resident/mlx-omarchy-ane-worker-lever "$@"
EOF
chmod +x /tmp/parakeet-perf-resident/wrapped/worker-tools /tmp/parakeet-perf-resident/wrapped/worker-lever

WORKER_B=/tmp/parakeet-perf-resident/wrapped/worker-tools
WORKER_C=/tmp/parakeet-perf-resident/wrapped/worker-lever

run_pass () { # label worker
  local label=$1 worker=$2
  local pbase=$BASE/$label
  mkdir -p "$pbase"
  {
    echo "=== IDENTITY $label ==="; date -u -Ins; hostname
    echo "worker=$worker"; sha256sum "$worker" "$LIBANE" | sed 's|/tmp/parakeet-perf-resident/||'
    echo "ANE_RESIDENT_PROFILE=1"
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
      --encoder-runner "$RUNNER" \
      --source /var/tmp/IslandsExecM1TestHost/encoder-source \
      --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
      --bundles /var/tmp/ane-runtime/bundles \
      --worker "$worker" \
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

# Interleaved order: B1, C1, C2, B2
run_pass B1 "$WORKER_B"; RC=$?
run_pass C1 "$WORKER_C"; RC=$((RC + $?))
run_pass C2 "$WORKER_C"; RC=$((RC + $?))
run_pass B2 "$WORKER_B"; RC=$((RC + $?))

# Paired analysis across ALL 20 measured runs
"$PY" - "$BASE" <<'PYEOF'
import glob, hashlib, json, statistics, sys
base = sys.argv[1]
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()

def collect(label):
    rows, seg = [], {"first_byte": [], "output_read": [], "write_call": [], "trailing": []}
    for d in sorted(glob.glob(f"{base}/{label}/out-meas-*")):
        r = json.load(open(d+"/e2e-report.json"))
        st = {s["stage"]: s.get("wall_ms") for s in r.get("stages", [])}
        gold = (sha(d+"/mel.npy")==MEL, sha(d+"/encoder_hidden.npy")==HID, sha(d+"/transcript.txt")==TRX)
        rows.append({"run": d.rsplit("out-",1)[1], "encoder_ane_ms": st.get("encoder_ane"),
                     "total_ms": r.get("timing",{}).get("total_pipeline_ms"),
                     "goldens": all(gold), "status": r.get("status")})
        # per-segment from ane.log profiles
        for entry in r.get("ane", {}).get("log", []):
            prof = entry.get("profile", {})
            sp = prof.get("session_profile")
            if sp:
                seg["first_byte"].append(sp.get("first_byte_ns", 0)/1e6)
                seg["output_read"].append(sp.get("output_read_ns", 0)/1e6)
                seg["write_call"].append(sp.get("write_call_ns", 0)/1e6)
                seg["trailing"].append(sp.get("trailing_ns", 0)/1e6)
    return rows, seg

B1, segB1 = collect("B1"); C1, segC1 = collect("C1")
C2, segC2 = collect("C2"); B2, segB2 = collect("B2")

def med(rs): return statistics.median([r["encoder_ane_ms"] for r in rs])
def segmed(s): return statistics.median(s) if s else None

result = {
  "schema": "m1-test-host-bcbc-replication/1",
  "order": "B1,C1,C2,B2 (interleaved, counterbalanced)",
  "all_runs_kept": True,
  "arms": {k: {"n": len(v), "encoder_ane_median_ms": med(v),
               "all_gates": all(r["goldens"] and r["status"]=="match" for r in v),
               "runs": v}
           for k, v in [("B1",B1),("C1",C1),("C2",C2),("B2",B2)]},
  "paired": {
    "B_pooled_median_ms": statistics.median([r["encoder_ane_ms"] for r in B1+B2]),
    "C_pooled_median_ms": statistics.median([r["encoder_ane_ms"] for r in C1+C2]),
    "B1_vs_B2_delta_ms": med(B2) - med(B1),
    "C1_vs_C2_delta_ms": med(C2) - med(C1),
    "C_vs_B_pooled_delta_ms": statistics.median([r["encoder_ane_ms"] for r in C1+C2]) - statistics.median([r["encoder_ane_ms"] for r in B1+B2]),
  },
  "per_segment_stdout_cost_ms": {
    "B_pooled": {k: segmed(segB1[k]+segB2[k]) for k in segB1},
    "C_pooled": {k: segmed(segC1[k]+segC2[k]) for k in segC1},
  },
  "noise_band_ms": 190,  # 3.7% of ~5150 ms stage
  "decision_rule": "if abs(C_vs_B_pooled_delta_ms) < noise_band_ms => NEUTRAL (bench receipt only, no perf claim)",
}
json.dump(result, open(base+"/bcbc-summary.json","w"), indent=1)
print(json.dumps({k: result[k] for k in ("paired","per_segment_stdout_cost_ms","noise_band_ms","decision_rule")}, indent=1))
PYEOF
RC=$((RC + $?))

echo "BCBC_RELEASE $(date -u -Ins) rc=$RC" >> "$LOG"
flock -u 9
echo "=== BCBC_DONE BASE=$BASE rc=$RC ==="
exit $RC
