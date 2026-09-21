#!/bin/bash
# perf-battery.sh — resident-batch (serve worker) full-ASR battery on jwm1.
# Protocol per Main + jw16 window script: 1 warm + 10 measured runs.
# COMPARISON RULE: encoder_ane STAGE median vs the 259.9 ms macOS 27 same-encoder
# divisor (2026-09-17-parakeet-macos-timing-t8103) — NEVER total-ASR vs encoder
# divisor mixing. Context caveat: macOS numbers are CoreML-context; same-encoder
# claim only.
set -uo pipefail

RUN=/var/tmp/jwm1-ane-step2/fused-e2e
PY=/var/tmp/jwm1-v072rc1/venv/bin/python3
RUNNER=/var/tmp/jwm1-ane-step2/fused-e2e/encwall-marshal-ab/vulkan_encoder.py
MODEL=/home/joshuawarren/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
WORKER=/var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=/var/tmp/jwm1-ane-step2/libane.so
DRIVER=/tmp/mesa-sin-ftz-jwm1/drivers/libvulkan_asahi-e167.so
ICD=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json
TS=$(date +%Y%m%dT%H%M%S)
BASE=/var/tmp/jwm1-ane-step2/fused-e2e/perf-battery-marshalab-$TS
mkdir -p "$BASE"

export VK_DRIVER_FILES=$ICD
export MLX_OMARCHY_PLACED=AC
unset PYTHONPATH LD_LIBRARY_PATH HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL MLX_OMARCHY_SPIRV_CACHE || true

# identity pin (once per battery)
{
  date -Ins; hostname
  echo "VK_DRIVER_FILES=$VK_DRIVER_FILES"; echo "MLX_OMARCHY_PLACED=$MLX_OMARCHY_PLACED"
  echo "ANE_ISLAND_MODE=${ANE_ISLAND_MODE-<unset: code default resident-batch>}"
  sha256sum "$WORKER" "$LIBANE" "$DRIVER" "$RUNNER" "$RUN/fused_e2e.py" "$PY"
  echo "driver-buildid: $(readelf -n "$DRIVER" | sed -n 's/.*Build ID: //p')"
} > "$BASE/identity.txt" 2>&1

run_one () { # name
  local name=$1
  local out=$BASE/out-$name scratch=$BASE/scratch-$name
  rm -rf "$out" "$scratch"; mkdir -p "$out" "$scratch"
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
    --scratch "$scratch" --out "$out" \
    --deadline-ms 20000 > "$BASE/log-$name.txt" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then echo "RUN-FAILED $name rc=$rc"; tail -6 "$BASE/log-$name.txt"; return 3; fi
  echo "$name done $(date -Iseconds)"
}

run_one warm || exit 3
for i in $(seq 1 10); do run_one "meas-$i" || exit 3; done

# summary: per-run encoder_ane + total from each machine report, goldens checked
"$PY" - "$BASE" <<'PYEOF'
import glob, hashlib, json, statistics, sys
base = sys.argv[1]
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
rows = []
for d in sorted(glob.glob(base+"/out-meas-*")):
    r = json.load(open(d+"/e2e-report.json"))
    st = {s["stage"]: s.get("wall_ms") for s in r.get("stages", [])}
    def sha(p):
        return hashlib.sha256(open(p,"rb").read()).hexdigest()
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
        "prefix_104": "104" if '"matching_prefix_length": 104' in json.dumps(r) else "NOT-104",
    })
enc = [r["encoder_ane_ms"] for r in rows]
summary = {
    "schema": "jwm1-perf-battery/1",
    "placement_partition": "AC placed: islands A (island-attn-a-kt) + C (island-pv) on T8103 ANE per layer, B (island-select-8head) + remaining encoder ops on GPU via e167 fork; placement per run recorded from ane.bundles",
    "runs": rows,
    "encoder_ane_median_all10_ms": statistics.median(enc),
    "encoder_ane_median_runs2_10_ms": statistics.median(enc[1:]),
    "total_median_all10_ms": statistics.median([r["total_ms"] for r in rows]),
    "macos27_same_encoder_divisor_ms": 259.9,
    "divisor_context_caveat": "macOS CoreML context; same-encoder stage claim only, not end-to-end",
    "all_goldens_bitexact": all(r["mel/hidden/trx_bitexact"] for r in rows),
    "all_status_match": all(r["status"]=="match" for r in rows),
    "all_prefix_104": all(r["prefix_104"]=="104" for r in rows),
}
json.dump(summary, open(base+"/battery-summary.json","w"), indent=1)
print(json.dumps(summary, indent=1))
PYEOF
echo "=== BATTERY DONE $BASE ==="
