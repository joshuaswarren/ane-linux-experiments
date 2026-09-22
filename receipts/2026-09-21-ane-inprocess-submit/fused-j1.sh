#!/bin/bash
# fused-j1.sh — interleaved A/B: resident-batch (worker fallback) vs
# inprocess (ane_inproc shim). One runner file, mode via ANE_ISLAND_MODE.
# Mirrors the green battery identity (ab-battery-j16.sh / battery-v2-16.sh).
set -uo pipefail
RUN=/var/tmp/j1-ane-step2/fused-e2e
PY=/var/tmp/j1-v072rc1/venv/bin/python3
MODEL=$HOME/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
WORKER=/var/tmp/j1-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=/var/tmp/j1-ane-step2/libane.so
SHIM=/var/tmp/encwall-decomp/libane_inproc.so
RUNNER=/var/tmp/encwall-decomp/inproc-tmp/vulkan_encoder_inproc.py
TS=$(date +%Y%m%dT%H%M%S)
BASE=/var/tmp/encwall-decomp/fused-$TS
mkdir -p "$BASE"
export MLX_OMARCHY_PLACED=AC
unset PYTHONPATH LD_LIBRARY_PATH MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL MLX_OMARCHY_SPIRV_CACHE
{
  date -Ins; hostname
  sha256sum "$WORKER" "$LIBANE" "$SHIM" "$RUNNER" "$RUN/fused_e2e.py" "$PY"
} > "$BASE/identity.txt" 2>&1

run_one () { # arm mode name fused
  local arm=$1 mode=$2 name=$3 fused=$4
  local out=$BASE/out-$arm-$name scratch=$BASE/scratch-$arm-$name
  rm -rf "$out" "$scratch"; mkdir -p "$out" "$scratch"
  ANE_ISLAND_MODE=$mode ANE_INPROC_SHIM=$SHIM MLX_OMARCHY_FUSED_AB=$fused \
  "$PY" "$RUN/fused_e2e.py" \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model "$MODEL" \
    --pkg /var/tmp/TdtLoopDefault/pkg \
    --encoder-runner "$RUNNER" \
    --source /var/tmp/IslandsExecJ1/encoder-source \
    --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
    --bundles /var/tmp/j1-ane-step2/bundles \
    --worker "$WORKER" \
    --libane "$LIBANE" \
    --scratch "$scratch" --out "$out" \
    --deadline-ms 20000 > "$BASE/log-$arm-$name.txt" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then echo "RUN-FAILED $arm-$name rc=$rc"; tail -8 "$BASE/log-$arm-$name.txt"; return 3; fi
  echo "$arm-$name done $(date -Iseconds)"
}

# Smoke: single inprocess run before the battery commits to it.
run_one B inprocess 1 warm-smoke || { echo "SMOKE-FAILED"; exit 3; }

run_one A inprocess 0 warm || exit 3
run_one B inprocess 1 warm || exit 3
for i in 1 2 3 4 5 6; do
  run_one A inprocess 0 "meas-$i" || exit 3
  run_one B inprocess 1 "meas-$i" || exit 3
done

"$PY" - "$BASE" <<'PYEOF'
import glob, hashlib, json, statistics, sys
base = sys.argv[1]
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
arms = {}
for d in sorted(glob.glob(base+"/out-*")):
    arm = d.rsplit("out-",1)[1].split("-")[0]
    r = json.load(open(d+"/e2e-report.json"))
    st = {s["stage"]: s.get("wall_ms") for s in r.get("stages", [])}
    log = r["ane"]["log"]
    agg = {}
    for e in log:
        b = e["bundle"]; a = agg.setdefault(b, dict(n=0, marshal=0.0, el=0.0, wr=0.0, rd=0.0))
        a["n"] += 1
        a["marshal"] += e.get("marshal_ns", 0)/1e6
        a["el"] += e.get("elapsed_ns", 0)/1e6
        if "write_ns" in e:
            a["wr"] += e["write_ns"]/1e6; a["rd"] += e["read_ns"]/1e6
    arms.setdefault(arm, []).append({
        "run": d.rsplit("out-",1)[1], "encoder_ane_ms": st.get("encoder_ane"),
        "total_ms": r.get("timing",{}).get("total_pipeline_ms"),
        "gold": sha(d+"/mel.npy")==MEL and sha(d+"/encoder_hidden.npy")==HID and sha(d+"/transcript.txt")==TRX,
        "status": r.get("status"), "p104": '"matching_prefix_length": 104' in json.dumps(r),
        "islands": agg,
    })
summary = {"schema":"j16-inproc-ab/1","base":base,"arms":{}}
for arm, rows in arms.items():
    meas = [r for r in rows if "meas-" in r["run"]] or rows
    summary["arms"][arm] = {
        "all_green": all(r["gold"] and r["status"]=="match" and r["p104"] for r in rows),
        "encoder_ane_median_ms": statistics.median([r["encoder_ane_ms"] for r in meas]),
        "total_median_ms": statistics.median([r["total_ms"] for r in meas]),
        "runs": rows,
    }
json.dump(summary, open(base+"/ab-summary.json","w"), indent=1)
print(json.dumps({a:{k:v for k,v in d.items() if k!="runs"} for a,d in summary["arms"].items()}, indent=1))
PYEOF
echo "=== AB DONE $BASE ==="
