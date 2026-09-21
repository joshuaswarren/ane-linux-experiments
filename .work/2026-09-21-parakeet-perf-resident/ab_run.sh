#!/bin/bash
# ab_run.sh — A/B perf-battery for worker lever on jwm1.
#
# Three arms:
#   A: prebuilt worker 944f2a86... (parent re-confirm 2026-09-21 baseline = 5243.345)
#   B: new-built base worker fd97ebe0... (this build, no lever)
#   C: new-built LEVER worker (with _IONBF + dropped per-output fflush)
#
# Each arm: warm + 5 measured, AC placement, resident-batch transport.
# All gates: 104/104 + mel/hidden/transcript golden sha bit-exact.
#
# Lock: /tmp/m1-gpu.lock inode 27, 1500s ceiling.
set -uo pipefail

LOCK=/tmp/m1-gpu.lock
LOCK_TIMEOUT_S=2400
TS=$(date +%Y%m%dT%H%M%S)
BASE=/var/tmp/jwm1-ane-step2/fused-e2e/ab-$TS
LOG=$BASE/run.log
mkdir -p "$BASE"

exec 9>"$LOCK"
echo "AB_ACQUIRE_LOCK_ATTEMPT $(date -u -Ins) host=$(hostname) inode=$(stat -c %i $LOCK)" >> "$LOG"
if ! flock -w $LOCK_TIMEOUT_S 9; then
  echo "AB_LOCK_FAIL $(date -u -Ins)" >> "$LOG"
  exit 2
fi
echo "AB_LOCK_HELD $(date -u -Ins) pid=$$ ppid=$PPID" >> "$LOG"

# Set up shared paths
export VK_DRIVER_FILES=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json
export MLX_OMARCHY_PLACED=AC
unset PYTHONPATH LD_LIBRARY_PATH HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL MLX_OMARCHY_SPIRV_CACHE || true

PY=/var/tmp/jwm1-v072rc1/venv/bin/python3
MODEL=/home/joshuawarren/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
RUN=/var/tmp/jwm1-ane-step2/fused-e2e/fused_e2e.py
LIBANE=/var/tmp/jwm1-ane-step2/libane.so
DRIVER=/tmp/mesa-sin-ftz-jwm1/drivers/libvulkan_asahi-e167.so

run_arm () { # arm_name worker_path
  local arm=$1
  local worker=$2
  local worker_sha=$(sha256sum "$worker" | cut -d' ' -f1)
  echo "=== ARM_START $arm worker=$worker sha=$worker_sha $(date -u -Ins) ===" >> "$LOG"
  local ts2=$(date +%Y%m%dT%H%M%S)
  local pbase=$BASE/$arm-$ts2
  mkdir -p "$pbase"
  # Per-arm identity pin
  {
    echo "=== IDENTITY $arm ==="
    date -u -Ins
    hostname
    uname -r
    echo "VK_DRIVER_FILES=$VK_DRIVER_FILES"
    echo "MLX_OMARCHY_PLACED=$MLX_OMARCHY_PLACED"
    echo "ANE_ISLAND_MODE=\${ANE_ISLAND_MODE-<unset: code default resident-batch>}"
    echo "worker_sha=$worker_sha"
    sha256sum "$worker" "$LIBANE" "$DRIVER" "$RUN/fused_e2e.py" "$PY" 2>/dev/null
    echo "worker_path=$worker"
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
      --encoder-runner /var/tmp/encwall-v071/base/vulkan_encoder.py \
      --source /var/tmp/IslandsExecJwm1/encoder-source \
      --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
      --bundles /var/tmp/jwm1-ane-step2/bundles \
      --worker "$worker" \
      --libane "$LIBANE" \
      --scratch "$scratch" --out "$out" \
      --deadline-ms 20000 > "$pbase/log-$name.txt" 2>&1
    local rc=$?
    if [ $rc -ne 0 ]; then echo "RUN-FAILED $name rc=$rc"; tail -6 "$pbase/log-$name.txt"; return 3; fi
  }
  run_one warm || return 3
  for i in $(seq 1 5); do run_one "meas-$i" || return 3; done

  # Aggregate
  "$PY" - "$pbase" "$BASE/$arm-summary.json" "$arm" <<'PYEOF'
import glob, hashlib, json, statistics, sys
src_base, dst, label = sys.argv[1], sys.argv[2], sys.argv[3]
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
rows = []
for d in sorted(glob.glob(src_base+"/out-meas-*")):
    r = json.load(open(d+"/e2e-report.json"))
    st = {s["stage"]: s.get("wall_ms") for s in r.get("stages", [])}
    gold = (sha(d+"/mel.npy")==MEL, sha(d+"/encoder_hidden.npy")==HID, sha(d+"/transcript.txt")==TRX)
    rows.append({
        "run": d.rsplit("out-",1)[1],
        "encoder_ane_ms": st.get("encoder_ane"),
        "total_ms": r.get("timing",{}).get("total_pipeline_ms"),
        "mel/hidden/trx_bitexact": all(gold),
        "submissions": r["ane"].get("submissions"),
        "worker_starts": r["ane"].get("worker_starts"),
        "placed_bundles": r["ane"].get("bundles"),
        "status": r.get("status"),
        "prefix_104": "104" if r.get("status")=="match" else "NOT-104",
    })
enc = [r["encoder_ane_ms"] for r in rows]
summary = {
    "arm": label,
    "schema": "jwm1-ab-perf-battery/1",
    "runs": rows,
    "encoder_ane_median_all5_ms": statistics.median(enc),
    "encoder_ane_median_runs2_5_ms": statistics.median(enc[1:]),
    "total_median_all5_ms": statistics.median([r["total_ms"] for r in rows]),
    "all_goldens_bitexact": all(r["mel/hidden/trx_bitexact"] for r in rows),
    "all_status_match": all(r["status"]=="match" for r in rows),
    "all_prefix_104": all(r["prefix_104"]=="104" for r in rows),
}
json.dump(summary, open(dst,"w"), indent=1)
print(json.dumps(summary, indent=1))
PYEOF
  local rc=$?
  echo "=== ARM_END $arm rc=$rc $(date -u -Ins) ===" >> "$LOG"
  return $rc
}

# === ARM A: prebuilt worker (parent baseline reference) ===
run_arm "A-prebuilt" /tmp/parakeet-perf-resident/worker-base-prebuilt.bak
RC_A=$?

# === ARM B: new-built TOOLS worker (this build, no lever) ===
run_arm "B-built-base" /tmp/parakeet-perf-resident/mlx-omarchy-ane-worker-tools
RC_B=$?

# === ARM C: new-built LEVER worker ===
run_arm "C-built-lever" /tmp/parakeet-perf-resident/mlx-omarchy-ane-worker-lever
RC_C=$?

echo "AB_LOCK_RELEASE $(date -u -Ins) A_rc=$RC_A B_rc=$RC_B C_rc=${RC_C:-0}" >> "$LOG"
flock -u 9

echo "=== AB_SUMMARY BASE=$BASE A_rc=$RC_A B_rc=$RC_B C_rc=${RC_C:-0} ==="
exit $((RC_A + RC_B + ${RC_C:-0}))
