#!/bin/bash
# profiled_lease_run.sh — Bounded jwm1 /dev/accel/accel0 lease with ANE_RESIDENT_PROFILE=1.
# Acquires /tmp/m1-gpu.lock inode 27, runs the perf-battery under profiled
# overlays, releases lock. Same identity pin as the baseline re-confirm.
set -uo pipefail

LOCK=/tmp/m1-gpu.lock
LOCK_TIMEOUT_S=1500
TS=$(date +%Y%m%dT%H%M%S)
BASE=/var/tmp/jwm1-ane-step2/fused-e2e/profiled-reconfirm-$TS
LOG=$BASE/run.log
mkdir -p "$BASE"
chmod 755 "$BASE"

exec 9>"$LOCK"
echo "ACQUIRE_LOCK_ATTEMPT $(date -u -Ins) host=$(hostname) inode=$(stat -c %i $LOCK)" >> "$LOG"
if ! flock -w $LOCK_TIMEOUT_S 9; then
  echo "FAILED_TO_ACQUIRE_LOCK $(date -u -Ins)" >> "$LOG"
  cat "$LOG"
  exit 2
fi
echo "LOCK_HELD $(date -u -Ins) pid=$$ ppid=$PPID" >> "$LOG"

# Identity pin
{
  echo "=== IDENTITY (profiled run) ==="
  date -u -Ins
  hostname
  uname -r
  echo "VK_DRIVER_FILES=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json"
  echo "MLX_OMARCHY_PLACED=AC"
  echo "ANE_ISLAND_MODE=\${ANE_ISLAND_MODE-<unset: code default resident-batch>}"
  echo "ANE_RESIDENT_PROFILE=1"
  sha256sum \
    /var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker \
    /var/tmp/jwm1-ane-step2/libane.so \
    /tmp/mesa-sin-ftz-jwm1/drivers/libvulkan_asahi-e167.so \
    /tmp/parakeet-perf-resident/vulkan_encoder_profile_wrapper.py \
    /tmp/parakeet-perf-resident/ane_resident_profiled.py \
    /tmp/parakeet-perf-resident/mock_worker.py \
    /tmp/parakeet-perf-resident/test_profile_invariants.py \
    /var/tmp/jwm1-v072rc1/venv/bin/python3
  echo "driver-buildid: $(readelf -n /tmp/mesa-sin-ftz-jwm1/drivers/libvulkan_asahi-e167.so | sed -n 's/.*Build ID: //p')"
} > "$BASE/identity.txt" 2>&1

# Run profiled perf-battery (warm + 5 measured, same as parent protocol
# but with ANE_RESIDENT_PROFILE=1 and the profiled overlay)
echo "=== PROFILED_PERF_BATTERY_START $(date -u -Ins) ===" >> "$LOG"

# Inline modified perf-battery that uses --encoder-runner overlay
TS2=$(date +%Y%m%dT%H%M%S)
PBASE=/var/tmp/jwm1-ane-step2/fused-e2e/profiled-$TS2
mkdir -p "$PBASE"

export VK_DRIVER_FILES=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json
export MLX_OMARCHY_PLACED=AC
export ANE_RESIDENT_PROFILE=1
unset PYTHONPATH LD_LIBRARY_PATH HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL MLX_OMARCHY_SPIRV_CACHE || true

PY=/var/tmp/jwm1-v072rc1/venv/bin/python3
RUNNER=/tmp/parakeet-perf-resident/vulkan_encoder_profile_wrapper.py
MODEL=/home/joshuawarren/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
WORKER=/var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=/var/tmp/jwm1-ane-step2/libane.so
RUN=/var/tmp/jwm1-ane-step2/fused-e2e/fused_e2e.py

run_one () { # name
  local name=$1
  local out=$PBASE/out-$name scratch=$PBASE/scratch-$name
  rm -rf "$out" "$scratch"; mkdir -p "$out" "$scratch"
  "$PY" "$RUN" \
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
    --scratch "$scratch" --out "$out" \
    --deadline-ms 20000 > "$PBASE/log-$name.txt" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then echo "RUN-FAILED $name rc=$rc"; tail -6 "$PBASE/log-$name.txt"; return 3; fi
  echo "$name done $(date -Iseconds)"
}

run_one warm || exit 3
for i in $(seq 1 5); do run_one "meas-$i" || exit 3; done

# Aggregate profiles across all measured runs
"$PY" - "$PBASE" "$BASE" <<'PYEOF'
import glob, hashlib, json, statistics, sys
src_base, dst_base = sys.argv[1], sys.argv[2]
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
rows = []
all_round_profiles = []
for d in sorted(glob.glob(src_base+"/out-meas-*")):
    r = json.load(open(d+"/e2e-report.json"))
    st = {s["stage"]: s.get("wall_ms") for s in r.get("stages", [])}
    gold = (sha(d+"/mel.npy")==MEL, sha(d+"/encoder_hidden.npy")==HID, sha(d+"/transcript.txt")==TRX)
    # Per-round profiles from island.log (vulkan_encoder) + session.log (ane_resident)
    rounds = []
    for logpath in glob.glob(d+"/island.log") + glob.glob(d+"/runner.log"):
        try:
            runner_log = json.load(open(logpath))
            rounds.extend(runner_log.get("island_log", []))
        except Exception:
            pass
    rows.append({
        "run": d.rsplit("out-",1)[1],
        "encoder_ane_ms": st.get("encoder_ane"),
        "total_ms": r.get("timing",{}).get("total_pipeline_ms"),
        "mel/hidden/trx_bitexact": all(gold),
        "submissions": r["ane"].get("submissions"),
        "worker_starts": r["ane"].get("worker_starts"),
        "placed_bundles": r["ane"].get("bundles"),
        "status": r.get("status"),
        "round_profile_count": len(rounds),
    })
    for rd in rounds:
        if "profile" in rd:
            all_round_profiles.append(rd["profile"])
enc = [r["encoder_ane_ms"] for r in rows]

# Per-segment breakdown summary
def stats(field):
    vals = [p[field] for p in all_round_profiles if field in p]
    if not vals: return None
    return {
        "n": len(vals),
        "median_ns": statistics.median(vals),
        "median_ms": statistics.median(vals) / 1e6,
        "min_ms": min(vals) / 1e6,
        "max_ms": max(vals) / 1e6,
        "pct_of_round_median": (statistics.median(vals) /
            statistics.median([p["session_round_ns"] for p in all_round_profiles if "session_round_ns" in p]) * 100
            if any("session_round_ns" in p for p in all_round_profiles) else None),
    }

# Aggregate parent-side segments (from session_profile)
def parent_stat(sp_field):
    vals = []
    for p in all_round_profiles:
        sp = p.get("session_profile")
        if sp and sp_field in sp:
            vals.append(sp[sp_field])
    if not vals: return None
    return {
        "n": len(vals),
        "median_ns": statistics.median(vals),
        "median_ms": statistics.median(vals) / 1e6,
        "min_ms": min(vals) / 1e6,
        "max_ms": max(vals) / 1e6,
    }

summary = {
    "schema": "jwm1-profiled-perf-battery/1",
    "placement_partition": "AC placed: islands A (island-attn-a-kt) + C (island-pv) on T8103 ANE per layer, B (island-select-8head) + remaining encoder ops on GPU via e167 fork",
    "profile_env": "ANE_RESIDENT_PROFILE=1",
    "runs": rows,
    "encoder_ane_median_all_ms": statistics.median(enc) if enc else None,
    "all_goldens_bitexact": all(r["mel/hidden/trx_bitexact"] for r in rows) if rows else False,
    "all_status_match": all(r["status"]=="match" for r in rows) if rows else False,
    "all_prefix_104": all(r["prefix_104"]=="104" for r in rows) if rows else False,
    "per_segment_vulkan_encoder_ms": {
        "marshal_eval_ns": stats("marshal_eval_ns"),
        "session_round_ns": stats("session_round_ns"),
        "back_conv_ns": stats("back_conv_ns"),
        "sum_ns": stats("sum_ns"),
    },
    "per_segment_parent_side_ns": {
        "encode_ns": parent_stat("encode_ns"),
        "write_call_ns": parent_stat("write_call_ns"),
        "first_byte_ns": parent_stat("first_byte_ns"),
        "output_read_ns": parent_stat("output_read_ns"),
        "header_lines_ns": parent_stat("header_lines_ns"),
        "trailing_ns": parent_stat("trailing_ns"),
    },
}
json.dump(summary, open(dst_base+"/profiled-summary.json","w"), indent=1)
print(json.dumps(summary, indent=1))
PYEOF
RC=$?
echo "=== PROFILED_PERF_BATTERY_END $(date -u -Ins) rc=$RC ===" >> "$LOG"

echo "LOCK_RELEASE $(date -u -Ins)" >> "$LOG"
flock -u 9

echo "=== SUMMARY ==="
echo "BASE=$BASE"
echo "RUN_BASE=$PBASE"
echo "RC=$RC"
exit $RC
