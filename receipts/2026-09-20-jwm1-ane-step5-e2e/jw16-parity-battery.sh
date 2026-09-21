#!/bin/bash
# jw16-parity-battery.sh — full-ASR parity battery for jw16 (M1 Max/T6001).
# Protocol: warm + 10 measured, resident-batch transport, AC placement.
# Gates per run: status=match, 104/104, mel/hidden/transcript goldens bit-exact.
# Divisor: M1 Ultra whole-pipeline ANE median 292.2 ms CROSS-CHIP (2026-09-16
# receipt) — T6001 native divisor DOES NOT EXIST yet (needs jw16 macOS timing
# run, owner action); do not substitute the T8103 259.9 ms same-die number.
# Precondition (jw16 protocol): llm-inference.service stopped + /tmp/m1-gpu.lock held.
set -uo pipefail

RUN=/var/tmp/ParakeetE2EJw16
PY=/var/tmp/V071REL-venv/bin/python
RUNNER=/var/tmp/encwall-v071/base/vulkan_encoder.py
MODEL=/home/joshuawarren/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
WORKER=/var/tmp/jw16-oproj-place/mlx-omarchy-ane-worker
LIBANE=/var/tmp/jw16-oproj-place/libane-strict-fill.so
TS=$(date +%Y%m%dT%H%M%S)
BASE=/var/tmp/parakeet-parity-battery-$TS
mkdir -p "$BASE"

export VK_DRIVER_FILES=${VK_DRIVER_FILES:-}   # jw16 driver pin per lane receipt (set by provisioner)
export MLX_OMARCHY_PLACED=AC
unset PYTHONPATH || true

{
  date -Ins; hostname; uname -r
  echo "MLX_OMARCHY_PLACED=$MLX_OMARCHY_PLACED  ANE_ISLAND_MODE=${ANE_ISLAND_MODE-unset:resident-batch default}"
  echo "VK_DRIVER_FILES=${VK_DRIVER_FILES-<unset>}"
  sha256sum "$WORKER" "$LIBANE" "$RUNNER" "$RUN/fused_e2e.py" "$PY"
  echo "venv dist: $($PY -c 'import importlib.metadata as M; print(M.version("mlx-omarchy"))')"
} > "$BASE/identity.txt" 2>&1

run_one () {
  local name=$1
  local out=$BASE/out-$name scratch=$BASE/scratch-$name
  rm -rf "$out" "$scratch"; mkdir -p "$out" "$scratch"
  MLX_OMARCHY_PLACED=AC ANE_ISLAND_MODE=resident-batch \
  "$PY" "$RUN/fused_e2e.py" \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model "$MODEL" \
    --pkg /var/tmp/TdtLoopDefault/pkg \
    --encoder-runner "$RUNNER" \
    --source /var/tmp/EncoderParityAne/encoder-source \
    --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
    --bundles /var/tmp/jw16-conv-place/bundles-conv \
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
    def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
    rows.append({
        "run": d.rsplit("out-",1)[1],
        "encoder_ane_ms": st.get("encoder_ane"),
        "total_ms": r.get("timing",{}).get("total_pipeline_ms"),
        "goldens_bitexact": sha(d+"/mel.npy")==MEL and sha(d+"/encoder_hidden.npy")==HID and sha(d+"/transcript.txt")==TRX,
        "submissions": r["ane"].get("submissions"), "worker_starts": r["ane"].get("worker_starts"),
        "status": r.get("status"),
        "prefix104": '"matching_prefix_length": 104' in json.dumps(r),
    })
enc = [r["encoder_ane_ms"] for r in rows]
summary = {
  "schema": "jw16-parity-battery/1",
  "placement_partition": "AC placed (islands A+C on ANE, B + remaining ops GPU) — matches jwm1 lane shape",
  "runs": rows,
  "encoder_ane_median_all10_ms": statistics.median(enc),
  "encoder_ane_median_runs2_10_ms": statistics.median(enc[1:]),
  "total_median_all10_ms": statistics.median([r["total_ms"] for r in rows]),
  "divisor": {"m1ultra_whole_pipeline_ane_median_ms": 292.2, "context": "CROSS-CHIP M1 Ultra/T6000 (Mac13,2) — T6001/M1-Max native divisor does NOT exist yet (jw16 macOS timing run pending, owner action); T8103 259.9 ms same-die number does not apply to jw16"},
  "all_gates": all(r["goldens_bitexact"] and r["status"]=="match" and r["prefix104"] for r in rows),
}
json.dump(summary, open(base+"/battery-summary.json","w"), indent=1)
print(json.dumps(summary, indent=1))
PYEOF
echo "=== JW16 BATTERY DONE $BASE ==="
