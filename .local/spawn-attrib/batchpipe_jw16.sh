#!/bin/bash
# Batch-eval measurement: MLX_OMARCHY_PIPE=1, AC/ACO x launch/resident x3.
# Runner: /var/tmp/jw16-spawn-attrib/vk_conv.py (AC default + batch gate).
set -uo pipefail
W=/var/tmp/jw16-spawn-attrib
RUN=/var/tmp/ParakeetE2EJw16
PY=/home/joshuawarren/venv-agxgen/bin/python
export PYTHONPATH=$RUN/site:/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true

run_arm () { # name placed mode rep
  local name=$1 placed=$2 mode=$3 rep=$4
  local outdir=$W/out-be-$name scratch=$W/scratch-be-$name
  echo "--- arm $name PLACED='$placed' MODE=$mode rep=$rep $(date -Iseconds) ---"
  python3 -c "import shutil; shutil.rmtree('$outdir', ignore_errors=True); shutil.rmtree('$scratch', ignore_errors=True)"
  mkdir -p $outdir $scratch
  MLX_OMARCHY_PLACED="$placed" ANE_ISLAND_MODE=$mode MLX_OMARCHY_PIPE=1 \
  flock -w 900 /tmp/m1-gpu.lock \
  $PY $RUN/fused_e2e.py \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model ~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018 \
    --pkg /var/tmp/TdtLoopDefault/pkg \
    --encoder-runner $W/vk_conv.py \
    --source /var/tmp/EncoderParityAne/encoder-source \
    --ane-reference /var/tmp/EncoderParityAne/out-ane/encoder_hidden.npy \
    --bundles /var/tmp/jw16-conv-place/bundles-conv \
    --worker /var/tmp/jw16-oproj-place/mlx-omarchy-ane-worker \
    --libane /var/tmp/jw16-oproj-place/libane-strict-fill.so \
    --scratch $scratch \
    --out $outdir \
    --deadline-ms 20000 > $W/be-$name.log 2>&1 || { echo "ARM $name FAILED"; tail -5 $W/be-$name.log; return 1; }
  python3 - "$outdir" "$name" "$placed" "$mode" "$rep" <<'PY'
import hashlib, json, sys
out, name, placed, mode, rep = sys.argv[1:6]
r = json.load(open(out + "/e2e-report.json"))
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
seq = r["layers"]["layer_6_decoder_sequence"]
enc = next((s for s in r["stages"] if isinstance(s, dict) and s.get("stage") == "encoder_ane"), {})
row = {
    "arm": name, "placed": placed, "mode": mode, "rep": rep,
    "status": r["status"], "subs": r["ane"]["submissions"],
    "prefix": seq.get("matching_prefix_length"),
    "bounds": r["layers"]["layer_5_encoder"]["all_bounds_pass"],
    "cpu_ev": r["execution"]["cpu_tensor_events"],
    "enc_wall_ms": enc.get("wall_ms"),
    "ane_exec_ms": round(r["ane"].get("exec_ms", 0.0), 1),
    "hidden": sha(out + "/encoder_hidden.npy"),
    "transcript": sha(out + "/transcript.txt"),
    "mel": sha(out + "/mel.npy"),
}
print(json.dumps(row, separators=(",", ":")))
with open("/var/tmp/jw16-spawn-attrib/batchpipe.jsonl", "a") as f:
    f.write(json.dumps(row) + "\n")
PY
}
for rep in 1 2 3; do
  run_arm "ac-launch$rep" AC launch $rep || true
  run_arm "aco-launch$rep" ACO launch $rep || true
done
for rep in 1 2 3; do
  run_arm "ac-resident$rep" AC resident-batch $rep || true
  run_arm "aco-resident$rep" ACO resident-batch $rep || true
done
echo "BATCHEVAL DONE"
