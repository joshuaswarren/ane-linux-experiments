#!/bin/bash
# run-contract.sh — Parakeet TDT 0.6b e2e stage-split contract on t6001-host
# (installed path: /var/tmp/v072-venv-fused), recovered harness 2026-09-24.
# Runs smoke + 3 measurements under /tmp/m1-gpu.lock with the service-stop /
# trap-restore discipline. Gates: status match + mel/hidden/transcript pins
# (5b54f4a9 / 38c73261 / db501a8c) + matching_prefix_length 104.
set -uo pipefail
R=/var/tmp/parakeet-recover
PY=/var/tmp/v072-venv-fused/bin/python3
E2E=$R/fused_e2e.py
RUNNER=$R/vulkan_encoder_inproc.py
BUNDLES=$R/bundles
SRC=$R/encoder-source
REF=$R/ane-reference/encoder_hidden.npy
AUDIO=$R/audio/fixture.flac
GOLDEN=$R/capture
PKG=$R/pkg
MODEL=$HOME/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
# worker + libane: prefer the surviving on-box builds, else the staged fallbacks
W_ENC=/var/tmp/encoder-whole
WORKER=${WORKER:-$W_ENC/build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker}
LIBANE=${LIBANE:-$W_ENC/libane-strict.so}
[ -x "$WORKER" ] || WORKER=$R/fallback-worker/worker-binary
[ -e "$LIBANE" ] || LIBANE=$R/fallback-worker/libane-strict.so
# inproc shim: discover an existing build, else rebuild from source
find_shim () {
  local c
  for c in "$W_ENC/build/libane_inproc.so" "$W_ENC/libane_inproc.so" \
           /var/tmp/v072-venv-fused/lib/libane_inproc.so /var/tmp/v072-venv-fused/libane_inproc.so; do
    [ -e "$c" ] && { echo "$c"; return 0; }
  done
  find /var/tmp/encoder-whole/build /var/tmp/v072-venv-fused "$HOME/src/mlx-omarchy" -maxdepth 6 -name 'libane_inproc.so' 2>/dev/null | head -1
  return 0
}
SHIM=${SHIM:-$(find_shim)}
TS=$(date +%Y%m%dT%H%M%S)
BASE=$R/battery-$TS
mkdir -p "$BASE"

echo "=== preflight ==="
fail=0
for f in "$PY" "$E2E" "$RUNNER" "$PKG/coreml/parakeet_tdt.py" "$AUDIO" "$MODEL" \
         "$GOLDEN/encoder_hidden.npy" "$GOLDEN/mel.npy" "$GOLDEN/transcript.txt" \
         "$BUNDLES/island-attn-a-kt/manifest.json" "$BUNDLES/island-pv/manifest.json" \
         "$SRC/model.mil" "$WORKER" "$LIBANE" "$REF"; do
  [ -e "$f" ] || { echo "MISSING $f"; fail=1; }
done
[ -n "$SHIM" ] && [ -e "$SHIM" ] || { echo "MISSING libane_inproc.so (shim)"; fail=1; }
[ $fail -ne 0 ] && { echo PREFLIGHT-FAIL; exit 9; }
echo "SHIM=$SHIM"
{ date -Ins; hostname; sha256sum "$PY" "$E2E" "$RUNNER" "$SHIM" "$WORKER" "$LIBANE" "$AUDIO"; } > "$BASE/identity.txt" 2>&1
"$PY" -c "import mlx.core, sys; print('mlx.ok', sys.version.split()[0])" || { echo VENV-BROKEN; exit 9; }
"$PY" -c "import soundfile; print('soundfile', soundfile.__version__)" 2>/dev/null || \
  "$PY" -m pip install --quiet soundfile > "$BASE/pip-soundfile.txt" 2>&1 || { echo PIP-FAILED; exit 3; }

restore_service () {
  echo "=== restore llm-inference $(date -Iseconds) ==="
  sudo systemctl start llm-inference.service
  local ok=""
  for i in $(seq 1 45); do
    if curl -sf -m 3 http://127.0.0.1:8002/health >/dev/null 2>&1; then ok=1; break; fi
    sleep 2
  done
  [ -n "$ok" ] && echo "health: 200" || { echo "health: FAILED"; return 1; }
  local key rc
  key=$(sudo cat /etc/llm-inference/api-key) || return 1
  rc=$(curl -sS -m 60 http://127.0.0.1:8002/v1/chat/completions \
    -H "Authorization: Bearer $key" -H 'Content-Type: application/json' \
    -d '{"model":"default","messages":[{"role":"user","content":"Say Pacific"}],"max_tokens":8}' \
    | "$PY" -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['finish_reason'])" 2>/dev/null)
  echo "completion probe finish: ${rc:-FAILED}"
}
trap 'restore_service' EXIT

run_one () { # name
  local out=$BASE/out-$1 scratch=$BASE/scratch-$1
  rm -rf "$out" "$scratch"; mkdir -p "$out" "$scratch"
  flock -w 900 /tmp/m1-gpu.lock \
  env MLX_OMARCHY_PLACED=AC ANE_ISLAND_MODE=inprocess ANE_INPROC_SHIM="$SHIM" \
      MLX_OMARCHY_FUSED_AB=0 MLX_OMARCHY_PIPE_OPS= MLX_OMARCHY_DEFER_COMMIT=${DEFER_COMMIT:-1} \
      -u PYTHONPATH -u LD_LIBRARY_PATH -u MLX_OMARCHY_GATED_BARRIERS -u MLX_OMARCHY_GPU_PROFILE \
      -u ANE_OP_WALL -u MLX_OMARCHY_SPIRV_CACHE \
  "$PY" "$E2E" \
    --audio "$AUDIO" --golden "$GOLDEN" --model "$MODEL" --pkg "$PKG" \
    --encoder-runner "$RUNNER" --source "$SRC" --ane-reference "$REF" \
    --bundles "$BUNDLES" --worker "$WORKER" --libane "$LIBANE" \
    --scratch "$scratch" --out "$out" --deadline-ms 20000 --tdt-host \
    > "$BASE/log-$1.txt" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then echo "RUN-FAILED $1 rc=$rc"; tail -12 "$BASE/log-$1.txt"; return 3; fi
  echo "$1 done $(date -Iseconds)"
}

echo "=== smoke ==="
run_one smoke || { echo SMOKE-FAILED; exit 3; }
for i in 1 2 3; do run_one "meas-$i" || exit 3; done

"$PY" - "$BASE" <<'PYEOF'
import glob, hashlib, json, statistics, sys
base = sys.argv[1]
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
summary = {"schema":"parakeet-decomp-ab/1","base":base,"rows":[]}
for d in sorted(glob.glob(base+"/out-*")):
    r = json.load(open(d+"/e2e-report.json"))
    st = {s["stage"]: s.get("wall_ms") for s in r.get("stages", [])}
    tm = r.get("timing", {})
    row = {
        "run": d.rsplit("out-",1)[1],
        "stages": st,
        "decoder_total_ms": tm.get("decoder_total_ms"),
        "joint_total_ms": tm.get("joint_total_ms"),
        "decoder_calls": tm.get("decoder_calls"),
        "joint_calls": tm.get("joint_calls"),
        "total_ms": tm.get("total_pipeline_ms"),
        "gold": sha(d+"/mel.npy")==MEL and sha(d+"/encoder_hidden.npy")==HID and sha(d+"/transcript.txt")==TRX,
        "status": r.get("status"),
        "p104": '"matching_prefix_length": 104' in json.dumps(r),
    }
    summary["rows"].append(row)
json.dump(summary, open(base+"/summary.json","w"), indent=1)
meas = [r for r in summary["rows"] if r["run"].startswith("meas")] or summary["rows"]
print("all_green:", all(r["gold"] and r["status"]=="match" and r["p104"] for r in summary["rows"]))
for k in ["audio_load","mel_frontend","encoder_ane","decoder_load","tdt_decode","detokenize"]:
    vals = [r["stages"].get(k) for r in meas if r["stages"].get(k)]
    if vals: print(f"  {k}: median {round(statistics.median(vals),1)} ms  runs {[round(v,1) for v in vals]}")
t = [r["total_ms"] for r in meas if r["total_ms"]]
if t: print(f"  total: median {round(statistics.median(t),1)} ms")
d = [r for r in meas if r.get("decoder_calls")]
if d: print("  decoder/joint ms:", d[-1]["decoder_total_ms"], d[-1]["joint_total_ms"], "calls:", d[-1]["decoder_calls"], d[-1]["joint_calls"])
PYEOF
echo "=== CONTRACT DONE $BASE ==="
