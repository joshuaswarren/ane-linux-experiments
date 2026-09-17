#!/bin/bash
# jwm1 fused-FFN chain E2E matrix: {ABC, ABCG} x {launch, resident-batch}.
# Runner: vk_chain.py (origin/main 23fc9a9a runner bytes + additive G hunks,
# sha 06e5f338; 63c1d3cf NOT an ancestor). Bundles: bundles-chain
# (= bundles-ffn set + 48 fused chain bundles island-ffn-L{LL}-f{m}).
# Workers: launch jwm1-oproj-place, resident r4-wheelx (same as ffn lane).
# Lock /tmp/m1-gpu.lock: flock -w 900, never steal, never unlink.
set -euo pipefail
RUN=/var/tmp/ParakeetE2ECurrentWheel
B=/var/tmp/jwm1-encoder-islands
PY=/home/joshuawarren/venv-agxgen/bin/python
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
export PYTHONPATH=$RUN/site:/var/tmp/r4-wheelx/mlx/coreml:/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
run_arm () { # name placed mode
  local name=$1 placed=$2 mode=$3
  local worker=/var/tmp/jwm1-oproj-place/mlx-omarchy-ane-worker
  [ "$mode" = "resident-batch" ] && worker=/var/tmp/r4-wheelx/mlx/bin/mlx-omarchy-ane-worker
  local outdir=$B/out-chain-$name scratch=$B/scratch-chain-$name
  echo "--- arm $name PLACED=$placed MODE=$mode $(date -Iseconds) ---"
  rm -rf $outdir $scratch; mkdir -p $outdir $scratch
  MLX_OMARCHY_PLACED=$placed ANE_ISLAND_MODE=$mode flock -w 900 /tmp/m1-gpu.lock \
  $PY /var/tmp/ParakeetE2E/parakeet_e2e.py \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model ~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018 \
    --pkg /var/tmp/ParakeetE2EAneBnns/pkg \
    --encoder-runner $RUN/vk_chain.py \
    --source /var/tmp/EncoderParityAne/encoder-source \
    --bundles /var/tmp/jwm1-encoder-islands/bundles-chain \
    --worker $worker \
    --libane /var/tmp/jwm1-oproj-place/libane-strict-fill.so \
    --ane-reference /var/tmp/EncoderParityAne/out-ane/encoder_hidden.npy \
    --scratch $scratch \
    --out $outdir \
    --deadline-ms 20000 > $B/chain-$name.log 2>&1 || { echo "ARM $name FAILED"; tail -5 $B/chain-$name.log; return 1; }
  python3 - "$outdir" "$name" <<'PY'
import hashlib, json, sys
out, name = sys.argv[1], sys.argv[2]
r = json.load(open(out + "/e2e-report.json"))
hid = hashlib.sha256(open(out + "/encoder_hidden.npy", "rb").read()).hexdigest()
trs = hashlib.sha256(open(out + "/transcript.txt", "rb").read()).hexdigest()
seq = r["layers"]["layer_6_decoder_sequence"]
enc = next((s for s in r["stages"] if isinstance(s, dict) and s.get("stage") == "encoder_ane"), {})
print(json.dumps({
    "arm": name, "status": r["status"],
    "subs": r["ane"]["submissions"],
    "prefix": seq.get("matching_prefix_length"),
    "bounds": r["layers"]["layer_5_encoder"]["all_bounds_pass"],
    "cpu_tensor_events": r["execution"]["cpu_tensor_events"],
    "gpu_ops": r["execution"]["encoder_gpu_ops"],
    "ane_ops": r["execution"]["encoder_ane_ops"],
    "encoder_ane_wall_ms": enc.get("wall_ms"),
    "ane_exec_ms": r["ane"].get("exec_ms"),
    "total_pipeline_ms": r["timing"]["total_pipeline_ms"],
    "timeouts": r["ane"].get("timeouts"),
    "hidden": hid, "transcript": trs,
}))
PY
}
run_arm abc-launch ABC launch
run_arm abc-resident ABC resident-batch
run_arm abcg-launch ABCG launch
run_arm abcg-resident ABCG resident-batch
