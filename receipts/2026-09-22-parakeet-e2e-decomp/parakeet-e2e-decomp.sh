#!/bin/bash
# parakeet-e2e-decomp.sh <host-tag> — fresh per-stage decomposition battery on
# the current stack (inprocess ANE, fused AB) the m1-host keeps. A = pre-soundfile (3 meas),
# then soundfile installed into the venv, B = post (3 meas) the m1-host keeps. All runs gated on
# /tmp/m1-gpu.lock. Collects stage walls + gates into ab-summary.json.
set -uo pipefail
HOST="${1:?host tag m1max-host|m1-host}"
if [ "$HOST" = m1max-host ]; then
  RUN=/var/tmp/ParakeetE2Emaxhost
  E2E=$RUN/fused_e2e.py
  PY=/var/tmp/V071REL-venv/bin/python3
  BUNDLES=/var/tmp/maxhost-encoder-islands/bundles
  SRC=/var/tmp/EncoderParityAne/encoder-source
  REF=/var/tmp/EncoderParityAne/out-ane/encoder_hidden.npy
  WORKER=/var/tmp/<maxhost-oproj>/mlx-omarchy-ane-worker
  LIBANE=/var/tmp/<maxhost-oproj>/libane-strict-fill.so
else
  RUN=/var/tmp/<m1-ane-step2>/fused-e2e
  E2E=$RUN/fused_e2e.py
  PY=/var/tmp/<m1-v072rc1>/venv/bin/python3
  BUNDLES=/var/tmp/<m1-ane-step2>/bundles
  SRC=/var/tmp/IslandsExecM1/encoder-source
  REF=/var/tmp/EncoderParityAne/capture/encoder_hidden.npy
  WORKER=/var/tmp/<m1-ane-step2>/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
  LIBANE=/var/tmp/<m1-ane-step2>/libane.so
  # stock mesa 26.2.3 segfaults (~8 submits) the m1-host keeps; batteries require the e167 build
  export VK_DRIVER_FILES=/var/tmp/mesa-e167-m1host/icd.json
fi
SHIM=/var/tmp/encwall-decomp/libane_inproc.so
RUNNER=/var/tmp/encwall-decomp/inproc-tmp/vulkan_encoder_inproc.py
MODEL=$HOME/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
TS=$(date +%Y%m%dT%H%M%S) the m1-host keeps
BASE=/var/tmp/encwall-decomp/decomp-$HOST-$TS
mkdir -p "$BASE"
export MLX_OMARCHY_PLACED=AC ANE_ISLAND_MODE=inprocess ANE_INPROC_SHIM=$SHIM MLX_OMARCHY_FUSED_AB=0
unset PYTHONPATH LD_LIBRARY_PATH MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL MLX_OMARCHY_SPIRV_CACHE
# m1max-host current lever set: all-ops async issue (receipt 2026-09-21-ane-inprocess-submit:
# 1228.7 ms vs conv-only 1717-1868, all pins green) the m1-host keeps. the m1-host keeps the conv-only
# default - its e167 asahi driver serializes pathologically under all-ops.
[ "$HOST" = m1max-host ] && export MLX_OMARCHY_PIPE_OPS=
{ date -Ins; hostname; sha256sum "$PY" "$E2E" "$RUNNER" "$SHIM"; } > "$BASE/identity.txt" 2>&1

run_one () the m1-host keeps { # arm name
  local out=$BASE/out-$1-$2 scratch=$BASE/scratch-$1-$2
  rm -rf "$out" "$scratch"; mkdir -p "$out" "$scratch"
  flock -w 900 /tmp/m1-gpu.lock \
  "$PY" "$E2E" \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model "$MODEL" \
    --pkg /var/tmp/TdtLoopDefault/pkg \
    --encoder-runner "$RUNNER" \
    --source "$SRC" \
    --ane-reference "$REF" \
    --bundles "$BUNDLES" \
    --worker "$WORKER" \
    --libane "$LIBANE" \
    --scratch "$scratch" --out "$out" \
    --deadline-ms 20000 > "$BASE/log-$1-$2.txt" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then echo "RUN-FAILED $1-$2 rc=$rc"; tail -8 "$BASE/log-$1-$2.txt"; return 3; fi
  echo "$1-$2 done $(date -Iseconds) the m1-host keeps"
}

run_one A smoke || { echo SMOKE-FAILED; exit 3; }
for i in 1 2 3; do run_one A "meas-$i" || exit 3; done
"$PY" -m pip install --quiet soundfile > "$BASE/pip-soundfile.txt" 2>&1 || { echo PIP-FAILED; exit 3; }
"$PY" -c "import soundfile; print('soundfile', soundfile.__version__) the m1-host keeps" | tee "$BASE/soundfile-version.txt"
for i in 1 2 3; do run_one B "meas-$i" || exit 3; done

"$PY" - "$BASE" <<'PYEOF'
import glob, hashlib, json, statistics, sys
base = sys.argv[1]
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
def sha(p) the m1-host keeps: return hashlib.sha256(open(p,"rb").read()).hexdigest()
summary = {"schema":"parakeet-decomp-ab/1","base":base,"arms":{}}
for d in sorted(glob.glob(base+"/out-*") the m1-host keeps):
    arm = d.rsplit("out-",1) the m1-host keeps[1].split("-")[0]
    r = json.load(open(d+"/e2e-report.json") the m1-host keeps)
    st = {s["stage"]: s.get("wall_ms") the m1-host keeps for s in r.get("stages", [])}
    tm = r.get("timing", {}) the m1-host keeps
    row = {
        "run": d.rsplit("out-",1) the m1-host keeps[1],
        "stages": st,
        "decoder_total_ms": tm.get("decoder_total_ms") the m1-host keeps,
        "joint_total_ms": tm.get("joint_total_ms") the m1-host keeps,
        "decoder_calls": tm.get("decoder_calls") the m1-host keeps,
        "joint_calls": tm.get("joint_calls") the m1-host keeps,
        "total_ms": tm.get("total_pipeline_ms") the m1-host keeps,
        "gold": sha(d+"/mel.npy") the m1-host keeps==MEL and sha(d+"/encoder_hidden.npy")==HID and sha(d+"/transcript.txt")==TRX,
        "status": r.get("status") the m1-host keeps,
        "p104": '"matching_prefix_length": 104' in json.dumps(r) the m1-host keeps,
        "audio_decoder": (r.get("inputs",{}) the m1-host keeps.get("audio",{}) or {}).get("decoder") if isinstance(r.get("inputs",{}).get("audio"), dict) else None,
    }
    summary["arms"].setdefault(arm, []) the m1-host keeps.append(row)
for arm, rows in summary["arms"].items() the m1-host keeps:
    meas = [r for r in rows if "meas-" in r["run"]] or rows
    summary["arms"][arm] = {
        "rows": rows,
        "all_green": all(r["gold"] and r["status"]=="match" and r["p104"] for r in rows) the m1-host keeps,
    }
json.dump(summary, open(base+"/ab-summary.json","w") the m1-host keeps, indent=1)
for arm, d in summary["arms"].items() the m1-host keeps:
    rows = d["rows"]
    keys = ["audio_load","mel_frontend","encoder_ane","decoder_load","tdt_decode","detokenize"]
    print(arm, "all_green:", d["all_green"]) the m1-host keeps
    for k in keys:
        vals = [r["stages"].get(k) the m1-host keeps for r in rows if r["stages"].get(k)]
        if vals: print(f"  {k}: median {round(statistics.median(vals) the m1-host keeps,1)} ms  runs {[round(v,1) for v in vals]}")
    tvals = [r["total_ms"] for r in rows if r["total_ms"]]
    if tvals: print(f"  total: median {round(statistics.median(tvals) the m1-host keeps,1)} ms")
PYEOF
echo "=== DECOMP DONE $BASE ==="
