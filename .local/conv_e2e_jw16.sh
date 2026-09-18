#!/bin/bash
# jw16 conv-placement screen arms: regression {ABC, ABCO} x {launch, resident}
# then conv arms {ABCV, ABCVP, ABCVT, ABCVPT}. Runner vk_conv.py =
# certified e93500d2 bytes + additive V/P/T hunks. Bundles bundles-conv =
# certified base set + 77 new conv/relpos/transpose islands.
# Lock /tmp/m1-gpu.lock: flock -w 900, never steal or unlink.
set -euo pipefail
RUN=/var/tmp/ParakeetE2EJw16
B=/var/tmp/jw16-conv-place
PY=/home/joshuawarren/venv-agxgen/bin/python
export PYTHONPATH=$RUN/site:/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
run_arm () { # name placed mode
  local name=$1 placed=$2 mode=$3
  local outdir=$B/out-$name scratch=$B/scratch-$name
  echo "--- arm $name PLACED=$placed MODE=$mode $(date -Iseconds) ---"
  python3 -c "import shutil; shutil.rmtree('$outdir', ignore_errors=True); shutil.rmtree('$scratch', ignore_errors=True)"
  mkdir -p $outdir $scratch
  MLX_OMARCHY_PLACED=$placed ANE_ISLAND_MODE=$mode flock -w 900 /tmp/m1-gpu.lock \
  $PY $RUN/fused_e2e.py \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model ~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018 \
    --pkg /var/tmp/TdtLoopDefault/pkg \
    --encoder-runner /tmp/conv-lane/vk_conv.py \
    --source /var/tmp/EncoderParityAne/encoder-source \
    --ane-reference /var/tmp/EncoderParityAne/out-ane/encoder_hidden.npy \
    --bundles $B/bundles-conv \
    --worker /var/tmp/jw16-oproj-place/mlx-omarchy-ane-worker \
    --libane /var/tmp/jw16-oproj-place/libane-strict-fill.so \
    --scratch $scratch \
    --out $outdir \
    --deadline-ms 20000 > $B/$name.log 2>&1 || { echo "ARM $name FAILED"; tail -5 $B/$name.log; return 1; }
  python3 - "$outdir" "$name" <<'PY'
import hashlib, json, sys
out, name = sys.argv[1], sys.argv[2]
r = json.load(open(out + "/e2e-report.json"))
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
hid, trs, mel = sha(out + "/encoder_hidden.npy"), sha(out + "/transcript.txt"), sha(out + "/mel.npy")
seq = r["layers"]["layer_6_decoder_sequence"]
enc = next((s for s in r["stages"] if isinstance(s, dict) and s.get("stage") == "encoder_ane"), {})
row = {
    "arm": name, "status": r["status"],
    "subs": r["ane"]["submissions"], "mode": r["ane"].get("mode"),
    "rounds": r["ane"].get("rounds"),
    "prefix": seq.get("matching_prefix_length"),
    "bounds": r["layers"]["layer_5_encoder"]["all_bounds_pass"],
    "cpu_ev": r["execution"]["cpu_tensor_events"],
    "gpu_ops": r["execution"]["encoder_gpu_ops"],
    "ane_ops": r["execution"]["encoder_ane_ops"],
    "enc_wall_ms": enc.get("wall_ms"),
    "ane_exec_ms": round(r["ane"].get("exec_ms", 0.0), 1),
    "total_ms": round(r["timing"]["total_pipeline_ms"], 1),
    "timeouts": r["ane"].get("timeouts"),
    "hidden": hid, "transcript": trs, "mel": mel,
}
print(json.dumps(row, separators=(",", ":")))
with open("/var/tmp/jw16-conv-place/arms.jsonl", "a") as f:
    f.write(json.dumps(row) + "\n")
PY
}
# Digest-first: certified regression arms must pin EXACTLY before any conv arm.
run_arm abc-launch ABC launch
run_arm abco-launch ABCO launch
run_arm abc-resident ABC resident-batch
run_arm abco-resident ABCO resident-batch
run_arm abcv-launch ABCV launch
run_arm abcv-resident ABCV resident-batch
run_arm abcvp-launch ABCVP launch
run_arm abcvt-launch ABCVT launch
run_arm abcvpt-launch ABCVPT launch
run_arm abcvpt-resident ABCVPT resident-batch
echo "ALL ARMS DONE"
