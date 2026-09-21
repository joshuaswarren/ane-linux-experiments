#!/bin/bash
# stage3-diag.sh — perturbation bound + per-op wall attribution for the encoder stage.
# 3x unprofiled base runs (fresh drift bound) + 2x ANE_OP_WALL=1 runs (per-op attribution).
# Read-only w.r.t. the shared runner; all outputs under a timestamped diag dir.
set -uo pipefail

RUN=/var/tmp/jwm1-ane-step2/fused-e2e
PY=/var/tmp/jwm1-v072rc1/venv/bin/python3
RUNNER=/var/tmp/encwall-v071/base/vulkan_encoder.py
MODEL=/home/joshuawarren/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
WORKER=/var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=/var/tmp/jwm1-ane-step2/libane.so
DRIVER=/tmp/mesa-sin-ftz-jwm1/drivers/libvulkan_asahi-e167.so
ICD=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json
TS=$(date +%Y%m%dT%H%M%S)
BASE=/var/tmp/jwm1-ane-step2/fused-e2e/stage3-diag-$TS
mkdir -p "$BASE"

export VK_DRIVER_FILES=$ICD
export MLX_OMARCHY_PLACED=AC
unset PYTHONPATH LD_LIBRARY_PATH ANE_ISLAND_MODE MLX_OMARCHY_SPIRV_CACHE HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL || true

{
  date -Ins; hostname
  echo "VK_DRIVER_FILES=$VK_DRIVER_FILES  MLX_OMARCHY_PLACED=$MLX_OMARCHY_PLACED  ANE_ISLAND_MODE=${ANE_ISLAND_MODE-unset}"
  sha256sum "$WORKER" "$LIBANE" "$DRIVER" "$RUNNER" "$RUN/fused_e2e.py" "$PY"
  echo "driver-buildid: $(readelf -n "$DRIVER" | sed -n 's/.*Build ID: //p')"
} > "$BASE/identity.txt" 2>&1

run_one () { # name extra_env
  local name=$1
  local out=$BASE/out-$name scratch=$BASE/scratch-$name
  rm -rf "$out" "$scratch"; mkdir -p "$out" "$scratch"
  env $2 "$PY" "$RUN/fused_e2e.py" \
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
  echo "$name rc=$rc $(date -Iseconds)"
}

# 3x unprofiled (no ANE_OP_WALL) — fresh drift/perturbation bound
for i in 1 2 3; do run_one "unprof-$i" ""; done
# 2x profiled with per-op walls
for i in 1 2; do ANE_OP_WALL=1 run_one "prof-$i" "ANE_OP_WALL=1"; done

python3 - "$BASE" <<'PYEOF'
import glob, hashlib, json, statistics, sys
base = sys.argv[1]
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
rows = []
for d in sorted(glob.glob(base+"/out-*")):
    r = json.load(open(d+"/e2e-report.json"))
    log = r["ane"]["log"]
    def s(k): return round(sum(float(e.get(k,0)) for e in log)/1e6,1)
    st = {x["stage"]: x.get("wall_ms") for x in r["stages"]}
    ok = (sha(d+"/mel.npy")==MEL and sha(d+"/encoder_hidden.npy")==HID and sha(d+"/transcript.txt")==TRX)
    rows.append({"run": d.rsplit("out-",1)[1], "stage_ms": st.get("encoder_ane"),
                 "marshal": s("marshal_ns"), "eval_split": s("eval_split_ns"),
                 "round": r["ane"]["exec_ms"], "status": r.get("status"),
                 "prefix104": '"matching_prefix_length": 104' in json.dumps(r), "goldens": ok})
un = [r["stage_ms"] for r in rows if r["run"].startswith("unprof")]
pr = [r["stage_ms"] for r in rows if r["run"].startswith("prof")]
summary = {
  "schema": "jwm1-stage3-diag/1",
  "rows": rows,
  "unprofiled_stage_ms": un,
  "unprofiled_median_ms": statistics.median(un) if un else None,
  "profiled_stage_ms": pr,
  "profiled_median_ms": statistics.median(pr) if pr else None,
  "perturbation_ms": (statistics.median(pr) - statistics.median(un)) if un and pr else None,
  "all_gates": all(r["status"]=="match" and r["prefix104"] and r["goldens"] for r in rows),
}
json.dump(summary, open(base+"/diag-summary.json","w"), indent=1)
print(json.dumps(summary, indent=1))
PYEOF
echo "=== DIAG DONE $BASE ==="
grep -h "op_wall_ms" "$BASE"/log-prof-*.txt | sort | uniq -c | sort -rn | head -30
